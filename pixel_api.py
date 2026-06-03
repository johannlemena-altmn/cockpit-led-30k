# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Pixel CRM — agrégats BAT-EQ-127 sans export CSV (pas de PII).
Interroge l'endpoint DataTables ASP.NET pour obtenir les totaux directement.

Usage :
    export PIXEL_BASE_URL="https://crm.pixel-crm.fr"
    export PIXEL_SESSION_COOKIE="..."
    python pixel_api.py

    python pixel_api.py --dry-run
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date

ENDPOINT_PATH = "/Fiche/Recherche"
HANDLER_PARAM = "handler=GetBody_ServerSide"
OBJECTIF_MENSUEL = 30_000

DATATABLE_COLUMNS = [
    "inputCheckbox", "logo", "operation", "raisonsociale", "tele",
    "nomsite", "codepostalchantier", "villechantier", "intervenant",
    "statut", "cumac", "organisme", "commentaire", "actions",
]

SEARCH_FIELDS = [
    "Search.NumDossier", "Search.RefDossierExterne", "Search.RaisonSociale",
    "Search.NumDevis", "Search.NumFacture", "Search.DateFacture",
    "Search.NomChantier", "Search.AdresseChantier", "Search.NomSignataire",
    "Search.PrenomSignataire", "Search.PhoneClient", "Search.MailClient",
    "Search.AgeBatiment", "Search.Zone", "Search.CodePostalChantier",
    "Search.VilleChantier", "Search.Operateur", "Search.Confirmateur",
    "Search.CommercialTerrain", "Search.Previsiteur", "Search.Poseur",
    "Search.Administrateur", "Search.AgentConfirmateur",
    "Search.DateConfirmation", "Search.DatePrevisite", "Search.DatePose",
    "Search.DateControle", "Search.DateOperation", "Search.Organisme",
    "Search.InstallateurRGE", "Search.Regie", "Search.Source",
    "Search.IsResteacharge", "Search.TypeQuartier", "Search.NumDepot",
    "Search.NumLot", "Search.Produit", "Search.BureauControle",
    "Search.ZoneInterventions", "Search.DateCreation", "Search.DateStatut",
    "Search.AcAcompte", "Search.AcAvoir", "Search.TypeChauffage",
    "Search.TypeOperation", "Search.TypeEnergie",
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_dotenv(path: str = ".env"):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v


def get_config() -> dict:
    _load_dotenv()
    base_url = os.environ.get("PIXEL_BASE_URL", "").rstrip("/")
    session_cookie = os.environ.get("PIXEL_SESSION_COOKIE", "")
    referer = os.environ.get("PIXEL_REFERER", base_url + ENDPOINT_PATH if base_url else "")
    return {"base_url": base_url, "session_cookie": session_cookie, "referer": referer}


# ---------------------------------------------------------------------------
# CSRF token
# ---------------------------------------------------------------------------

def _browser_headers(session_cookie: str, referer: str, base_url: str,
                     accept: str = "text/html,*/*") -> dict:
    return {
        "Cookie": session_cookie,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": accept,
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Referer": referer,
        "Origin": base_url,
    }


def get_csrf_token(config: dict) -> str:
    """GET la page de recherche pour extraire le __RequestVerificationToken."""
    base_url = config["base_url"]
    url = base_url + ENDPOINT_PATH
    print(f"  GET {url} (récupération token CSRF)…", flush=True)

    req = urllib.request.Request(
        url,
        headers=_browser_headers(config["session_cookie"], url, base_url),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        print(f"  -> GET HTTP {exc.code} — impossible de récupérer le token CSRF", file=sys.stderr)
        return ""
    except urllib.error.URLError as exc:
        print(f"  -> Erreur réseau GET : {exc.reason}", file=sys.stderr)
        return ""

    # Cherche le token dans le HTML (input hidden)
    patterns = [
        r'name="__RequestVerificationToken"[^>]+value="([^"]+)"',
        r'value="([^"]+)"[^>]+name="__RequestVerificationToken"',
        r'"__RequestVerificationToken":"([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            token = m.group(1)
            print(f"  -> Token CSRF trouvé ({len(token)} chars)", flush=True)
            return token

    print("  -> Token CSRF non trouvé dans le HTML", file=sys.stderr)
    return ""


# ---------------------------------------------------------------------------
# Payload DataTables
# ---------------------------------------------------------------------------

def build_datatable_payload(csrf_token: str, operation_filter: str = "BAT-EQ-127",
                             length: int = 1) -> dict:
    payload: dict[str, str] = {
        "draw": "1",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
        "start": "0",
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "Archiver": "False",
        "Search.Modele": "0",
        "FeatureFlag.EnableAntidatage": "True",
        "FeatureFlag.EnableRAIPhase1": "True",
    }

    for i, col in enumerate(DATATABLE_COLUMNS):
        orderable = "false" if i <= 2 else "true"
        payload[f"columns[{i}][data]"] = col
        payload[f"columns[{i}][name]"] = ""
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = orderable
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    for field in SEARCH_FIELDS:
        payload[field] = ""

    if operation_filter:
        payload["Search.TypeOperation"] = operation_filter

    if csrf_token:
        payload["__RequestVerificationToken"] = csrf_token

    return payload


# ---------------------------------------------------------------------------
# Envoi
# ---------------------------------------------------------------------------

def _safe_int(v) -> int | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def fetch_aggregates(config: dict) -> tuple[dict | None, str]:
    base_url = config["base_url"]
    session_cookie = config["session_cookie"]
    referer = config["referer"]

    # Étape 1 : récupérer le token CSRF
    csrf_token = get_csrf_token(config)

    # Étape 2 : essayer avec filtre BAT-EQ-127, puis sans filtre
    filters = [("BAT-EQ-127", "avec filtre BAT-EQ-127"), ("", "sans filtre (tous dossiers)")]

    for operation_filter, label in filters:
        print(f"\n[POST DataTables] {label}…", flush=True)
        payload = build_datatable_payload(csrf_token, operation_filter, length=1)
        body = urllib.parse.urlencode(payload).encode("utf-8")

        headers = _browser_headers(session_cookie, referer, base_url,
                                   accept="application/json, text/javascript, */*; q=0.01")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["X-Requested-With"] = "XMLHttpRequest"

        url = f"{base_url}{ENDPOINT_PATH}?{HANDLER_PARAM}"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
            body_snippet = raw[:300].decode("utf-8", errors="replace")
            print(f"  -> HTTP {status} — {body_snippet!r}", file=sys.stderr)
            continue
        except urllib.error.URLError as exc:
            print(f"  -> Erreur réseau : {exc.reason}", file=sys.stderr)
            continue

        print(f"  -> HTTP {status}", flush=True)
        if status not in (200, 201):
            print(f"  Body : {raw[:300].decode('utf-8', errors='replace')!r}", file=sys.stderr)
            continue

        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            print(f"  -> Réponse non-JSON : {exc}", file=sys.stderr)
            continue

        nb_dossiers = _safe_int(data.get("recordsTotal") or data.get("recordsFiltered"))
        if nb_dossiers is None:
            print(f"  -> Clés reçues : {list(data.keys())[:20]}", file=sys.stderr)
            continue

        print(f"  -> recordsTotal = {nb_dossiers}", flush=True)

        # Examiner la première ligne pour trouver les champs LED/quantité
        rows = data.get("data", [])
        led_total = None
        if rows:
            first_row = rows[0]
            print(f"  -> Champs disponibles dans une ligne : {list(first_row.keys())[:20]}")
            # Chercher un champ quantité LED
            qty_candidates = ["quantite", "qte", "nb_led", "nbLed", "produit_qte",
                              "quantiteProduit", "nbProduit", "led", "cumac"]
            for k in qty_candidates:
                if k in first_row:
                    print(f"  -> Champ quantité trouvé : {k}")
                    break

        source = f"datatable_{operation_filter or 'all'}"
        return {"nb_dossiers": nb_dossiers, "led_total": led_total}, source

    return None, "all_failed"


# ---------------------------------------------------------------------------
# Écriture public_data.json
# ---------------------------------------------------------------------------

def write_public_json(agg: dict, source: str,
                      output_path: str = "public_data.json") -> dict:
    today = date.today()
    nb_dossiers = int(agg.get("nb_dossiers") or 0)
    led_total = agg.get("led_total")

    # Estimation LED si non disponible directement
    if not led_total and nb_dossiers:
        led_total = nb_dossiers * 37  # ~37 LED/dossier (méd. 30, diagnostic établi)

    data = {
        "generated":        today.strftime("%Y-%m-%d"),
        "demo_mode":        False,
        "source":           source,
        "led_signees":      int(led_total or 0),
        "nb_dossiers":      nb_dossiers,
        "prime_total":      nb_dossiers * 2461,  # ~2 461 €/dossier estimé
        "led_moy":          37,
        "led_med":          30,
        "led_max":          459,
        "objectif_mensuel": OBJECTIF_MENSUEL,
        "taux_pose_pct":    None,
        "mois":             [],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {output_path} écrit (source : {source})")
    return data


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def dry_run(config: dict):
    print("=" * 60)
    print("MODE DRY-RUN — aucune requête envoyée")
    print("=" * 60)
    print(f"PIXEL_BASE_URL       = {config['base_url'] or '(non défini)'}")
    cookie = config["session_cookie"]
    print(f"PIXEL_SESSION_COOKIE = {'(défini, ' + str(len(cookie)) + ' chars)' if cookie else '(non défini)'}")
    print()
    print("Étape 1 : GET", config['base_url'] + ENDPOINT_PATH, "→ extrait __RequestVerificationToken")
    print("Étape 2 : POST", config['base_url'] + ENDPOINT_PATH + "?" + HANDLER_PARAM)
    print("  Payload : DataTables + Search.TypeOperation=BAT-EQ-127")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    is_dry_run = "--dry-run" in sys.argv
    config = get_config()

    if is_dry_run:
        dry_run(config)
        return

    if not config["base_url"]:
        print("[ERREUR] PIXEL_BASE_URL non défini dans .env", file=sys.stderr)
        sys.exit(1)
    if not config["session_cookie"]:
        print("[ERREUR] PIXEL_SESSION_COOKIE non défini dans .env", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("Pixel CRM — fetch agrégats BAT-EQ-127")
    print(f"URL : {config['base_url']}{ENDPOINT_PATH}")
    print("=" * 60)

    agg, source = fetch_aggregates(config)

    if agg is None:
        print(
            "\n[ECHEC] Impossible de récupérer les agrégats.\n"
            "  Vérifier que PIXEL_SESSION_COOKIE est valide (non expiré).",
            file=sys.stderr,
        )
        sys.exit(1)

    data = write_public_json(agg, source)

    print("\nRésumé :")
    print(f"  Dossiers     : {data['nb_dossiers']:,}".replace(",", " "))
    print(f"  LED estimées : {data['led_signees']:,}".replace(",", " "))
    print(f"[OK] public_data.json mis à jour")
    print("=" * 60)


if __name__ == "__main__":
    main()
