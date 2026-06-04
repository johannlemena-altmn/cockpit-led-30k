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
    """Format public_data.json en contexte lisible pour le prompt."""
    lines = [
        f"Date de génération : {data.get('generated','?')}",
        f"LED signées totales : {data.get('led_signees','?'):,}",
        f"Nombre de dossiers : {data.get('nb_dossiers','?'):,}",
        f"Prime totale : {data.get('prime_total','?'):,} €",
        f"LED moy/dossier : {data.get('led_moy','?')} (médiane {data.get('led_med','?')})",
        f"Objectif mensuel : {data.get('objectif_mensuel','?'):,} LED",
        f"Taux de pose : {data.get('taux_pose_pct','?')} %",
    ]
    if mois := data.get("mois"):
        lines.append("LED signées par mois :")
        for m in mois[-6:]:
            lines.append(f"  {m.get('mois','?')} : {m.get('led',0):,} LED")
    if p := data.get("pipeline"):
        lines += [
            "",
            "Pipeline BETOOL (chaîne active) :",
            f"  Total actif (hors déposé) : {p.get('total_actif','?')} dossiers / {p.get('led_actif','?'):,} LED",
            f"  Zone d'action immédiate : {p.get('action_n','?')} dossiers / {p.get('action_led','?'):,} LED",
            f"  Déposé : {p.get('pct_depose','?')} % du volume total",
        ]
        for e in p.get("etapes", []):
            age = f"  âge moy {e['age_moy']}j" if e.get("age_moy") else ""
            lines.append(f"  [{e['id']}] {e['label']} — {e['n']} dossiers / {e['led']:,} LED{age}")
    return "\n".join(lines)


SYSTEM_PROMPT = """Tu es l'assistant du cockpit LED 30k d'Énergie Responsable.
Tu aides les équipes à piloter l'objectif de 30 000 LED déposées par mois (fiche BAT-EQ-127,
secteur entrepôts, délégataire iSolidarité, prime ~200 €/personne).

Règles :
- Réponds en français, de façon concise et actionnable.
- Cite les chiffres exacts quand disponibles.
- Si une information n'est pas dans les données, dis-le clairement.
- Pour les recommandations, priorise les étapes urgentes du pipeline (modif_audit > attente_signature > attente_audit).
"""


def ask(question: str, data_path: str = DATA_PATH) -> str:
    if not os.path.isfile(data_path):
        return f"[ERREUR] Fichier de données introuvable : {data_path}"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "[ERREUR] ANTHROPIC_API_KEY non défini. Exporter la variable d'environnement."

    data    = load_data(data_path)
    context = build_context(data)
    client  = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Voici les données actuelles du cockpit :\n\n{context}\n\n---\n\nQuestion : {question}",
        }],
    )
    return message.content[0].text


def main():
    args = sys.argv[1:]
    data_path = DATA_PATH
    if "--data" in args:
        idx = args.index("--data")
        if idx + 1 < len(args):
            data_path = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        print("Usage: python ask_pipeline.py [--data public_data.json] \"Votre question\"",
              file=sys.stderr)
        sys.exit(1)

    question = " ".join(args)
    print(f"Question : {question}\n")
    answer = ask(question, data_path)
    print(answer)


if __name__ == "__main__":
    main()
