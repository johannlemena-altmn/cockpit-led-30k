# -*- coding: utf-8 -*-
"""
snapshot.py — Cockpit LED 30k
Archive un instantané quotidien (léger, anonymisé) de l'état du pipeline à
partir de public_data.json, pour suivre l'évolution jour/semaine/mois.

Écrit :
  history/YYYY-MM-DD.json  → snapshot complet du jour (agrégats + top prios)
  history/timeseries.json  → série temporelle compacte (1 ligne/jour, pour les
                             graphes macro de history_dashboard.html)
  history/index.json       → liste des dates disponibles

SÉCURITÉ PII : ne stocke QUE des agrégats + références internes non nominatives
(n° Waresito, ticket LE-XXXX, réf ERS). Les dossiers sans réf (installs internes)
reçoivent un identifiant de position « #N · interne », jamais de nom client.
Un garde-fou refuse l'écriture si du PII est détecté.

Usage :
    python snapshot.py                       # lit public_data.json
    python snapshot.py --input public_data.json --date 2026-06-04
"""
from __future__ import annotations
import json, os, re, sys, glob
from datetime import date, datetime

HISTORY_DIR = "history"
TOP_PRIOS_CAP = 30   # on archive 30 prios/jour (la page en affiche 10-20)

# Priorité d'affichage (poids décroissant) par stage, toutes sources confondues
STAGE_PRIORITY = {
    "modif_audit":       100,  # betool : modifs bloquantes avant dépôt
    "modif_a_faire":      95,  # audit  : études bloquées
    "attente_signature":  70,  # betool : relances client
    "attente_audit":      50,  # betool : audits à contrôler
    "etude_prête":        40,  # audit  : à valider
}

STAGE_LABELS = {
    "modif_audit":       "Modif audit (avant dépôt)",
    "modif_a_faire":     "Modif audit (étude)",
    "attente_signature": "Attente signature",
    "attente_audit":     "Attente audit",
    "etude_prête":       "Étude prête",
}


# ──────────────────────────────────────────────────────────────────────────
def _etapes_map(etapes: list, vol_key: str) -> dict:
    """Transforme [{id,n,led/cellules}, …] → {id: {n, vol}}."""
    out = {}
    for e in etapes or []:
        out[e.get("id", "?")] = {"n": e.get("n", 0), "vol": e.get(vol_key, 0)}
    return out


def compute_snapshot(d: dict, snap_date: str) -> dict:
    pipeline  = d.get("pipeline", {})
    audit     = d.get("audit_pipeline", {})
    confirmes = d.get("confirmes", {})
    autres    = d.get("autres_secteurs", {})

    sources = []
    if pipeline:  sources.append("betool")
    if audit:     sources.append("audit")
    if confirmes: sources.append("confirmes")

    # ── Top prios du jour (multi-sources) ────────────────────────────────
    prios = []

    # 1) BETOOL : dossiers actionnables listés dans les quickwins
    for qw in d.get("quickwins", []):
        stage = qw.get("stage_id", "?")
        for i, dos in enumerate(qw.get("top", [])):
            ref = (dos.get("ref") or "").strip()
            internal = not ref
            prios.append({
                "source":      "betool",
                "stage":       stage,
                "stage_label": STAGE_LABELS.get(stage, stage),
                "ref":         ref or f"#{i+1} · interne",
                "internal":    internal,
                "led":         dos.get("led", 0),
                "cellules":    None,
                "age_days":    dos.get("age_days"),
                "prio":        STAGE_PRIORITY.get(stage, 10),
            })

    # 2) AUDIT : dossiers « Modification à faire »
    for i, dos in enumerate(audit.get("modif_dossiers", [])):
        ref = (dos.get("ref") or "").strip()
        internal = not ref
        prios.append({
            "source":      "audit",
            "stage":       "modif_a_faire",
            "stage_label": STAGE_LABELS["modif_a_faire"],
            "ref":         ref or f"#{i+1} · interne",
            "internal":    internal,
            "led":         dos.get("led", 0),
            "cellules":    dos.get("cellules", 0),
            "age_days":    dos.get("age_days"),
            "prio":        STAGE_PRIORITY["modif_a_faire"],
        })

    # Tri : priorité du stage, puis volume (LED sinon cellules), puis ancienneté
    def _vol(p): return p["led"] or (p["cellules"] or 0)
    prios.sort(key=lambda p: (-p["prio"], -_vol(p), -(p["age_days"] or 0)))
    top_prios = prios[:TOP_PRIOS_CAP]

    snap = {
        "date":    snap_date,
        "sources": sources,
        "kpis": {
            "led_signees": d.get("led_signees", 0),
            "nb_dossiers": d.get("nb_dossiers", 0),
            "prime_total": d.get("prime_total", 0),
            "taux_pose":   d.get("taux_pose_pct", 0),
        },
        "pipeline": {
            "total_actif": pipeline.get("total_actif", 0),
            "led_actif":   pipeline.get("led_actif", 0),
            "action_led":  pipeline.get("action_led", 0),
            "pct_depose":  pipeline.get("pct_depose", 0),
            "etapes":      _etapes_map(pipeline.get("etapes", []), "led"),
        },
        "audit": {
            "total":          audit.get("total", 0),
            "cellules_total": audit.get("cellules_total", 0),
            "etapes":         _etapes_map(audit.get("etapes", []), "cellules"),
        },
        "confirmes": {
            "n":     confirmes.get("n", 0),
            "led":   confirmes.get("led", 0),
            "prime": confirmes.get("prime", 0),
        },
        "autres_secteurs": {
            "n":                 autres.get("n", 0),
            "led":               autres.get("led", 0),
            "en_attente_photos": autres.get("en_attente_photos", 0),
        },
        "top_prios": top_prios,
    }
    return snap


# ──────────────────────────────────────────────────────────────────────────
def _compact_day(snap: dict) -> dict:
    """Ligne compacte (sans top_prios) pour la série temporelle des graphes."""
    return {
        "date":          snap["date"],
        "sources":       snap["sources"],
        "led_signees":   snap["kpis"]["led_signees"],
        "taux_pose":     snap["kpis"]["taux_pose"],
        "led_actif":     snap["pipeline"]["led_actif"],
        "action_led":    snap["pipeline"]["action_led"],
        "pct_depose":    snap["pipeline"]["pct_depose"],
        "pipeline":      {k: v["n"] for k, v in snap["pipeline"]["etapes"].items()},
        "pipeline_led":  {k: v["vol"] for k, v in snap["pipeline"]["etapes"].items()},
        "audit":         {k: v["n"] for k, v in snap["audit"]["etapes"].items()},
        "confirmes_led": snap["confirmes"]["led"],
        "confirmes_n":   snap["confirmes"]["n"],
    }


def _find_reference(snap_date: str):
    """Snapshot de référence pour le delta « depuis la dernière mise à jour ».

    Priorité :
      1. fichier du jour déjà présent  → delta INTRA-JOUR (ré-export same-day)
      2. sinon, jour archivé le + récent antérieur → delta J-1.
    Retourne (ref_snap | None, kind: 'intraday' | 'jminus' | None).
    """
    today_file = os.path.join(HISTORY_DIR, f"{snap_date}.json")
    if os.path.isfile(today_file):
        try:
            with open(today_file, encoding="utf-8") as fh:
                return json.load(fh), "intraday"
        except json.JSONDecodeError:
            pass
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "20*-*-*.json")))
    prior = [f for f in files if os.path.basename(f)[:10] < snap_date]
    if prior:
        try:
            with open(prior[-1], encoding="utf-8") as fh:
                return json.load(fh), "jminus"
        except json.JSONDecodeError:
            pass
    return None, None


def _signature(snap: dict) -> str:
    """Empreinte des métriques clés — sert à détecter un export identique
    (idempotence : ne pas remettre le delta à zéro si la donnée n'a pas bougé)."""
    k = snap.get("kpis", {})
    p = snap.get("pipeline", {})
    dep = (p.get("etapes", {}).get("depose") or {})
    a = snap.get("audit", {}).get("etapes", {})
    parts = [
        k.get("led_signees", 0), k.get("taux_pose", 0),
        p.get("led_actif", 0), p.get("action_led", 0),
        dep.get("n", 0), dep.get("vol", 0),
        (a.get("modif_a_faire") or {}).get("n", 0),
        snap.get("confirmes", {}).get("led", 0),
        snap.get("confirmes", {}).get("n", 0),
    ]
    return "|".join(str(x) for x in parts)


def compute_delta(new_snap: dict, ref: dict, kind: str) -> dict | None:
    """Delta agrégé entre le snapshot courant et sa référence.

    Convention de signe : valeur brute (cur - ref). L'interprétation
    bon/mauvais est portée par le front (déposés ↑ = bon, stock actif ↓ = bon).
    """
    if not ref:
        return None

    def _n(etapes: dict, k: str) -> int:
        return (etapes.get(k) or {}).get("n", 0)

    def _vol(etapes: dict, k: str) -> int:
        return (etapes.get(k) or {}).get("vol", 0)

    nk, rk = new_snap["kpis"], ref.get("kpis", {})
    np_, rp = new_snap["pipeline"], ref.get("pipeline", {})
    na, ra = new_snap["audit"].get("etapes", {}), ref.get("audit", {}).get("etapes", {})
    nc, rc = new_snap["confirmes"], ref.get("confirmes", {})
    npe, rpe = np_.get("etapes", {}), rp.get("etapes", {})

    return {
        "ref_date":      ref.get("date", ""),
        "kind":          kind,                       # 'intraday' | 'jminus'
        "taux_pose":     nk.get("taux_pose", 0) - rk.get("taux_pose", 0),
        "led_signees":   nk.get("led_signees", 0) - rk.get("led_signees", 0),
        "deposees_n":    _n(npe, "depose") - _n(rpe, "depose"),
        "deposees_led":  _vol(npe, "depose") - _vol(rpe, "depose"),
        "led_actif":     np_.get("led_actif", 0) - rp.get("led_actif", 0),
        "action_led":    np_.get("action_led", 0) - rp.get("action_led", 0),
        "modif_audit":   _n(na, "modif_a_faire") - _n(ra, "modif_a_faire"),
        "confirmes_led": nc.get("led", 0) - rc.get("led", 0),
        "confirmes_n":   nc.get("n", 0) - rc.get("n", 0),
    }


def rebuild_indexes():
    """Régénère timeseries.json + index.json en scannant history/*.json."""
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "20*-*-*.json")))
    dates, days = [], []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                snap = json.load(fh)
        except json.JSONDecodeError:
            continue
        dates.append(snap["date"])
        days.append(_compact_day(snap))
    days.sort(key=lambda x: x["date"])
    dates.sort()
    with open(os.path.join(HISTORY_DIR, "timeseries.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": date.today().strftime("%Y-%m-%d"), "days": days},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(HISTORY_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": date.today().strftime("%Y-%m-%d"), "dates": dates},
                  f, ensure_ascii=False, indent=2)
    return len(dates)


# ── Garde-fou PII ─────────────────────────────────────────────────────────
def _assert_no_pii(block: dict):
    blob = json.dumps(block, ensure_ascii=False)
    for pat, label in [(r"\b\d{14}\b", "SIRET"),
                       (r"[\w.+-]+@[\w-]+\.[\w.-]+", "email"),
                       (r"\b0[1-9](?:[\s.-]?\d{2}){4}\b", "téléphone"),
                       (r"\+33\d{9}", "téléphone")]:
        if re.search(pat, blob):
            raise SystemExit(f"[STOP PII] {label} détecté dans le snapshot — écriture annulée.")


def main():
    inp = "public_data.json"
    snap_date = date.today().strftime("%Y-%m-%d")
    if "--input" in sys.argv:
        i = sys.argv.index("--input")
        if i + 1 < len(sys.argv): inp = sys.argv[i + 1]
    if "--date" in sys.argv:
        i = sys.argv.index("--date")
        if i + 1 < len(sys.argv): snap_date = sys.argv[i + 1]

    if not os.path.isfile(inp):
        print(f"[ERREUR] {inp} introuvable.", file=sys.stderr)
        sys.exit(1)

    with open(inp, encoding="utf-8") as f:
        data = json.load(f)

    # Si public_data.json porte une date de génération, la respecter.
    gen = data.get("generated")
    if gen and re.match(r"\d{4}-\d{2}-\d{2}", str(gen)) and "--date" not in sys.argv:
        snap_date = gen

    snap = compute_snapshot(data, snap_date)

    # ── Delta « depuis la dernière mise à jour » (avant écrasement) ──────────
    ref, kind = _find_reference(snap_date)
    cur_sig = _signature(snap)
    ref_delta = (ref or {}).get("delta") or {}
    if ref and ref_delta.get("cur_sig") == cur_sig:
        # Donnée identique au snapshot existant → on PRÉSERVE le delta précédent
        # (idempotence : re-run / cron quotidien ne doit pas écraser le mouvement réel).
        delta = ref_delta
    else:
        delta = compute_delta(snap, ref, kind)
        if delta:
            delta["cur_sig"] = cur_sig
    if delta:
        snap["delta"] = delta

    _assert_no_pii(snap)

    os.makedirs(HISTORY_DIR, exist_ok=True)
    out = os.path.join(HISTORY_DIR, f"{snap_date}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)

    # Réinjecte le delta dans public_data.json pour le cockpit du jour
    if delta:
        try:
            data["delta"] = delta
            with open(inp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"[WARN] delta non réinjecté dans {inp} : {e}", file=sys.stderr)

    n = rebuild_indexes()
    tp = len(snap["top_prios"])
    print(f"[OK] {out} écrit · {tp} top prios · sources={snap['sources']}")
    if delta:
        lbl = "intra-jour" if kind == "intraday" else f"vs {delta['ref_date']}"
        print(f"[OK] delta calculé ({lbl}) : déposés {delta['deposees_n']:+d} dossiers / "
              f"{delta['deposees_led']:+d} LED · taux pose {delta['taux_pose']:+d}pt · "
              f"modifs audit {delta['modif_audit']:+d}")
    print(f"[OK] history/timeseries.json + index.json régénérés ({n} jours archivés)")


if __name__ == "__main__":
    main()
