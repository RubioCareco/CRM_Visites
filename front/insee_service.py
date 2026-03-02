import os
from typing import Dict, Any, Tuple

import requests
from django.core.cache import cache


INSEE_TOKEN_CACHE_KEY = "insee:access_token"
INSEE_TOKEN_TTL_FALLBACK = 3500
INSEE_DATA_CACHE_TTL = 24 * 60 * 60


def _build_company_name(unite_legale: Dict[str, Any]) -> str:
    denomination = (
        unite_legale.get("denominationUniteLegale")
        or unite_legale.get("denominationUsuelle1UniteLegale")
        or ""
    ).strip()
    if denomination:
        return denomination
    nom = (unite_legale.get("nomUniteLegale") or "").strip()
    prenom = (unite_legale.get("prenom1UniteLegale") or "").strip()
    return f"{prenom} {nom}".strip()


def _map_insee_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    etab = payload.get("etablissement", {}) or {}
    unite = etab.get("uniteLegale", {}) or {}
    adr = etab.get("adresseEtablissement", {}) or {}

    voie = " ".join(
        part for part in [
            adr.get("numeroVoieEtablissement"),
            adr.get("typeVoieEtablissement"),
            adr.get("libelleVoieEtablissement"),
        ]
        if part
    ).strip()

    return {
        "siret": etab.get("siret", ""),
        "entreprise": _build_company_name(unite),
        "adresse": voie,
        "code_postal": adr.get("codePostalEtablissement", "") or "",
        "ville": adr.get("libelleCommuneEtablissement", "") or "",
    }


def _get_insee_token() -> Tuple[str, str]:
    # Optional static token support for simple deployments.
    static_token = os.getenv("INSEE_ACCESS_TOKEN", "").strip()
    if static_token:
        return static_token, ""

    cached_token = cache.get(INSEE_TOKEN_CACHE_KEY)
    if cached_token:
        return cached_token, ""

    client_id = os.getenv("INSEE_CLIENT_ID", "").strip()
    client_secret = os.getenv("INSEE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return "", "INSEE credentials are missing"

    token_url = os.getenv("INSEE_TOKEN_URL", "https://api.insee.fr/token")
    try:
        resp = requests.post(
            token_url,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=10,
        )
    except requests.RequestException:
        return "", "Unable to reach INSEE token endpoint"

    if resp.status_code != 200:
        return "", "INSEE token request failed"

    data = resp.json()
    access_token = data.get("access_token", "")
    expires_in = int(data.get("expires_in", INSEE_TOKEN_TTL_FALLBACK))
    if not access_token:
        return "", "INSEE token response is invalid"

    cache.set(INSEE_TOKEN_CACHE_KEY, access_token, timeout=max(60, expires_in - 60))
    return access_token, ""


def fetch_company_by_siret(siret: str) -> Tuple[Dict[str, Any], int]:
    """
    Returns tuple: (payload, http_status).
    payload shape on success: {"success": True, "data": {...}}
    """
    cache_key = f"insee:siret:{siret}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return {"success": True, "data": cached_data, "cached": True}, 200

    token, token_error = _get_insee_token()
    if not token:
        return {"success": False, "error": token_error or "INSEE unavailable"}, 503

    base_url = os.getenv("INSEE_API_BASE_URL", "https://api.insee.fr/entreprises/sirene/V3.11")
    url = f"{base_url}/siret/{siret}"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException:
        return {"success": False, "error": "INSEE unavailable"}, 503

    if resp.status_code == 404:
        return {"success": False, "error": "SIRET inconnu"}, 404
    if resp.status_code == 429:
        return {"success": False, "error": "INSEE rate limit"}, 429
    if resp.status_code != 200:
        return {"success": False, "error": "INSEE error"}, 503

    mapped = _map_insee_payload(resp.json() or {})
    cache.set(cache_key, mapped, timeout=INSEE_DATA_CACHE_TTL)
    return {"success": True, "data": mapped}, 200
