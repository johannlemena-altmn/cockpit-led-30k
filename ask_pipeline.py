# -*- coding: utf-8 -*-
"""
ask_pipeline.py — Questions en langage naturel sur le pipeline Cockpit LED 30k
Lit public_data.json et répond à une question via l'API Claude.

Usage :
    python ask_pipeline.py "Combien de LED sont en attente d'audit ?"
    python ask_pipeline.py --data chemin/vers/public_data.json "Quel est le taux de pose ?"

Prérequis :
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
"""
from __future__ import annotations
import json, os, sys

try:
    import anthropic
except ImportError:
    print("[ERREUR] anthropic manquant. Lancer : pip install anthropic", file=sys.stderr)
    sys.exit(1)

MODEL     = "claude-opus-4-8"
DATA_PATH = "public_data.json"


def load_data(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_context(data: dict) -> str:
    """Format public_data.json complet (pipeline + quickwins + delta + dossiers) pour le prompt."""
    lines = [
        f"Date : {data.get('generated','?')}",
        f"LED signées : {data.get('led_signees',0):,} · Dossiers : {data.get('nb_dossiers',0):,}",
        f"Prime totale : {data.get('prime_total',0):,} € · LED moy/dossier : {data.get('led_moy','?')} (méd {data.get('led_med','?')})",
        f"Objectif mensuel : {data.get('objectif_mensuel',30000):,} LED · Taux de pose : {data.get('taux_pose_pct','?')}% (cible ≥95%)",
    ]

    if p := data.get("pipeline"):
        dep = next((e for e in p.get("etapes", []) if e["id"] == "depose"), {})
        lines += [
            "",
            "=== PIPELINE BETOOL ===",
            f"Total actif : {p.get('total_actif','?')} dossiers / {p.get('led_actif',0):,} LED",
            f"Zone d'action immédiate : {p.get('action_n','?')} dossiers / {p.get('action_led',0):,} LED",
            f"Déposé Total Energies : {dep.get('n','?')} dossiers / {dep.get('led',0):,} LED ({p.get('pct_depose','?')}%)",
        ]
        for e in p.get("etapes", []):
            age = f" · âge moy {e['age_moy']}j" if e.get("age_moy") else ""
            lines.append(f"  {e['id']:25s} {e['n']:>4} dossiers / {e['led']:>7,} LED{age}")

    if qw := data.get("quickwins"):
        lines += ["", "=== QUICKWINS (actions classées par priorité) ==="]
        for q in qw:
            old_info = f" ({q['blocage_old']} bloqués >7j)" if q.get("blocage_old") else ""
            lines.append(f"#{q['rank']} [{q['urgence'].upper()}] {q['stage_id']} — {q['n']} dos / {q['led']:,} LED{old_info}")
            lines.append(f"   Effort : {q['effort']}")
            lines.append(f"   Action : {q['action']}")
            if q.get("top5_led"):
                lines.append(f"   Top 5 dossiers (plus gros) : {q['top5_led']:,} LED")
            if tops := q.get("top"):
                ages = [t["age_days"] for t in tops[:5] if t.get("age_days") is not None]
                leds = [t["led"] for t in tops[:5] if t.get("led", 0) > 0]
                if leds:  lines.append(f"   LED des top 5 : {leds}")
                if ages:  lines.append(f"   Âges (jours)  : {ages}")

    if dp := data.get("dossiers_pipeline"):
        lines += ["", "=== DOSSIERS PAR STAGE (anonymes, triés par LED desc) ==="]
        for sid, dos in dp.items():
            if dos:
                leds = [d["led"] for d in dos[:10]]
                lines.append(f"  {sid}: top 10 LED = {leds}")

    if delta := data.get("delta"):
        lines += ["", f"=== DELTA vs {delta.get('date_ref','J-1')} ===",
                  f"LED déposées : {'+' if delta['deposees_delta']>=0 else ''}{delta['deposees_delta']:,}",
                  f"Dossiers à traiter : {'+' if delta['action_n_delta']>=0 else ''}{delta['action_n_delta']}",
                  f"Bilan : {delta['bilan']}"]

    if br := data.get("brief"):
        lines += ["", "=== BRIEF DU JOUR ===",
                  f"Statut : {br.get('statut','?')}",
                  f"Headline : {br.get('headline','?')}",
                  f"Top action : {br.get('top_action','?')}",
                  f"Objectif du jour : ~{br.get('objectif_jour',0):,} LED"]

    return "\n".join(lines)


SYSTEM_PROMPT = """Tu es l'assistant opérationnel du cockpit LED 30k — Énergie Responsable.
Objectif : aider les équipes à déposer 30 000 LED/mois sous fiche BAT-EQ-127 (entrepôts,
délégataire iSolidarité, prime ~200 €/personne, via Total Energies).

La chaîne de traitement est :
  Installation en cours → Attente audit → Attente signature → Modif audit → Déposé TE

Quickwins prioritaires (toujours dans cet ordre) :
  1. modif_audit : dossiers BLOQUÉS — corriger et envoyer à Total Energies
  2. attente_signature : relancer les clients qui n'ont pas encore signé
  3. attente_audit : traiter les audits (plus gros dossiers en premier = max LED/effort)

Règles de réponse :
- Court, direct, actionnable. Pas de bla-bla.
- Chiffres exacts si disponibles, sinon dis-le.
- Quand on demande "quoi faire", donne une liste numérotée avec nb de dossiers + LED en jeu.
- Quand on demande une projection, calcule-la explicitement.
- Priorise TOUJOURS modif_audit en premier (bloquant pour le dépôt).
"""


def ask(question: str, data_path: str = DATA_PATH,
        history: list | None = None) -> tuple[str, list]:
    """Pose une question. Retourne (réponse, historique mis à jour).
    history = liste de messages pour la conversation multi-tours."""
    if not os.path.isfile(data_path):
        return f"[ERREUR] Fichier de données introuvable : {data_path}", history or []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "[ERREUR] ANTHROPIC_API_KEY non défini.", history or []

    data    = load_data(data_path)
    context = build_context(data)
    client  = anthropic.Anthropic(api_key=api_key)

    if not history:
        # Premier message : injecter le contexte
        history = [{
            "role": "user",
            "content": f"Voici les données actuelles du cockpit :\n\n{context}",
        }, {
            "role": "assistant",
            "content": "Compris. Je connais le pipeline et les quickwins. Posez vos questions.",
        }]

    history.append({"role": "user", "content": question})

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=history,
    )
    answer = message.content[0].text
    history.append({"role": "assistant", "content": answer})
    return answer, history


def interactive_mode(data_path: str):
    """Mode conversation multi-tours."""
    print("\n=== ASSISTANT COCKPIT LED 30k ===")
    print("Tapez vos questions. 'quit' ou Ctrl+C pour quitter.\n")
    history: list = []
    while True:
        try:
            q = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            break
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue
        answer, history = ask(q, data_path, history)
        print(f"\nAssistant : {answer}\n")


def main():
    args = sys.argv[1:]
    data_path = DATA_PATH
    if "--data" in args:
        idx = args.index("--data")
        if idx + 1 < len(args):
            data_path = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if "-i" in args or "--interactive" in args:
        interactive_mode(data_path)
        return

    if not args:
        print("Usage: python ask_pipeline.py [--data public_data.json] [-i] \"Votre question\"",
              file=sys.stderr)
        print("  -i / --interactive  : mode conversation multi-tours", file=sys.stderr)
        sys.exit(1)

    question = " ".join(a for a in args if not a.startswith("-"))
    print(f"Question : {question}\n")
    answer, _ = ask(question, data_path)
    print(answer)


if __name__ == "__main__":
    main()
