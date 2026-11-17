"""Valida se a vaga ainda está aberta."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

CLOSED_STATUSES = {301, 302, 404}
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


@dataclass
class ValidationResult:
    url: str
    is_open: bool
    status_code: int | None
    html: str | None = None


def validate(url: str, session: requests.Session | None = None, timeout: float = 15) -> ValidationResult:
    """GET sem seguir redirects. 200 = aberta; 301/302/404 (ou qualquer outro) = fechada.

    Retorna o HTML para que a página não precise ser baixada de novo pelo parser.
    """
    http = session or requests
    try:
        resp = http.get(url, allow_redirects=False, timeout=timeout, headers=DEFAULT_HEADERS)
    except requests.RequestException as exc:
        log.warning("Erro de rede em %s: %s", url, exc)
        return ValidationResult(url, False, None)

    if resp.status_code == 200:
        return ValidationResult(url, True, 200, resp.text)
    if resp.status_code in CLOSED_STATUSES:
        log.info("Vaga fechada (%s): %s", resp.status_code, url)
    else:
        log.info("Status inesperado (%s), tratando como indisponível: %s", resp.status_code, url)
    return ValidationResult(url, False, resp.status_code)


def is_job_open(url: str, **kwargs) -> bool:
    """Interface booleana da spec."""
    return validate(url, **kwargs).is_open
