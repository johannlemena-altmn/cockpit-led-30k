# -*- coding: utf-8 -*-
"""
confirme_summary.py — Cockpit LED 30k
Lit la LISTE EQ 127 « CONFIRME » (fichier de dépôt CEE officiel, format admin)
et ajoute un bloc d'agrégats ANONYMISÉS dans public_data.json sous la clé
"confirmes". C'est la vue centrale de suivi (opérations confirmées au CEE).

SÉCURITÉ PII (règle absolue) : on ne stocke JAMAIS de nom client, SIREN,
adresse, téléphone ou email. Uniquement : comptes, sommes LED/prime, secteurs,
et les références internes ERS (ex: ERS-2025-1102-1) qui sont des identifiants
opérationnels non nominatifs servant à retrouver un dossier.

Usage :
    python confirme_summary.py "data/LISTE EQ 127 CONFIRME.csv"
    python confirme_summary.py liste.csv --ary "data/TABLEAU ARY.csv"
    python confirme_summary.py liste.csv --output public_data.json
"""
from __future__ import annotations
import csv, json, os, re, sys
from collections import Counter
from datetime import date

# ── Index des colonnes (LISTE CONFIRME, format CEE EMMY) ──────────────────────
# Les en-têtes contiennent des retours-ligne ; on indexe par position (stable).
COL_ID        = 0    # ID interne (numérique)
COL_CODEFICHE = 2    # BAT-EQ-127
COL_ERS       = 5    # REFERENCE interne de l'opération (ERS-2025-XXXX-N) — non-PII
COL_PRIME     = 7    # MONTANT de l'incitation financière (€)
COL_LED       = 36   # Nombre de luminaires de l'opération
COL_SECTEUR1  = 40   # Secteur concerné
COL_SECTEUR2  = 41   # Précision sur le secteur

# Colonnes PII à ne JAMAIS exporter (pour mémoire / scan défensif)
_PII_HINTS = ("nom", "prenom", "raison sociale", "siren", "siret",
              "adresse", "courriel", "email", "téléphone", "telephone", "ville")


def _num(s) -> float:
    if not s:
        return 0.0
    s = re.sub(r"[^\d,.-]", "", str(s)).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _read_csv(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        sample = fh.read(4000)
    sep = ";" if sample.count(";") > sample.count(",") else ","
    with open(path, encoding="utf-8", errors="replace") as fh:
        return list(csv.reader(fh, delimiter=sep))


# ── Normalisation secteur ─────────────────────────────────────────────────────
def _classify_secteur(s1: str, s2: str) -> str:
    blob = f"{s1} {s2}".lower()
    if "autre" in blob:
        return "autres"
    if "entrep" in blob or "santé" in blob or "sante" in blob or "commerce" in blob:
        return "entrepots"
    return "autres" if blob.strip() else "non_renseigne"


def compute_confirmes(rows: list[list[str]]) -> dict:
    data = rows[1:]
    led_total   = 0
    prime_total = 0.0
    ers_ok      = 0
    secteurs    = Counter()
    ers_sample  = []

    for r in data:
        if len(r) <= COL_LED:
            continue
        led_total   += int(_num(r[COL_LED]))
        prime_total += _num(r[COL_PRIME]) if len(r) > COL_PRIME else 0
        ref = r[COL_ERS].strip() if len(r) > COL_ERS else ""
        if ref.upper().startswith("ERS"):
            ers_ok += 1
            if len(ers_sample) < 8:
                ers_sample.append(ref)
        s1 = r[COL_SECTEUR1] if len(r) > COL_SECTEUR1 else ""
        s2 = r[COL_SECTEUR2] if len(r) > COL_SECTEUR2 else ""
        secteurs[_classify_secteur(s1, s2)] += 1

    n = len(data)
    return {
        "generated":        date.today().strftime("%Y-%m-%d"),
        "n":                n,
        "led":              led_total,
        "prime":            round(prime_total),
        "led_moy":          round(led_total / n, 1) if n else 0,
        "ers_coverage_pct": round(ers_ok / n * 100) if n else 0,
        "secteurs":         dict(secteurs),
        "ers_sample":       ers_sample,
    }


# ── TABLEAU ARY (autres secteurs) — optionnel ─────────────────────────────────
ARY_LED    = 2
ARY_MOTIF  = 6
ARY_PHOTOS = 7

def _norm_motif(m: str) -> str:
    m = m.lower().strip()
    if not m:
        return "non_renseigne"
    if "élevage" in m or "elevage" in m or "animaux" in m or "animau" in m:
        return "elevage_animaux"
    if "ouvert" in m:
        return "batiment_ouvert"
    if "15 ans" in m or "<15" in m or "ancien" in m:
        return "batiment_recent"
    return "autre_motif"


def compute_autres_secteurs(rows: list[list[str]]) -> dict:
    data = rows[1:]
    led_total = 0
    photos_ok = 0
    motifs    = Counter()
    for r in data:
        if len(r) <= ARY_LED:
            continue
        led_total += int(_num(r[ARY_LED]))
        if len(r) > ARY_PHOTOS and r[ARY_PHOTOS].strip().upper() in ("TRUE", "OUI", "VRAI", "1"):
            photos_ok += 1
        motif = r[ARY_MOTIF] if len(r) > ARY_MOTIF else ""
        motifs[_norm_motif(motif)] += 1
    n = len(data)
    return {
        "generated":         date.today().strftime("%Y-%m-%d"),
        "n":                 n,
        "led":               led_total,
        "photos_recues":     photos_ok,
        "photos_pct":        round(photos_ok / n * 100) if n else 0,
        "en_attente_photos": n - photos_ok,
        "motifs":            dict(motifs.most_common()),
    }


# ── Garde-fou PII : refuse d'écrire si une valeur ressemble à du PII ───────────
def _assert_no_pii(block: dict):
    blob = json.dumps(block, ensure_ascii=False)
    # SIRET/SIREN (9 ou 14 chiffres collés), email, téléphone FR
    for pat, label in [(r"\b\d{14}\b", "SIRET"),
                       (r"[\w.+-]+@[\w-]+\.[\w.-]+", "email"),
                       (r"\b0[1-9](?:[\s.-]?\d{2}){4}\b", "téléphone")]:
        if re.search(pat, blob):
            raise SystemExit(f"[STOP PII] {label} détecté dans l'agrégat — écriture annulée.")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    output = "public_data.json"
    ary_path = None
    if "--output" in sys.argv:
        i = sys.argv.index("--output")
        if i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
    if "--ary" in sys.argv:
        i = sys.argv.index("--ary")
        if i + 1 < len(sys.argv):
            ary_path = sys.argv[i + 1]

    if not args:
        print('Usage: python confirme_summary.py "data/LISTE EQ 127 CONFIRME.csv" '
              '[--ary "data/TABLEAU ARY.csv"] [--output public_data.json]', file=sys.stderr)
        sys.exit(1)

    liste_path = args[0]
    if not os.path.isfile(liste_path):
        print(f"[ERREUR] Fichier introuvable : {liste_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Lecture LISTE CONFIRME : {liste_path}")
    confirmes = compute_confirmes(_read_csv(liste_path))
    _assert_no_pii(confirmes)
    print(f"  {confirmes['n']:,} opérations · {confirmes['led']:,} LED · "
          f"{confirmes['prime']:,} € · réfs ERS {confirmes['ers_coverage_pct']}%".replace(",", " "))
    print(f"  Secteurs : {confirmes['secteurs']}")

    autres = None
    if ary_path:
        if os.path.isfile(ary_path):
            print(f"Lecture TABLEAU ARY : {ary_path}")
            autres = compute_autres_secteurs(_read_csv(ary_path))
            _assert_no_pii(autres)
            print(f"  {autres['n']:,} dossiers autres secteurs · {autres['led']:,} LED · "
                  f"photos {autres['photos_pct']}% ({autres['en_attente_photos']:,} à relancer)".replace(",", " "))
        else:
            print(f"[AVERTISSEMENT] TABLEAU ARY introuvable : {ary_path}")

    # Merge dans public_data.json
    data = {}
    if os.path.isfile(output):
        with open(output, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    data["confirmes"] = confirmes
    if autres:
        data["autres_secteurs"] = autres
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {output} enrichi avec le bloc 'confirmes'"
          + (" + 'autres_secteurs'" if autres else ""))


if __name__ == "__main__":
    main()
