# -*- coding: utf-8 -*-
"""
betool_summary.py — Cockpit LED 30k
Lit l'export BETOOL (Excel) et ajoute les stats pipeline dans public_data.json.

Usage :
    python betool_summary.py data/betool.xlsx
    python betool_summary.py data/betool.xlsx --output public_data.json
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict
from datetime import date, datetime

try:
    import openpyxl
except ImportError:
    print("[ERREUR] openpyxl manquant. Lancer : pip install openpyxl", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration du pipeline (ordre = ordre de la chaîne)
# ---------------------------------------------------------------------------
PIPELINE_STAGES = [
    {
        "id":          "en_cours",
        "label":       "Installation en cours",
        "short":       "En cours",
        "statuts":     ["Installation en cours", "installation en cours EXPRESS",
                        "Installation en Interne"],
        "urgence":     "normal",
        "conseil":     "Attendre fin d'installation avant action.",
    },
    {
        "id":          "attente_audit",
        "label":       "Attente doc & audit",
        "short":       "Audit ⚡",
        "statuts":     ["Installation Fini - En attente doc et audit",
                        "Installation fini en Interne"],
        "urgence":     "action",
        "conseil":     "Contrôler audits → envoyer au client → commenter auditeurs.",
    },
    {
        "id":          "attente_signature",
        "label":       "Attente signature",
        "short":       "Signature ⏳",
        "statuts":     ["Installation fini - En attente signature doc"],
        "urgence":     "relance",
        "conseil":     "Rappeler le client pour signature du dossier.",
    },
    {
        "id":          "modif_audit",
        "label":       "Modif audit avant dépôt",
        "short":       "Modif 🔴",
        "statuts":     ["Installation Fini - Doc ok - Modif Audit"],
        "urgence":     "urgent",
        "conseil":     "Corriger les audits → envoyer à Total Energies.",
    },
    {
        "id":          "depose",
        "label":       "Déposé ✅",
        "short":       "Déposé",
        "statuts":     ["Déposé"],
        "urgence":     "ok",
        "conseil":     "En attente validation + paiement Total Energies.",
    },
]

# Index de recherche rapide statut → étape
_STATUT_TO_STAGE = {}
for _s in PIPELINE_STAGES:
    for _st in _s["statuts"]:
        _STATUT_TO_STAGE[_st] = _s["id"]


# ---------------------------------------------------------------------------
# Lecture Excel
# ---------------------------------------------------------------------------

def load_betool(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h) if h is not None else "" for h in rows[0]]
    return [dict(zip(headers, row)) for row in rows[1:]]


# ---------------------------------------------------------------------------
# Calcul pipeline
# ---------------------------------------------------------------------------

def compute_pipeline(records: list[dict]) -> dict:
    today = date.today()

    # Accumulateurs par stage_id
    acc: dict[str, dict] = {
        s["id"]: {"n": 0, "led": 0, "ages": []}
        for s in PIPELINE_STAGES
    }

    for rec in records:
        statut = rec.get("Statut") or ""
        stage_id = _STATUT_TO_STAGE.get(statut)
        if stage_id is None:
            continue

        # LED
        raw_led = rec.get("Nombre de points lumineux ?")
        try:
            led = int(float(str(raw_led))) if raw_led not in (None, "") else 0
        except (ValueError, TypeError):
            led = 0

        # Âge depuis dernière mise à jour
        upd = rec.get("Last updateTime")
        age = None
        if upd:
            try:
                d = upd.date() if hasattr(upd, "date") else datetime.strptime(str(upd)[:10], "%Y-%m-%d").date()
                age = (today - d).days
            except Exception:
                pass

        acc[stage_id]["n"]   += 1
        acc[stage_id]["led"] += led
        if age is not None:
            acc[stage_id]["ages"].append(age)

    # Construction de la réponse
    etapes = []
    total_actif_n   = 0
    total_actif_led = 0

    for s in PIPELINE_STAGES:
        a   = acc[s["id"]]
        avg_age = round(sum(a["ages"]) / len(a["ages"])) if a["ages"] else None
        etape = {
            "id":      s["id"],
            "label":   s["label"],
            "short":   s["short"],
            "urgence": s["urgence"],
            "conseil": s["conseil"],
            "n":       a["n"],
            "led":     a["led"],
            "age_moy": avg_age,
        }
        etapes.append(etape)
        if s["id"] != "depose":
            total_actif_n   += a["n"]
            total_actif_led += a["led"]

    # Zone d'action immédiate (hors "en cours" et "déposé")
    action_ids  = {"attente_audit", "attente_signature", "modif_audit"}
    action_n    = sum(acc[i]["n"]   for i in action_ids)
    action_led  = sum(acc[i]["led"] for i in action_ids)

    depose      = acc["depose"]
    total_led   = depose["led"] + total_actif_led
    pct_depose  = round(depose["led"] / total_led * 100) if total_led else 0

    return {
        "generated":    today.strftime("%Y-%m-%d"),
        "total_actif":  total_actif_n,
        "led_actif":    total_actif_led,
        "action_n":     action_n,
        "action_led":   action_led,
        "pct_depose":   pct_depose,
        "etapes":       etapes,
    }


# ---------------------------------------------------------------------------
# Mise à jour public_data.json
# ---------------------------------------------------------------------------

def update_public_json(pipeline: dict, output_path: str = "public_data.json"):
    data = {}
    if os.path.isfile(output_path):
        with open(output_path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass

    data["pipeline"] = pipeline
    data["generated"] = date.today().strftime("%Y-%m-%d")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {output_path} mis à jour avec pipeline BETOOL")
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    output = "public_data.json"
    for i, a in enumerate(sys.argv[1:]):
        if a == "--output" and i + 2 < len(sys.argv):
            output = sys.argv[i + 2]

    if not args:
        print("Usage: python betool_summary.py <fichier.xlsx> [--output public_data.json]",
              file=sys.stderr)
        sys.exit(1)

    xlsx_path = args[0]
    if not os.path.isfile(xlsx_path):
        print(f"[ERREUR] Fichier introuvable : {xlsx_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Lecture BETOOL : {xlsx_path}")
    records  = load_betool(xlsx_path)
    print(f"  {len(records)} lignes chargées")

    pipeline = compute_pipeline(records)

    print(f"\nPipeline BETOOL :")
    for e in pipeline["etapes"]:
        print(f"  {e['short']:<22} {e['n']:>4} dossiers  {e['led']:>6} LED")
    print(f"\n  Action immédiate : {pipeline['action_n']} dossiers / {pipeline['action_led']} LED")
    print(f"  Déposé : {pipeline['etapes'][-1]['n']} dossiers / {pipeline['etapes'][-1]['led']} LED "
          f"({pipeline['pct_depose']}% du total)")

    update_public_json(pipeline, output)


if __name__ == "__main__":
    main()
