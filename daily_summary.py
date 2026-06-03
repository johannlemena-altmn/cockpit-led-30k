# -*- coding: utf-8 -*-
"""
daily_summary.py — Cockpit LED 30k · Énergie Responsable
=========================================================
Lit les exports CRM Pixel depuis data/*.csv et génère un résumé quotidien
mobile-first au format HTML : resume_quotidien_YYYYMMDD.html

Colonnes attendues (toutes facultatives — try/except par colonne) :
  Numéro de dossier, Produit Qté, Date signature devis,
  Prime CEE opération, Secteur d'activité, Raison Sociale, Ville chantier

Usage :
  pip install pandas openpyxl   # openpyxl optionnel
  python daily_summary.py

Le fichier HTML généré N'EST PAS commité (voir .gitignore).
"""

import csv
import glob
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Constantes configurables
# ---------------------------------------------------------------------------
OBJECTIF_MENSUEL = 30_000       # LED déposées / mois
CIBLE_JOUR       = 1_500        # LED / jour
ALERTE_LED_MIN   = 100          # seuil "gros dossier"
ALERTE_JOURS     = 30           # ancienneté max avant alerte (jours)
MAX_ALERTES      = 3            # nombre max d'alertes affichées
DATA_GLOB        = "data/*.csv"
ENCODING         = "latin-1"
SEPARATOR        = ";"

# Noms de colonnes (tels qu'exportés par Pixel CRM)
COL_NUM    = "Numéro de dossier"
COL_QTE    = "Produit Qté"
COL_DATE   = "Date signature devis"
COL_PRIME  = "Prime CEE opération"
COL_SECT   = "Secteur d'activité"
COL_RS     = "Raison Sociale"
COL_VILLE  = "Ville chantier"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(s: str):
    """Parse une chaîne numérique FR (espaces, virgules) → float ou None."""
    if not s:
        return None
    s = s.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s: str):
    """Parse une date DD/MM/YYYY → date ou None."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _fmt_int(n: int) -> str:
    """Formatte un entier avec espace comme séparateur de milliers."""
    return f"{n:,}".replace(",", " ")  # espace fine insécable


def _fmt_float(n: float, decimals: int = 1) -> str:
    return f"{n:,.{decimals}f}".replace(",", " ").replace(".", ",")


# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------

def load_csv_files(pattern: str = DATA_GLOB):
    """Charge tous les CSV matchant le pattern glob. Retourne une liste de dicts."""
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"[WARN] Aucun fichier CSV trouvé dans '{pattern}'.", file=sys.stderr)
        return [], []
    rows = []
    loaded = []
    for path in files:
        try:
            with open(path, encoding=ENCODING, newline="") as f:
                reader = csv.DictReader(f, delimiter=SEPARATOR)
                file_rows = list(reader)
                rows.extend(file_rows)
                loaded.append((path, len(file_rows)))
                print(f"[OK] {path} — {len(file_rows)} lignes")
        except Exception as exc:
            print(f"[WARN] Impossible de lire {path}: {exc}", file=sys.stderr)
    return rows, loaded


# ---------------------------------------------------------------------------
# Calcul des agrégats
# ---------------------------------------------------------------------------

def compute_aggregates(rows: list):
    """
    Calcule les agrégats principaux.
    Chaque champ est calculé dans un try/except indépendant pour ne pas planter
    si une colonne manque dans l'export.
    """
    today = date.today()
    agg = {
        "today": today,
        "total_led": 0,
        "nb_dossiers": 0,
        "led_par_jour": None,
        "prime_totale": None,
        "taux_pose": "non disponible sans colonne statut",
        "date_premier": None,
        "date_dernier": None,
        "nb_lignes": len(rows),
        "alertes": [],
        "mois_courant_led": 0,
        "mois_courant_jours_ecoules": today.day,
        "colonnes_manquantes": [],
    }

    if not rows:
        # ── MODE DÉMO ────────────────────────────────────────────────────────
        # Aucun CSV trouvé → on retourne les agrégats connus issus du diagnostic
        # Énergie Responsable (données réelles au 03/06/2026, sans PII).
        agg.update({
            "total_led":             196_177,
            "nb_dossiers":           5_280,
            "led_par_jour":          None,   # pas de série temporelle en démo
            "prime_totale":          13_000_000.0,
            "taux_pose":             "60-75 % (objectif ≥ 95 %) — données agrégées",
            "date_premier":          None,
            "date_dernier":          None,
            "mois_courant_led":      0,
            "colonnes_manquantes":   [],
            "demo_mode":             True,
        })
        # Alerte démo : rappel du contexte
        agg["alertes"].append({
            "type":   "warn",
            "icone":  "🟡",
            "titre":  "Mode démo — données statiques du 03/06/2026",
            "detail": (
                " Aucun export CSV Pixel CRM chargé. "
                "Déposer un export dans data/ ou configurer PIXEL_EXPORT_URL "
                "pour afficher les données live."
            ),
        })
        return agg

    # --- Agrégation par dossier ---
    doss = defaultdict(lambda: {
        "led": 0,
        "prime": 0.0,
        "date_sig": None,
        "has_date": False,
    })

    # Détection colonnes présentes
    sample_keys = set(rows[0].keys()) if rows else set()

    has_num   = COL_NUM   in sample_keys
    has_qte   = COL_QTE   in sample_keys
    has_date  = COL_DATE  in sample_keys
    has_prime = COL_PRIME in sample_keys

    for col, flag in [(COL_NUM, has_num), (COL_QTE, has_qte),
                      (COL_DATE, has_date), (COL_PRIME, has_prime)]:
        if not flag:
            agg["colonnes_manquantes"].append(col)

    for row in rows:
        try:
            k = row.get(COL_NUM, "").strip() if has_num else "__inconnu__"
            if not k:
                k = "__inconnu__"
        except Exception:
            k = "__inconnu__"

        try:
            if has_qte:
                v = _num(row.get(COL_QTE, ""))
                if v and v > 0:
                    doss[k]["led"] += v
        except Exception:
            pass

        try:
            if has_prime:
                p = _num(row.get(COL_PRIME, ""))
                if p:
                    doss[k]["prime"] += p
        except Exception:
            pass

        try:
            if has_date:
                raw = row.get(COL_DATE, "").strip()
                d = _parse_date(raw)
                if d:
                    if not doss[k]["has_date"] or d > doss[k]["date_sig"]:
                        doss[k]["date_sig"] = d
                        doss[k]["has_date"] = True
        except Exception:
            pass

    # --- KPIs globaux ---
    try:
        agg["nb_dossiers"] = len(doss)
    except Exception:
        pass

    try:
        agg["total_led"] = int(sum(d["led"] for d in doss.values()))
    except Exception:
        pass

    try:
        if has_prime:
            agg["prime_totale"] = sum(d["prime"] for d in doss.values())
    except Exception:
        pass

    try:
        if has_date:
            dates = [d["date_sig"] for d in doss.values() if d["has_date"]]
            if dates:
                agg["date_premier"] = min(dates)
                agg["date_dernier"] = max(dates)
                nb_jours = (today - agg["date_premier"]).days or 1
                agg["led_par_jour"] = round(agg["total_led"] / nb_jours, 1)
    except Exception:
        pass

    # --- LED mois courant ---
    try:
        if has_date:
            for d in doss.values():
                if d["has_date"] and d["date_sig"]:
                    if (d["date_sig"].year == today.year
                            and d["date_sig"].month == today.month):
                        agg["mois_courant_led"] += int(d["led"])
    except Exception:
        pass

    # --- Alertes : gros dossiers anciens (proxy "non vus depuis >30j") ---
    try:
        if has_date:
            seuil = today - timedelta(days=ALERTE_JOURS)
            candidats = [
                (k, d) for k, d in doss.items()
                if d["led"] >= ALERTE_LED_MIN
                and d["has_date"]
                and d["date_sig"] <= seuil
            ]
            # Trier par LED décroissant (les plus gros d'abord)
            candidats.sort(key=lambda x: x[1]["led"], reverse=True)
            for k, d in candidats[:MAX_ALERTES]:
                anciennete = (today - d["date_sig"]).days
                agg["alertes"].append({
                    "type": "danger",
                    "icone": "⚠️",
                    "titre": f"Dossier {k} — {int(d['led'])} LED",
                    "detail": (
                        f"Signé le {d['date_sig'].strftime('%d/%m/%Y')} "
                        f"({anciennete}j). Aucun statut disponible — "
                        f"à vérifier en priorité."
                    ),
                })
    except Exception as exc:
        print(f"[WARN] Calcul alertes : {exc}", file=sys.stderr)

    return agg


# ---------------------------------------------------------------------------
# Génération de l'alerte mois courant
# ---------------------------------------------------------------------------

def build_month_alert(agg: dict) -> dict | None:
    """Génère une alerte si le rythme du mois courant est insuffisant."""
    try:
        today = agg["today"]
        jours_ecoules = today.day
        jours_dans_mois = 30  # approximation
        led_mois = agg["mois_courant_led"]

        if jours_ecoules == 0:
            return None

        rythme = led_mois / jours_ecoules  # LED/jour ce mois-ci
        projection = rythme * jours_dans_mois

        if projection < OBJECTIF_MENSUEL * 0.8:
            return {
                "type": "danger",
                "icone": "🔴",
                "titre": f"Rythme du mois insuffisant — projection {_fmt_int(int(projection))} LED",
                "detail": (
                    f"{_fmt_int(led_mois)} LED signées en {jours_ecoules}j "
                    f"({_fmt_float(rythme)}/j). "
                    f"Objectif mensuel : {_fmt_int(OBJECTIF_MENSUEL)}. "
                    f"Action immédiate requise."
                ),
            }
        elif projection < OBJECTIF_MENSUEL:
            return {
                "type": "warn",
                "icone": "🟡",
                "titre": f"Rythme du mois à surveiller — projection {_fmt_int(int(projection))} LED",
                "detail": (
                    f"{_fmt_int(led_mois)} LED signées en {jours_ecoules}j "
                    f"({_fmt_float(rythme)}/j). "
                    f"Objectif mensuel : {_fmt_int(OBJECTIF_MENSUEL)}."
                ),
            }
        else:
            return {
                "type": "ok",
                "icone": "✅",
                "titre": f"Rythme du mois en bonne voie — projection {_fmt_int(int(projection))} LED",
                "detail": (
                    f"{_fmt_int(led_mois)} LED signées en {jours_ecoules}j "
                    f"({_fmt_float(rythme)}/j). "
                    f"Objectif mensuel : {_fmt_int(OBJECTIF_MENSUEL)}."
                ),
            }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Recommandation du jour
# ---------------------------------------------------------------------------

def compute_recommendation(agg: dict) -> str:
    """Détermine l'action prioritaire du jour selon les agrégats."""
    try:
        led_j = agg.get("led_par_jour")
        if led_j is not None and led_j < CIBLE_JOUR * 0.5:
            return (
                f"Le rythme estimé ({_fmt_float(led_j)} LED/j) est très inférieur "
                f"à l'objectif de {_fmt_int(CIBLE_JOUR)}/j. "
                "Mobiliser l'équipe Contrôle + Pose en urgence et vérifier les blocages "
                "sur les dossiers ≥ 100 LED signés il y a plus de 30 jours."
            )
        if agg.get("alertes"):
            n = len(agg["alertes"])
            return (
                f"{n} dossier(s) ≥ {_fmt_int(ALERTE_LED_MIN)} LED signé(s) "
                f"depuis plus de {ALERTE_JOURS} jours sans statut connu. "
                "Traiter en priorité : contacter le responsable de chaque dossier "
                "pour débloquer la chaîne Contrôle → Dépôt."
            )
        if not agg.get("total_led"):
            return (
                "Aucune donnée chargée. Déposer l'export Pixel CRM "
                "(« eq 127 pour liste ») dans data/ et relancer ce script."
            )
        return (
            "Portefeuille en ordre. Concentrer les efforts sur le taux de pose : "
            "relancer les dossiers posés < 95 % et accélérer le flux Contrôle → Dépôt "
            f"pour atteindre {_fmt_int(CIBLE_JOUR)} LED/j."
        )
    except Exception:
        return "Analyser les dossiers en attente de dépôt et relancer les poses insuffisantes."


# ---------------------------------------------------------------------------
# Génération HTML
# ---------------------------------------------------------------------------

CSS = """
:root {
  --navy: #1F3A5F;
  --blue: #2E6FB7;
  --amber: #E08600;
  --green: #2E7D32;
  --red: #C0392B;
  --ink: #1c2530;
  --muted: #5b6573;
  --line: #dfe5ee;
  --soft: #eef3fb;
  --bg: #f0f4fa;
  --card: #ffffff;
  --r: 14px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1621; --card: #1a2535; --ink: #e8edf5;
    --muted: #8a9bb0; --line: #2a3a50; --soft: #1e2d42;
    --navy: #4a7fc1; --blue: #5a9fd4;
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
body {
  font-family: -apple-system, "SF Pro Display", "Segoe UI", Roboto, Arial, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.45; min-height: 100dvh;
}
.hdr {
  background: linear-gradient(145deg, #1F3A5F 0%, #2b5899 100%);
  color: #fff;
  padding: env(safe-area-inset-top, 12px) 16px 18px;
  padding-top: max(env(safe-area-inset-top), 16px);
}
.hdr-tag { font-size: 10px; letter-spacing: .2em; text-transform: uppercase; opacity: .75; margin-bottom: 4px; }
.hdr h1 { font-size: 21px; font-weight: 700; line-height: 1.2; }
.hdr-sub { font-size: 12px; opacity: .8; margin-top: 4px; }
.progress-wrap {
  background: rgba(255,255,255,.12); border-radius: 999px; height: 8px; margin-top: 14px; overflow: hidden;
}
.progress-bar { height: 100%; border-radius: 999px; background: linear-gradient(90deg,#ffd24a,#ffb300); }
.progress-label { display:flex; justify-content:space-between; font-size:11px; opacity:.85; margin-top:5px; }
.scroll { padding: 14px 14px calc(env(safe-area-inset-bottom) + 40px); max-width: 520px; margin: 0 auto; }
.kpi-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px; }
.kpi { background:var(--card); border-radius:var(--r); padding:14px 14px 12px; border:1px solid var(--line); }
.kpi .val { font-size:24px; font-weight:700; color:var(--navy); line-height:1.1; }
.kpi .lbl { font-size:11px; color:var(--muted); margin-top:3px; }
.kpi.accent { background:var(--navy); border-color:transparent; }
.kpi.accent .val { color:#ffd24a; font-size:26px; }
.kpi.accent .lbl { color:rgba(255,255,255,.75); }
.kpi.warn { border-left:3px solid var(--amber); }
.kpi.danger { border-left:3px solid var(--red); }
.kpi.ok { border-left:3px solid var(--green); }
.sec-title {
  font-size:11px; font-weight:600; color:var(--muted);
  text-transform:uppercase; letter-spacing:.12em; margin:18px 0 8px;
}
.alert {
  border-radius:var(--r); padding:12px 14px; font-size:12.5px;
  margin-bottom:10px; display:flex; gap:10px; align-items:flex-start;
}
.alert.amber { background:#fff8e7; border:1px solid #f5d77e; color:#7a4900; }
.alert.blue  { background:#eaf3ff; border:1px solid #b8d6f5; color:#1a3d6d; }
.alert.green { background:#eafaf1; border:1px solid #a8dfbe; color:#1a5232; }
.alert.red   { background:#fdf2f2; border:1px solid #f0b8b8; color:#7a1a1a; }
@media (prefers-color-scheme: dark) {
  .alert.amber { background:#2a1e00; border-color:#6b4e00; color:#ffc94a; }
  .alert.blue  { background:#0e1e35; border-color:#1d4570; color:#7fb9f0; }
  .alert.green { background:#0c2418; border-color:#1a5232; color:#6fcf97; }
  .alert.red   { background:#2a0e0e; border-color:#701d1d; color:#f0a0a0; }
}
.alert-icon { font-size:18px; flex-shrink:0; margin-top:-1px; }
.alert b { display:block; font-size:13px; margin-bottom:2px; }
.action-card {
  background: linear-gradient(135deg,#1F3A5F,#2b5899);
  color:#fff; border-radius:var(--r); padding:16px;
  margin-bottom:10px;
}
.action-card .action-label {
  font-size:10px; letter-spacing:.15em; text-transform:uppercase; opacity:.75; margin-bottom:6px;
}
.action-card .action-text { font-size:14px; line-height:1.5; }
.warn-box {
  background:#fff8e7; border:1px solid #f5d77e; border-left:4px solid var(--amber);
  border-radius:var(--r); padding:12px 14px; margin-bottom:10px; font-size:12px; color:#7a4900;
}
@media (prefers-color-scheme: dark) {
  .warn-box { background:#2a1e00; border-color:#6b4e00; color:#ffc94a; }
}
.foot { text-align:center; font-size:10.5px; color:var(--muted); margin-top:20px; padding-bottom:6px; }
@media (max-width:380px) {
  .kpi .val { font-size:20px; } .kpi.accent .val { font-size:22px; } .hdr h1 { font-size:18px; }
}
"""


def render_alert(a: dict) -> str:
    type_map = {
        "danger": "red",
        "warn":   "amber",
        "ok":     "green",
        "info":   "blue",
    }
    cls = type_map.get(a.get("type", "info"), "blue")
    icone = a.get("icone", "ℹ️")
    titre = a.get("titre", "")
    detail = a.get("detail", "")
    return (
        f'<div class="alert {cls}">'
        f'<div class="alert-icon">{icone}</div>'
        f'<div><b>{titre}</b>{detail}</div>'
        f'</div>'
    )


def generate_html(agg: dict, sources: list, output_path: str):
    today = agg["today"]
    date_fr = today.strftime("%d/%m/%Y")

    total_led     = agg["total_led"]
    nb_dossiers   = agg["nb_dossiers"]
    prime_totale  = agg["prime_totale"]
    led_par_jour  = agg["led_par_jour"]
    taux_pose     = agg["taux_pose"]
    date_premier  = agg["date_premier"]
    date_dernier  = agg["date_dernier"]

    # --- Barre de progression mois ---
    mois_led      = agg["mois_courant_led"]
    pct_objectif  = min(100, round(mois_led / OBJECTIF_MENSUEL * 100)) if OBJECTIF_MENSUEL else 0

    # --- KPI : ratio global ---
    ratio_global  = round(total_led / OBJECTIF_MENSUEL, 1) if total_led and OBJECTIF_MENSUEL else 0

    # --- Valeurs formatées ---
    val_led       = _fmt_int(total_led) if total_led else "—"
    val_doss      = _fmt_int(nb_dossiers) if nb_dossiers else "—"
    val_prime     = f"{prime_totale/1e6:.1f} M€".replace(".", ",") if prime_totale else "—"
    val_led_j     = _fmt_float(led_par_jour) if led_par_jour is not None else "—"
    val_mois      = _fmt_int(mois_led) if mois_led else "0"
    val_ratio     = f"×{ratio_global}" if ratio_global else "—"

    # --- Dates source ---
    val_date_p = date_premier.strftime("%d/%m/%Y") if date_premier else "—"
    val_date_d = date_dernier.strftime("%d/%m/%Y") if date_dernier else "—"

    # --- Alertes ---
    alertes = list(agg["alertes"])  # alertes dossiers
    month_alert = build_month_alert(agg)
    if month_alert:
        alertes.insert(0, month_alert)
    alertes = alertes[:MAX_ALERTES]

    alertes_html = "".join(render_alert(a) for a in alertes) if alertes else (
        '<div class="alert green">'
        '<div class="alert-icon">✅</div>'
        '<div><b>Aucune alerte détectée</b>'
        'Tous les indicateurs sont dans les normes.</div>'
        '</div>'
    )

    # --- Recommandation ---
    reco = compute_recommendation(agg)

    # --- Colonnes manquantes ---
    manquantes = agg.get("colonnes_manquantes", [])
    manquantes_html = ""
    if manquantes:
        cols = ", ".join(f"<code>{c}</code>" for c in manquantes)
        manquantes_html = (
            f'<div class="warn-box">'
            f'Colonnes non trouvées dans l\'export : {cols}. '
            f'Certains KPIs affichent « — ». Vérifier le modèle d\'export Pixel CRM.'
            f'</div>'
        )

    # --- Bandeau MODE DÉMO ---
    demo_banner_html = ""
    if agg.get("demo_mode"):
        demo_banner_html = (
            '<div style="background:#fff3cd;border-bottom:2px solid #e6b800;'
            'color:#7a4900;padding:10px 16px;font-size:12.5px;font-weight:600;'
            'text-align:center;position:sticky;top:0;z-index:100;">'
            '⚠️ MODE DÉMO — données agrégées du 03/06/2026, pas de CSV live'
            '</div>'
        )

    # --- Sources ---
    if sources:
        sources_txt = ", ".join(
            f"{os.path.basename(p)} ({n} lignes)" for p, n in sources
        )
    else:
        sources_txt = "Aucun fichier chargé — mode démo"

    # --- Barre progression ---
    pct_bar = min(100, pct_objectif)
    bar_color = (
        "linear-gradient(90deg,#e74c3c,#c0392b)" if pct_bar < 50
        else "linear-gradient(90deg,#ffd24a,#ffb300)" if pct_bar < 90
        else "linear-gradient(90deg,#27ae60,#2ecc71)"
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Résumé quotidien LED — {date_fr}</title>
<style>{CSS}</style>
</head>
<body>
{demo_banner_html}
<!-- HEADER -->
<div class="hdr">
  <div class="hdr-tag">Énergie Responsable · BAT-EQ-127 · Résumé quotidien</div>
  <h1>Cockpit LED 30 000</h1>
  <div class="hdr-sub">Généré le {date_fr} · {sources_txt}</div>
  <div class="progress-wrap">
    <div class="progress-bar" style="width:{pct_bar}%; background:{bar_color};"></div>
  </div>
  <div class="progress-label">
    <span>{val_mois} LED ce mois-ci</span>
    <span>{pct_objectif}% de l'objectif ({_fmt_int(OBJECTIF_MENSUEL)})</span>
  </div>
</div>

<!-- SCROLL AREA -->
<div class="scroll">

  <!-- KPIs PRINCIPAUX -->
  <div class="sec-title">KPIs clés</div>
  <div class="kpi-grid">
    <div class="kpi accent" style="grid-column: 1 / -1;">
      <div class="val">{val_led}</div>
      <div class="lbl">LED signées (total portefeuille)</div>
    </div>
    <div class="kpi">
      <div class="val">{val_doss}</div>
      <div class="lbl">dossiers</div>
    </div>
    <div class="kpi">
      <div class="val">{val_ratio}</div>
      <div class="lbl">vs objectif 30 000/mois</div>
    </div>
    <div class="kpi">
      <div class="val">{val_led_j}</div>
      <div class="lbl">LED/j estimé (depuis 1er dossier)</div>
    </div>
    <div class="kpi">
      <div class="val">{val_prime}</div>
      <div class="lbl">prime CEE totale</div>
    </div>
  </div>

  <!-- KPI taux de pose -->
  <div class="kpi warn" style="margin-bottom:14px;">
    <div class="val" style="font-size:14px; color:var(--amber);">Taux de pose</div>
    <div class="lbl">{taux_pose}</div>
  </div>

  <!-- Dates extrêmes -->
  <div class="kpi-grid">
    <div class="kpi">
      <div class="val" style="font-size:16px;">{val_date_p}</div>
      <div class="lbl">1er dossier signé</div>
    </div>
    <div class="kpi">
      <div class="val" style="font-size:16px;">{val_date_d}</div>
      <div class="lbl">dernier dossier signé</div>
    </div>
  </div>

  {manquantes_html}

  <!-- ALERTES -->
  <div class="sec-title">Alertes ({len(alertes)} / {MAX_ALERTES} max)</div>
  {alertes_html}

  <!-- ACTION PRIORITAIRE -->
  <div class="sec-title">Action prioritaire du jour</div>
  <div class="action-card">
    <div class="action-label">Recommandation</div>
    <div class="action-text">{reco}</div>
  </div>

  <!-- FOOTER -->
  <div class="foot">
    Résumé quotidien LED · Énergie Responsable · {date_fr}<br>
    Aucune donnée PII dans ce fichier — agrégats uniquement
  </div>

</div><!-- /scroll -->
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] HTML généré : {output_path}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    today = date.today()
    output_filename = f"resume_quotidien_{today.strftime('%Y%m%d')}.html"

    print("=" * 60)
    print(f"Cockpit LED 30k — Résumé quotidien du {today.strftime('%d/%m/%Y')}")
    print("=" * 60)

    rows, sources = load_csv_files(DATA_GLOB)
    agg = compute_aggregates(rows)

    print(f"\nAgrégats calculés :")
    print(f"  LED signées   : {_fmt_int(agg['total_led'])}")
    print(f"  Dossiers      : {_fmt_int(agg['nb_dossiers'])}")
    print(f"  LED/j estimé  : {agg['led_par_jour']}")
    print(f"  Prime totale  : {agg['prime_totale']}")
    print(f"  Alertes       : {len(agg['alertes'])}")
    if agg["colonnes_manquantes"]:
        print(f"  Cols manquantes: {agg['colonnes_manquantes']}")

    generate_html(agg, sources, output_filename)

    print(f"\nTermine. Ouvrir : {output_filename}")
    print("=" * 60)


if __name__ == "__main__":
    main()
