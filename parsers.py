"""Extração de dados de vagas por ATS (Strategy Pattern + Factory)."""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify

from models import JobPosting

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- erros
class ParserError(Exception):
    """Erro base de parsing."""


class UnsupportedATSError(ParserError):
    """Nenhum parser registrado para o domínio."""


class NoJobDataError(ParserError):
    """Não foi possível extrair título/descrição da página."""


class StaleJobError(ParserError):
    """Vaga mais antiga que o limite configurado (regra de descarte)."""


# --------------------------------------------------------------------------- helpers
def html_to_markdown(raw: str) -> str:
    """Converte a descrição (HTML, às vezes escapado dentro do JSON-LD) em Markdown limpo."""
    if not raw:
        return ""
    text = html_lib.unescape(raw)
    if "<" in text and ">" in text:
        text = markdownify(text, heading_style="ATX", bullets="-", strip=["img", "script", "style"])
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        log.debug("Data inválida: %r", value)
        return None


def _is_job_posting(node: dict) -> bool:
    t = node.get("@type")
    return t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t)


def _walk(node: Any):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _walk(node["@graph"])


def extract_job_posting_ld(soup: BeautifulSoup) -> dict | None:
    """Retorna o primeiro objeto JSON-LD do tipo JobPosting da página."""
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            # strict=False tolera quebras de linha cruas dentro das strings (comum em ATS)
            data = json.loads(raw, strict=False)
        except json.JSONDecodeError as exc:
            log.debug("JSON-LD inválido ignorado: %s", exc)
            continue
        for node in _walk(data):
            if _is_job_posting(node):
                return node
    return None


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return tag.get("content").strip() if tag and tag.get("content") else None


# --------------------------------------------------------------------------- strategy
class ATSParser(ABC):
    platform: ClassVar[str]
    domains: ClassVar[tuple[str, ...]]

    def __init__(self, max_age_days: int = 30, today: date | None = None):
        self.max_age_days = max_age_days
        self.today = today

    @classmethod
    def matches(cls, url: str) -> bool:
        host = urlparse(url).netloc.lower().split(":")[0]
        return any(host == d or host.endswith("." + d) for d in cls.domains)

    def parse(self, url: str, html: str) -> JobPosting:
        """Template method: JSON-LD primeiro, fallback de HTML específico do ATS."""
        soup = BeautifulSoup(html, "html.parser")
        ld = extract_job_posting_ld(soup)

        title = description = company = None
        date_posted = None
        if ld:
            title = (ld.get("title") or "").strip() or None
            description = html_to_markdown(ld.get("description") or "")
            date_posted = parse_date(ld.get("datePosted"))
            org = ld.get("hiringOrganization")
            if isinstance(org, dict):
                company = (org.get("name") or "").strip() or None
            elif isinstance(org, str):
                company = org.strip() or None

        if not title or not description:
            fb_title, fb_desc = self.fallback_extract(soup)
            title = title or fb_title
            description = description or fb_desc

        if not title or not description:
            raise NoJobDataError(f"Sem título/descrição em {url}")

        job = JobPosting(
            url=url,
            ats_platform=self.platform,
            title=title,
            company=company or self.company_from_url(url),
            date_posted=date_posted,
            description=description,
        )
        if job.is_stale(self.max_age_days, self.today):
            raise StaleJobError(f"Vaga publicada em {job.date_posted} (> {self.max_age_days} dias): {url}")
        return job

    def company_from_url(self, url: str) -> str | None:
        """Padrão dos três ATS: o slug da empresa é o 1º segmento do path."""
        parts = [p for p in urlparse(url).path.split("/") if p]
        return parts[0] if parts else None

    @abstractmethod
    def fallback_extract(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """Extrai (título, descrição em markdown) do HTML quando não há JSON-LD."""

    # utilitário para as subclasses
    @staticmethod
    def _first(soup: BeautifulSoup, selectors: list[str]):
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                return el
        return None


class AshbyParser(ATSParser):
    platform = "ashby"
    domains = ("ashbyhq.com",)

    def fallback_extract(self, soup):
        title = _meta(soup, "og:title") or (soup.title.get_text(strip=True) if soup.title else None)
        desc_el = self._first(soup, ["div[class*='descriptionText']", "div[class*='_description']", "main"])
        desc = html_to_markdown(str(desc_el)) if desc_el else _meta(soup, "og:description")
        return title, desc


class GreenhouseParser(ATSParser):
    platform = "greenhouse"
    domains = ("greenhouse.io",)

    def company_from_url(self, url):
        qs = parse_qs(urlparse(url).query)
        if qs.get("for"):  # boards.greenhouse.io/embed/job_app?for=<empresa>&token=...
            return qs["for"][0]
        return super().company_from_url(url)

    def fallback_extract(self, soup):
        title_el = self._first(soup, ["h1.section-header", "h1.app-title", ".job__title h1", "h1"])
        desc_el = self._first(soup, ["div.job__description", "div#content", "div.job-post-content"])
        return (
            title_el.get_text(" ", strip=True) if title_el else _meta(soup, "og:title"),
            html_to_markdown(str(desc_el)) if desc_el else None,
        )


class LeverParser(ATSParser):
    platform = "lever"
    domains = ("lever.co",)

    def fallback_extract(self, soup):
        title_el = self._first(soup, ["div.posting-headline h2", "h2"])
        sections = soup.select("div[data-qa='job-description'], div.section-wrapper div.section")
        desc = "\n\n".join(html_to_markdown(str(s)) for s in sections) or None
        return (title_el.get_text(" ", strip=True) if title_el else _meta(soup, "og:title"), desc)


# --------------------------------------------------------------------------- factory
PARSERS: tuple[type[ATSParser], ...] = (AshbyParser, GreenhouseParser, LeverParser)


def get_parser(url: str, **kwargs) -> ATSParser:
    """Factory Method: identifica o ATS pelo domínio e instancia o parser certo."""
    for cls in PARSERS:
        if cls.matches(url):
            return cls(**kwargs)
    raise UnsupportedATSError(f"ATS não suportado: {urlparse(url).netloc}")


def is_supported(url: str) -> bool:
    return any(cls.matches(url) for cls in PARSERS)
