# -*- coding: utf-8 -*-
"""
daily_brief.py — Brief quotidien Cockpit LED 30k
Génère un résumé actionnable du pipeline + calcule le delta J-1.
Met à jour public_data.json avec les clés "brief" et "delta".

Usage :
    python daily_brief.py                         → lit public_data.json
    python daily_brief.py --data public_data.json
    python daily_brief.py --no-update             → affiche sans modifier le JSON
"""
from __future__ import annotations
import json, os, sys
from datetime import date, datetime, timedelta

DATA_PATH = "public_data.json"
SNAP_DIR  = "snapshots"
OBJECTIF_MENSUEL = 30_000
JOURS_MOIS       = 22  # jours ouvrés

# ---------------------------------------------------------------------------

def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_yesterday_snapshot(data_path: str) -> dict | None:
    snap_dir  = os.path.join(os.path.dirname(os.path.abspath(data_path)), SNAP_DIR)
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    snap_path = os.path.join(snap_dir, f"{yesterday}.json")
    if os.path.isfile(snap_path):
        with open(snap_path, encoding="utf-8") as f:
            return json.load(f)
    # Tenter J-2 si J-1 absent (weekend)
    for delta in range(2, 5):
        d = (date.today() - timedelta(days=delta)).strftime("%Y-%m-%d")
        p = os.path.join(snap_dir, f"{d}.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                snap = json.load(f)
                snap["_ref_date"] = d
                return snap
    return None


def compute_delta(current_pipeline: dict, prev_snap: dict | None) -> dict | None:
    if not prev_snap or not prev_snap.get("pipeline"):
        return None
    prev   = prev_snap["pipeline"]
    today  = current_pipeline
    ref    = prev_snap.get("_ref_date", (date.today() - timedelta(days=1)).strftime("%Y-%m-%d"))

    etapes_delta = []
    prev_idx = {e["id"]: e for e in prev.get("etapes", [])}
    for e in today.get("etapes", []):
        p = prev_idx.get(e["id"])
        if p:
            dn = e["n"] - p["n"]
            dl = e["led"] - p["led"]
            if dn != 0 or dl != 0:
                etapes_delta.append({
                    "id": e["id"], "label": e["label"],
                    "n_delta": dn, "led_delta": dl,
                })

    depose_now  = next((e for e in today.get("etapes", []) if e["id"] == "depose"), {})
    depose_prev = prev_idx.get("depose", {})
    deposees_delta = (depose_now.get("led", 0) - depose_prev.get("led", 0))

    bilan = "stable"
    if deposees_delta > 0:
        bilan = "progression"
    elif today.get("action_n", 0) < prev.get("action_n", 0):
        bilan = "pipeline_reduit"

    return {
        "date_ref":       ref,
        "deposees_delta": deposees_delta,
        "action_n_delta": today.get("action_n", 0) - prev.get("action_n", 0),
        "etapes":         etapes_delta,
        "bilan":          bilan,
    }


def compute_brief(data: dict, delta: dict | None) -> dict:
    p  = data.get("pipeline", {})
    qw = data.get("quickwins", [])
    tp = data.get("taux_pose_pct", 0)

    # Objectif journalier
    today_date    = date.today()
    day_of_month  = today_date.day
    days_left     = max(JOURS_MOIS - day_of_month, 1)
    obj_restant   = max(OBJECTIF_MENSUEL - p.get("pct_depose", 0) * OBJECTIF_MENSUEL // 100, 0)
    cible_jour    = round(obj_restant / days_left) if days_left else 0

    urgences = []
    for q in qw:
        if q["urgence"] == "urgent":
            urgences.append(
                f"{q['n']} modif_audit bloquants → {q['led']} LED libérées en {q['effort']}"
            )

    top_action = qw[0]["action"] if qw else "Analyser le pipeline."

    statut = "URGENT" if any(q["urgence"] == "urgent" and q["n"] > 0 for q in qw) else "ACTION_REQUISE"

    return {
        "date":        today_date.strftime("%Y-%m-%d"),
        "statut":      statut,
        "headline":    f"{p.get('action_n', 0)} dossiers actionnables · {p.get('action_led', 0):,} LED à débloquer".replace(",", " "),
        "urgences":    urgences,
        "top_action":  top_action,
        "objectif_jour": cible_jour,
        "taux_pose_pct": tp,
        "pipeline_bilan": delta["bilan"] if delta else "premier_run",
    }


# ---------------------------------------------------------------------------
# Affichage terminal
# ---------------------------------------------------------------------------

SEP = "─" * 52

def _sign(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)

def _flag(urgence: str) -> str:
    return {"urgent": "🔴", "relance": "📞", "action": "📋"}.get(urgence, "•")


def print_brief(data: dict, delta: dict | None):
    today_str = date.today().strftime("%d/%m/%Y")
    p  = data.get("pipeline", {})
    qw = data.get("quickwins", [])
    br = data.get("brief", {})
    tp = data.get("taux_pose_pct", "?")

    print(f"\n{'═'*52}")
    print(f"  BRIEF LED 30k — {today_str}")
    print(f"{'═'*52}")

    # État pipeline
    print(f"\n  Pipeline actif  : {p.get('total_actif', '?')} dossiers · {p.get('led_actif', 0):>7,} LED".replace(",", " "))
    print(f"  Déposés (TE)    : {next((e['n'] for e in p.get('etapes',[]) if e['id']=='depose'), '?')} dossiers · "
          f"{next((e['led'] for e in p.get('etapes',[]) if e['id']=='depose'), 0):>7,} LED ({p.get('pct_depose','?')}%)".replace(",", " "))
    print(f"  Taux de pose    : {tp}% (cible ≥95%) — écart {95-int(tp)}pt")

    # Delta J-1
    if delta:
        print(f"\n{SEP}")
        print(f"  Δ vs {delta['date_ref']} :")
        if delta["deposees_delta"] != 0:
            print(f"    Déposées  : {_sign(delta['deposees_delta'])} LED")
        if delta["action_n_delta"] != 0:
            print(f"    À traiter : {_sign(delta['action_n_delta'])} dossiers")
        bilan_lbl = {"progression": "✅ Pipeline progresse", "pipeline_reduit": "📉 Moins de travail en attente",
                     "stable": "= Stable"}.get(delta["bilan"], delta["bilan"])
        print(f"    Bilan     : {bilan_lbl}")

    # Quickwins
    print(f"\n{SEP}")
    print("  ACTIONS PRIORITAIRES DU JOUR\n")
    for q in qw:
        ages = [d["age_days"] for d in q.get("top", []) if d.get("age_days") is not None]
        age_info = f" · {q['blocage_old']} depuis >7j" if q.get("blocage_old") else ""
        print(f"  {_flag(q['urgence'])} #{q['rank']} — {q['stage_id'].upper()}")
        print(f"     {q['n']} dossiers · {q['led']:,} LED{age_info}".replace(",", " "))
        print(f"     Effort   : {q['effort']}")
        print(f"     Action   : {q['action']}")
        if q.get("top5_led"):
            print(f"     Top 5    : {q['top5_led']:,} LED (les 5 plus gros)".replace(",", " "))
        if ages:
            print(f"     Âges     : {ages[:5]} jours")
        print()

    # Objectif jour
    obj_j = br.get("objectif_jour", 0)
    if obj_j:
        print(f"{SEP}")
        print(f"  Objectif du jour : ~{obj_j:,} LED à faire progresser".replace(",", " "))

    # Impact potentiel immédiat
    if qw:
        impact_urgent = sum(q["led"] for q in qw if q["urgence"] == "urgent")
        if impact_urgent:
            print(f"\n  💡 Impact immédiat si modifs corrigées aujourd'hui : +{impact_urgent:,} LED".replace(",", " "))
    print(f"\n{'═'*52}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args      = sys.argv[1:]
    data_path = DATA_PATH
    no_update = "--no-update" in args
    if "--data" in args:
        idx = args.index("--data")
        if idx + 1 < len(args):
            data_path = args[idx + 1]

    if not os.path.isfile(data_path):
        print(f"[ERREUR] {data_path} introuvable. Lancer betool_summary.py d'abord.", file=sys.stderr)
        sys.exit(1)

    data  = load(data_path)
    prev  = load_yesterday_snapshot(data_path)
    delta = compute_delta(data.get("pipeline", {}), prev)
    brief = compute_brief(data, delta)

    data["brief"] = brief
    if delta:
        data["delta"] = delta

    print_brief(data, delta)

    if not no_update:
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] {data_path} enrichi avec brief + delta")


if __name__ == "__main__":
    main()
