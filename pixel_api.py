# -*- coding: utf-8 -*-
"""
Pixel CRM — agrégats BAT-EQ-127 sans export CSV (pas de PII).
Interroge l'endpoint de recherche pour obtenir les totaux directement.

Usage :
    # Depuis la session Pixel (cookie de session nécessaire)
    export PIXEL_SESSION_COOKIE="..."   # cookie de session Pixel
    export PIXEL_BASE_URL="https://..."  # URL base Pixel CRM
    python pixel_api.py

    # Mode dry-run (affiche la requête sans l'envoyer)
    python pixel_api.py --dry-run

Sortie : public_data.json (agrégats anonymisés, commitable dans git)

Variables d'environnement (ou fichier .env) :
    PIXEL_BASE_URL          URL de base du CRM Pixel (ex: https://app.pixel-crm.fr)
    PIXEL_SESSION_COOKIE    Valeur du cookie de session (copier depuis DevTools → Network)
    PIXEL_REFERER           (optionnel) URL de la page de recherche pour le header Referer
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ENDPOINT_PATH = "/Fiche/Recherche"
HANDLER_PARAM = "handler=GetBody_ServerSide"
OBJECTIF_MENSUEL = 30_000

# Payloads à essayer (du plus probable au moins probable).
# Le format exact des paramètres Pixel n'est pas documenté publiquement ;
# on tente plusieurs variantes pour maximiser les chances de succès.
# Adapter si la réponse indique un format différent.
CANDIDATE_PAYLOADS = [
    # Variante 1 : paramètres courants des CRM ASP.NET Core (Razor Pages handler)
    {
        "Search.BaremeMultiple": "BAT-EQ-127",
        "Search.TypeOperation":  "BAT-EQ-127",
        "Search.Statut":         "",
        "draw":                  "1",
        "start":                 "0",
        "length":                "1",  # on ne veut que les totaux, pas les lignes
    },
    # Variante 2 : nommage plus court
    {
        "BaremeMultiple": "BAT-EQ-127",
        "draw":           "1",
        "start":          "0",
        "length":         "1",
    },
    # Variante 3 : JSON body (certains endpoints Pixel acceptent du JSON)
    # Marqué avec la clé spéciale "__json__" pour indiquer l'encodage
    {
        "__json__": True,
        "search": {
            "baremeMultiple": "BAT-EQ-127",
        },
        "draw":   1,
        "start":  0,
        "length": 1,
    },
]

# ---------------------------------------------------------------------------
# Lecture de l'environnement (supporte aussi un fichier .env minimal)
# ---------------------------------------------------------------------------

def _load_dotenv(path: str = ".env"):
    """Charge un fichier .env simple (KEY=VALUE, commentaires #) dans os.environ."""
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
    """Retourne la config depuis l'environnement."""
    _load_dotenv()
    base_url = os.environ.get("PIXEL_BASE_URL", "").rstrip("/")
    session_cookie = os.environ.get("PIXEL_SESSION_COOKIE", "")
    referer = os.environ.get("PIXEL_REFERER", base_url + "/Fiche/Recherche" if base_url else "")
    return {
        "base_url":       base_url,
        "session_cookie": session_cookie,
        "referer":        referer,
    }


# ---------------------------------------------------------------------------
# Construction de la requête
# ---------------------------------------------------------------------------

def build_request(base_url: str, session_cookie: str, referer: str,
                  payload: dict) -> urllib.request.Request:
    """
    Construit un objet Request pour un payload donné.
    Gère les deux modes : form-urlencoded et JSON.
    """
    url = f"{base_url}{ENDPOINT_PATH}?{HANDLER_PARAM}"

    is_json = payload.get("__json__", False)
    if is_json:
        body_dict = {k: v for k, v in payload.items() if k != "__json__"}
        body = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
        content_type = "application/json; charset=utf-8"
    else:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"

    headers = {
        "Content-Type":  content_type,
        "Cookie":        session_cookie,
        "User-Agent":    (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":        "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":       referer,
        "Origin":        base_url,
    }

    return urllib.request.Request(url, data=body, headers=headers, method="POST")


# ---------------------------------------------------------------------------
# Parseur de réponse
# ---------------------------------------------------------------------------

def _safe_int(v) -> int | None:
    """Tente de convertir une valeur en int (accepte str avec espaces, virgules)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def parse_aggregates(data: dict) -> dict | None:
    """
    Tente d'extraire les agrégats depuis la réponse JSON Pixel.

    Les réponses DataTables (format standard Pixel/ASP.NET) contiennent :
      - recordsTotal    : nombre total de dossiers
      - data            : liste de lignes (on ne lit pas les détails)

    D'autres formats possibles sont aussi tentés.
    Retourne un dict {nb_dossiers, total_led, prime_total} ou None si non parsé.
    """
    agg = {}

    # --- Format DataTables (le plus courant) ---
    if "recordsTotal" in data:
        agg["nb_dossiers"] = _safe_int(data["recordsTotal"])

    # Champs de totaux qui peuvent varier selon la configuration Pixel
    # (noms observés dans des exports JSON similaires)
    led_keys   = ["totalLED", "total_led", "TotalLED", "produit_qte_total",
                  "led_total", "sumLED", "SumLED"]
    prime_keys = ["totalPrime", "total_prime", "TotalPrime", "prime_cee_total",
                  "sumPrime", "SumPrime", "primeTotale"]
    doss_keys  = ["recordsTotal", "recordsFiltered", "nb_dossiers", "NbDossiers",
                  "totalDossiers"]

    for k in led_keys:
        if k in data and data[k] is not None:
            agg["total_led"] = _safe_int(data[k])
            break

    for k in prime_keys:
        if k in data and data[k] is not None:
            agg["prime_total"] = _safe_int(data[k])
            break

    if "nb_dossiers" not in agg:
        for k in doss_keys:
            if k in data and data[k] is not None:
                agg["nb_dossiers"] = _safe_int(data[k])
                break

    # --- Tentative de lecture depuis un champ "summary" ou "totaux" ---
    for key in ("summary", "totaux", "totals", "aggregate", "aggregates"):
        if key in data and isinstance(data[key], dict):
            sub = data[key]
            for k in led_keys:
                if k in sub:
                    agg.setdefault("total_led", _safe_int(sub[k]))
            for k in prime_keys:
                if k in sub:
                    agg.setdefault("prime_total", _safe_int(sub[k]))
            for k in doss_keys:
                if k in sub:
                    agg.setdefault("nb_dossiers", _safe_int(sub[k]))

    if not agg:
        return None
    return agg


# ---------------------------------------------------------------------------
# Envoi de la requête
# ---------------------------------------------------------------------------

def fetch_aggregates(config: dict) -> tuple[dict | None, str]:
    """
    Essaie les payloads candidats dans l'ordre.
    Retourne (agrégats_dict_ou_None, message_diagnostic).
    """
    base_url       = config["base_url"]
    session_cookie = config["session_cookie"]
    referer        = config["referer"]

    for i, payload in enumerate(CANDIDATE_PAYLOADS, 1):
        is_json = payload.get("__json__", False)
        mode    = "JSON" if is_json else "form-urlencoded"
        print(f"[Tentative {i}/{len(CANDIDATE_PAYLOADS)}] Payload {mode}...", flush=True)

        req = build_request(base_url, session_cookie, referer, payload)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status  = resp.status
                headers = dict(resp.getheaders())
                raw     = resp.read()
        except urllib.error.HTTPError as exc:
            status  = exc.code
            headers = dict(exc.headers)
            raw     = exc.read()
            print(f"  -> HTTP {status}", file=sys.stderr)
            _print_diag(status, headers, raw)
            continue
        except urllib.error.URLError as exc:
            print(f"  -> Erreur réseau : {exc.reason}", file=sys.stderr)
            continue

        print(f"  -> HTTP {status}")

        if status not in (200, 201, 202):
            _print_diag(status, headers, raw)
            continue

        # Tenter le décodage JSON
        try:
            text = raw.decode("utf-8", errors="replace")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"  -> Réponse non-JSON ({exc}) — premiers 500 chars :")
            print(f"     {raw[:500]!r}", file=sys.stderr)
            continue

        agg = parse_aggregates(data)
        if agg:
            print(f"  -> Agrégats extraits : {agg}")
            return agg, f"payload_{i}_{mode}"

        # Pas d'agrégats reconnus : dump diagnostic
        print(f"  -> Réponse JSON reçue mais agrégats non reconnus.")
        print(f"     Clés de premier niveau : {list(data.keys())[:20]}", file=sys.stderr)
        print(f"     Premiers 500 chars : {json.dumps(data)[:500]}", file=sys.stderr)

    return None, "all_payloads_failed"


def _print_diag(status: int, headers: dict, raw: bytes):
    """Affiche les informations de diagnostic en cas d'échec."""
    print(f"  Diagnostic — statut HTTP : {status}", file=sys.stderr)
    interesting = ("content-type", "www-authenticate", "location",
                   "x-aspnet-version", "x-powered-by")
    for k, v in headers.items():
        if k.lower() in interesting:
            print(f"  Header {k}: {v}", file=sys.stderr)
    snippet = raw[:500].decode("utf-8", errors="replace")
    print(f"  Body (500 premiers chars) : {snippet!r}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Écriture de public_data.json (même format que daily_summary.py)
# ---------------------------------------------------------------------------

def write_public_json(agg: dict, source: str,
                      output_path: str = "public_data.json") -> dict:
    """
    Écrit les agrégats dans public_data.json au même format que daily_summary.py.
    Aucune PII — uniquement des totaux numériques.
    """
    today = date.today()

    data = {
        "generated":        today.strftime("%Y-%m-%d"),
        "demo_mode":        False,
        "source":           source,
        "led_signees":      int(agg.get("total_led") or 0),
        "nb_dossiers":      int(agg.get("nb_dossiers") or 0),
        "prime_total":      int(agg.get("prime_total") or 0),
        "led_moy":          37,   # valeur connue du diagnostic (pas de PII)
        "led_med":          30,
        "led_max":          459,
        "objectif_mensuel": OBJECTIF_MENSUEL,
        "taux_pose_pct":    None,  # non disponible sans colonne statut
        "mois":             [],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {output_path} écrit (source : {source})")
    return data


# ---------------------------------------------------------------------------
# Mode dry-run
# ---------------------------------------------------------------------------

def dry_run(config: dict):
    """Affiche les requêtes qui seraient envoyées, sans les envoyer."""
    base_url       = config["base_url"]
    session_cookie = config["session_cookie"]
    referer        = config["referer"]

    print("=" * 60)
    print("MODE DRY-RUN — aucune requête envoyée")
    print("=" * 60)
    print(f"PIXEL_BASE_URL          = {base_url or '(non défini)'}")
    print(f"PIXEL_SESSION_COOKIE    = {'(défini, ' + str(len(session_cookie)) + ' chars)' if session_cookie else '(non défini)'}")
    print(f"PIXEL_REFERER           = {referer or '(non défini)'}")
    print()

    for i, payload in enumerate(CANDIDATE_PAYLOADS, 1):
        is_json = payload.get("__json__", False)
        mode    = "JSON" if is_json else "form-urlencoded"
        url     = f"{base_url}{ENDPOINT_PATH}?{HANDLER_PARAM}"

        print(f"--- Requête {i}/{len(CANDIDATE_PAYLOADS)} ({mode}) ---")
        print(f"  POST {url}")
        print(f"  Content-Type: {'application/json' if is_json else 'application/x-www-form-urlencoded'}")

        if is_json:
            body_dict = {k: v for k, v in payload.items() if k != "__json__"}
            print(f"  Body (JSON) : {json.dumps(body_dict, ensure_ascii=False)}")
        else:
            print(f"  Body (form) : {urllib.parse.urlencode(payload)}")
        print()

    print("Pour exécuter réellement : supprimer --dry-run")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    is_dry_run = "--dry-run" in sys.argv

    config = get_config()

    if is_dry_run:
        dry_run(config)
        return

    # Validation de la configuration
    if not config["base_url"]:
        print(
            "[ERREUR] PIXEL_BASE_URL non défini.\n"
            "  Définir dans l'environnement ou dans un fichier .env :\n"
            "    PIXEL_BASE_URL=https://votre-instance.pixel-crm.fr",
            file=sys.stderr,
        )
        sys.exit(1)

    if not config["session_cookie"]:
        print(
            "[ERREUR] PIXEL_SESSION_COOKIE non défini.\n"
            "  1. Ouvrir Pixel CRM dans le navigateur et se connecter.\n"
            "  2. Ouvrir DevTools (F12) → onglet Network → sélectionner une requête.\n"
            "  3. Copier la valeur complète du header 'Cookie' de la requête.\n"
            "  4. Définir PIXEL_SESSION_COOKIE dans .env ou l'environnement.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 60)
    print(f"Pixel CRM — fetch agrégats BAT-EQ-127")
    print(f"URL : {config['base_url']}{ENDPOINT_PATH}")
    print("=" * 60)

    agg, source = fetch_aggregates(config)

    if agg is None:
        print(
            "\n[ECHEC] Aucun agrégat extrait après toutes les tentatives.\n"
            "Actions possibles :\n"
            "  1. Vérifier que PIXEL_SESSION_COOKIE est valide et non expiré.\n"
            "  2. Ouvrir DevTools sur la page de recherche Pixel, filtrer par\n"
            "     'GetBody_ServerSide', copier le payload exact de la requête\n"
            "     réseau et l'ajouter dans CANDIDATE_PAYLOADS dans pixel_api.py.\n"
            "  3. Contacter le support Pixel pour la documentation de l'API.",
            file=sys.stderr,
        )
        sys.exit(1)

    data = write_public_json(agg, source)

    print("\nRésumé des agrégats récupérés :")
    print(f"  LED signées  : {data['led_signees']:,}".replace(",", " "))
    print(f"  Dossiers     : {data['nb_dossiers']:,}".replace(",", " "))
    print(f"  Prime totale : {data['prime_total']:,} €".replace(",", " "))
    print(f"\n[OK] public_data.json mis à jour (source : {source})")
    print("=" * 60)


if __name__ == "__main__":
    main()
