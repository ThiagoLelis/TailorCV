"""Ingestão de feeds RSS/Atom do Google Alerts."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import feedparser
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedItem:
    title: str
    url: str
    feed_url: str


def extract_target_url(link: str) -> str:
    """Desembrulha o redirect do Google (https://www.google.com/url?...&url=<destino>)."""
    parsed = urlparse(link)
    host = parsed.netloc.lower()
    if (host == "google.com" or host.endswith(".google.com")) and parsed.path == "/url":
        qs = parse_qs(parsed.query)
        for key in ("url", "q"):
            if qs.get(key):
                return qs[key][0]
    return link


def _clean_title(raw: str) -> str:
    # O Google Alerts marca o termo buscado com <b>...</b> no título.
    return BeautifulSoup(raw or "", "html.parser").get_text(" ", strip=True)


def load_feed_urls(path: str | Path) -> list[str]:
    """Lê URLs de feed de um arquivo texto (uma por linha, '#' é comentário)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def fetch_feed_items(feed_url: str) -> list[FeedItem]:
    """Faz o parse de um feed (URL, caminho local ou string XML)."""
    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        log.warning("Falha ao ler feed %s: %s", feed_url, parsed.get("bozo_exception"))
        return []
    items = []
    for entry in parsed.entries:
        link = entry.get("link")
        if not link:
            continue
        items.append(
            FeedItem(
                title=_clean_title(entry.get("title", "")),
                url=extract_target_url(link),
                feed_url=feed_url,
            )
        )
    return items


def collect_items(feed_urls: list[str]) -> list[FeedItem]:
    """Lê todos os feeds e remove URLs duplicadas, preservando a ordem."""
    seen: set[str] = set()
    result: list[FeedItem] = []
    for feed_url in feed_urls:
        for item in fetch_feed_items(feed_url):
            if item.url not in seen:
                seen.add(item.url)
                result.append(item)
    log.info("%d URLs únicas coletadas de %d feeds", len(result), len(feed_urls))
    return result
