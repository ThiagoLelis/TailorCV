"""Orquestração: feeds -> validação -> parsing -> SQLite -> LLM -> Markdown."""
from __future__ import annotations

import argparse
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import ingestor
import parsers
import validator
from cv_generator import CVGenerator
from storage import STATUS_CV_GENERATED, STATUS_FAILED, JobStore

log = logging.getLogger("job_hunter")


def slugify(text: str | None, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].rstrip("-")) or "unknown"


def cv_filename(job, today: date | None = None) -> str:
    today = today or date.today()
    return f"{today.isoformat()}_{slugify(job.company)}_{slugify(job.title)}.md"


@dataclass
class RunStats:
    found: int = 0
    unsupported: int = 0
    already_done: int = 0
    closed: int = 0
    stale: int = 0
    parse_errors: int = 0
    generated: int = 0
    failed: int = 0
    files: list[str] = field(default_factory=list)


def run(urls: list[str], store: JobStore, generator: CVGenerator | None, out_dir: Path,
        max_age_days: int = 30, timeout: float = 15, session=None) -> RunStats:
    stats = RunStats(found=len(urls))
    out_dir.mkdir(parents=True, exist_ok=True)

    for url in urls:
        if not parsers.is_supported(url):
            stats.unsupported += 1
            log.debug("Ignorando domínio não suportado: %s", url)
            continue
        if store.get_status(url) == STATUS_CV_GENERATED:
            stats.already_done += 1
            continue

        result = validator.validate(url, session=session, timeout=timeout)
        if not result.is_open:
            stats.closed += 1
            continue

        try:
            job = parsers.get_parser(url, max_age_days=max_age_days).parse(url, result.html)
        except parsers.StaleJobError as exc:
            stats.stale += 1
            log.info("Descartada: %s", exc)
            continue
        except parsers.ParserError as exc:
            stats.parse_errors += 1
            log.warning("Erro de parsing: %s", exc)
            continue

        jid = store.save_pending(job)
        if generator is None:  # --dry-run
            continue

        try:
            markdown = generator.generate(job)
            path = out_dir / cv_filename(job)
            path.write_text(markdown, encoding="utf-8")
            store.update_status(jid, STATUS_CV_GENERATED, cv_path=str(path))
            stats.generated += 1
            stats.files.append(str(path))
            log.info("CV salvo: %s", path)
        except Exception as exc:  # noqa: BLE001 - erro da LLM não deve parar o lote
            store.update_status(jid, STATUS_FAILED, error=str(exc)[:500])
            stats.failed += 1
            log.error("Falha ao gerar CV para %s: %s", url, exc)

    return stats


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Job Hunter & AI Resume Generator")
    ap.add_argument("--feeds", default="feeds.txt", help="Arquivo com URLs de feeds RSS (uma por linha)")
    ap.add_argument("--url", action="append", default=[], help="Processa URL(s) de vaga diretamente")
    ap.add_argument("--resume", default="base_resume.md")
    ap.add_argument("--db", default="jobs.db")
    ap.add_argument("--out", default="generated_cvs")
    ap.add_argument("--max-age-days", type=int, default=int(os.getenv("MAX_JOB_AGE_DAYS", "30")))
    ap.add_argument("--dry-run", action="store_true", help="Não chama a LLM; só valida, parseia e salva")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    urls = list(args.url)
    if Path(args.feeds).exists():
        urls += [item.url for item in ingestor.collect_items(ingestor.load_feed_urls(args.feeds))]
    elif not urls:
        ap.error(f"Arquivo de feeds não encontrado: {args.feeds}")
    urls = list(dict.fromkeys(urls))

    generator = None if args.dry_run else CVGenerator(args.resume)
    store = JobStore(args.db)
    try:
        stats = run(urls, store, generator, Path(args.out), args.max_age_days,
                    timeout=float(os.getenv("HTTP_TIMEOUT", "15")))
    finally:
        store.close()

    log.info("Resumo: %s", {k: v for k, v in vars(stats).items() if k != "files"})
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
