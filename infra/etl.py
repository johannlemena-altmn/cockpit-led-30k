# -*- coding: utf-8 -*-
"""
ETL Cockpit LED — Pixel CRM CSV + BETOOL Excel -> Postgres
Lit le(s) export(s) CSV déposés dans DATA_DIR, normalise, agrège par dossier,
et charge 2 tables dans Postgres : ligne_chantier (brut) + dossier (agrégé).
Avec --betool <fichier.xlsx> : charge aussi betool_lead (pipeline BETOOL).
Robuste aux colonnes manquantes (statut / pose / responsable optionnels).

Usage :
    pip install -r requirements.txt
    export PG_URL=postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit
    python etl.py /chemin/vers/dossier_des_csv
    python etl.py /chemin/vers/dossier_des_csv --betool /chemin/betool.xlsx
"""
from __future__ import annotations
import sys, os, glob
import pandas as pd
from sqlalchemy import create_engine, text

PG_URL = os.environ.get("PG_URL", "postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit")
PATTERN = os.environ.get("CSV_GLOB", "*.csv")

# Parse args
_args = sys.argv[1:]
BETOOL_PATH: str | None = None
_positional = []
_i = 0
while _i < len(_args):
    if _args[_i] == "--betool" and _i + 1 < len(_args):
        BETOOL_PATH = _args[_i + 1]; _i += 2
    else:
        _positional.append(_args[_i]); _i += 1
DATA_DIR = _positional[0] if _positional else os.environ.get("DATA_DIR", "../data")

# Pixel (libellé export) -> colonne normalisée
COLMAP = {
    "Numéro de dossier": "num_dossier", "Numero de dossier": "num_dossier",
    "Operation CEE": "operation", "Opération CEE": "operation",
    "Raison Sociale": "client", "Raison sociale": "client",
    "Produit Qté": "led", "Produit Qte": "led",
    "Prime CEE opération": "prime", "Prime CEE operation": "prime", "Montant Prime CEE": "prime",
    "Cumac Opération": "cumac", "Cumac Operation": "cumac", "Kwh cumac": "cumac",
    "Secteur d'activité": "secteur", "Secteur d'activite": "secteur",
    "Date signature devis": "date_signature",
    "Statut": "statut", "Catégorie de statuts": "categorie_statut", "Date statut": "date_statut",
    "Numéro dépôt dossier": "num_depot", "Numero depot dossier": "num_depot",
    "Date dépôt dossier": "date_depot", "Date depot dossier": "date_depot",
    "Poseur": "poseur", "Administrateur": "administrateur", "Confirmateur": "confirmateur",
    "Date début pose": "date_debut_pose", "Date fin pose": "date_fin_pose", "Date pose": "date_pose",
    "Date fin travaux": "date_fin_travaux",
    "Ville chantier": "ville", "Code postal chantier": "cp",
}
DATE_COLS = ["date_signature","date_statut","date_depot","date_debut_pose",
             "date_fin_pose","date_pose","date_fin_travaux"]
NUM_COLS  = ["led","prime","cumac"]

def read_csv(path):
    for enc in ("latin-1","utf-8"):
        try:
            return pd.read_csv(path, sep=";", encoding=enc, dtype=str, keep_default_na=False)
        except Exception:
            continue
    raise RuntimeError("Lecture impossible : " + path)

def to_num(s):
    s = (s or "").strip().replace("\xa0","").replace(" ","").replace(",",".")
    try: return float(s) if s else None
    except: return None

# ---------------------------------------------------------------------------
# BETOOL pipeline stages (mirrors betool_summary.py)
# ---------------------------------------------------------------------------
_BETOOL_STAGES = [
    {"id": "en_cours",            "statuts": ["Installation en cours", "installation en cours EXPRESS", "Installation en Interne"]},
    {"id": "attente_audit",       "statuts": ["Installation Fini - En attente doc et audit", "Installation fini en Interne"]},
    {"id": "attente_signature",   "statuts": ["Installation fini - En attente signature doc"]},
    {"id": "modif_audit",         "statuts": ["Installation Fini - Doc ok - Modif Audit"]},
    {"id": "depose",              "statuts": ["Déposé"]},
]
_BETOOL_MAP = {st: s["id"] for s in _BETOOL_STAGES for st in s["statuts"]}


def load_betool_xlsx(path: str) -> pd.DataFrame | None:
    """Read BETOOL Excel -> DataFrame(raw_statut, stage_id, led, update_time, age_days)."""
    try:
        import openpyxl
    except ImportError:
        print("[ERREUR] openpyxl manquant : pip install openpyxl"); return None
    from datetime import date, datetime
    today = date.today()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h) if h is not None else "" for h in rows[0]]
    records = []
    for row in rows[1:]:
        rec = dict(zip(headers, row))
        statut = rec.get("Statut") or ""
        stage_id = _BETOOL_MAP.get(statut)
        if stage_id is None:
            continue
        raw_led = rec.get("Nombre de points lumineux ?")
        try:
            led = int(float(str(raw_led))) if raw_led not in (None, "") else 0
        except (ValueError, TypeError):
            led = 0
        upd = rec.get("Last updateTime")
        age_days = None
        update_time = None
        if upd:
            try:
                d = upd.date() if hasattr(upd, "date") else datetime.strptime(str(upd)[:10], "%Y-%m-%d").date()
                age_days = (today - d).days
                update_time = d
            except Exception:
                pass
        records.append({"raw_statut": statut, "stage_id": stage_id, "led": led,
                        "update_time": update_time, "age_days": age_days})
    return pd.DataFrame(records)


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, PATTERN)))
    if not files:
        print("Aucun CSV dans", DATA_DIR); sys.exit(1)
    frames = []
    for f in files:
        df = read_csv(f)
        df = df.rename(columns={k:v for k,v in COLMAP.items() if k in df.columns})
        df = df[[c for c in df.columns if c in COLMAP.values()]]
        if "num_dossier" not in df.columns:
            print("  (ignoré, pas de num_dossier):", os.path.basename(f)); continue
        df["_src"] = os.path.basename(f)
        frames.append(df); print("  +", os.path.basename(f), len(df), "lignes")
    if not frames:
        print("Aucun fichier exploitable."); sys.exit(1)
    raw = pd.concat(frames, ignore_index=True)

    for c in NUM_COLS:
        if c in raw: raw[c] = raw[c].map(to_num)
    for c in DATE_COLS:
        if c in raw: raw[c] = pd.to_datetime(raw[c], dayfirst=True, errors="coerce")
    raw["signe"] = raw["date_signature"].notna() if "date_signature" in raw else False
    if "num_depot" in raw: raw["depose"] = raw["num_depot"].astype(str).str.strip().replace("nan","").ne("")
    else: raw["depose"] = False

    # agrégat par dossier
    g = raw.groupby("num_dossier", as_index=False)
    agg = {}
    if "led" in raw: agg["led"]=("led","sum")
    if "prime" in raw: agg["prime"]=("prime","sum")
    if "cumac" in raw: agg["cumac"]=("cumac","sum")
    for col in ["client","secteur","statut","categorie_statut","poseur","administrateur",
                "confirmateur","ville","cp","num_depot","operation"]:
        if col in raw: agg[col]=(col,"first")
    for col in ["date_signature","date_statut","date_depot","date_fin_pose","date_fin_travaux"]:
        if col in raw: agg[col]=(col,"max")
    agg["signe"]=("signe","max"); agg["depose"]=("depose","max"); agg["nb_lignes"]=("num_dossier","size")
    dossier = g.agg(**agg)
    # pose terminée = au moins une date de fin de pose / travaux (boolean, omis si absent)
    fin = None
    for c in ["date_fin_pose","date_fin_travaux"]:
        if c in dossier: fin = dossier[c] if fin is None else fin.fillna(dossier[c])
    if fin is not None:
        dossier["pose_terminee"] = fin.notna()

    eng = create_engine(PG_URL)
    # DROP CASCADE pour libérer les vues dépendantes avant rechargement
    with eng.begin() as cx:
        cx.execute(text("DROP TABLE IF EXISTS ligne_chantier CASCADE"))
        cx.execute(text("DROP TABLE IF EXISTS dossier CASCADE"))
    with eng.begin() as cx:
        raw.to_sql("ligne_chantier", cx, if_exists="replace", index=False)
        dossier.to_sql("dossier", cx, if_exists="replace", index=False)
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_dossier_num ON dossier(num_dossier)"))

    # BETOOL
    if BETOOL_PATH:
        print(f"Chargement BETOOL : {BETOOL_PATH}")
        df_bt = load_betool_xlsx(BETOOL_PATH)
        if df_bt is not None and not df_bt.empty:
            with eng.begin() as cx:
                df_bt.to_sql("betool_lead", cx, if_exists="replace", index=False)
                cx.execute(text("CREATE INDEX IF NOT EXISTS idx_bt_stage ON betool_lead(stage_id)"))
            print(f"  betool_lead : {len(df_bt)} lignes chargées")
        else:
            print("  (aucune ligne BETOOL reconnue)")

    # Appliquer les vues SQL — psycopg2 direct pour gérer les DO $$ blocks
    SQL_VIEWS = os.path.join(os.path.dirname(__file__), "sql", "views.sql")
    if os.path.exists(SQL_VIEWS):
        with open(SQL_VIEWS, encoding="utf-8") as f:
            sql = f.read()
        raw_conn = eng.raw_connection()
        try:
            with raw_conn.cursor() as cur:
                cur.execute(sql)
            raw_conn.commit()
            print("Vues SQL appliquées.")
        except Exception as e:
            raw_conn.rollback()
            print(f"  (erreur vues SQL) {e}")
        finally:
            raw_conn.close()

    nb_signes = int(dossier["signe"].sum())
    led_signees = int(dossier.loc[dossier["signe"], "led"].sum()) if "led" in dossier else "?"
    msg = "OK -> Postgres : %d lignes, %d dossiers (%d signés, LED signées=%s)" % (
        len(raw), len(dossier), nb_signes, led_signees)
    if "pose_terminee" in dossier and dossier["pose_terminee"].notna().any():
        signes_non_deposes = dossier[dossier["signe"] & ~dossier["depose"]]
        if len(signes_non_deposes) > 0:
            taux = 100.0 * signes_non_deposes["pose_terminee"].sum() / len(signes_non_deposes)
            msg += " | taux pose=%.1f%% (%d/%d)" % (taux, int(signes_non_deposes["pose_terminee"].sum()), len(signes_non_deposes))
    print(msg)

if __name__ == "__main__":
    main()
