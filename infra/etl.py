# -*- coding: utf-8 -*-
"""
ETL Cockpit LED — Pixel CRM CSV -> Postgres
Lit le(s) export(s) CSV déposés dans DATA_DIR, normalise, agrège par dossier,
et charge 2 tables dans Postgres : ligne_chantier (brut) + dossier (agrégé).
Robuste aux colonnes manquantes (statut / pose / responsable optionnels).

Usage :
    pip install -r requirements.txt
    export PG_URL=postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit
    python etl.py /chemin/vers/dossier_des_csv
"""
import sys, os, glob, re
import pandas as pd
from sqlalchemy import create_engine, text

PG_URL = os.environ.get("PG_URL", "postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATA_DIR", "../data")
PATTERN = os.environ.get("CSV_GLOB", "*.csv")

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
    # pose terminée = au moins une date de fin de pose / travaux
    fin = None
    for c in ["date_fin_pose","date_fin_travaux"]:
        if c in dossier: fin = dossier[c] if fin is None else fin.fillna(dossier[c])
    dossier["pose_terminee"] = fin.notna() if fin is not None else None

    eng = create_engine(PG_URL)
    with eng.begin() as cx:
        raw.to_sql("ligne_chantier", cx, if_exists="replace", index=False)
        dossier.to_sql("dossier", cx, if_exists="replace", index=False)
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_dossier_num ON dossier(num_dossier)"))
    print("OK -> Postgres : %d lignes, %d dossiers (%d signés, LED signées=%s)" % (
        len(raw), len(dossier), int(dossier["signe"].sum()),
        int(dossier.loc[dossier["signe"],"led"].sum()) if "led" in dossier else "?"))

if __name__ == "__main__":
    main()
