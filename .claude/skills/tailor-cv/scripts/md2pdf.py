"""Minimal Markdown -> ATS-friendly single-column HTML -> PDF via headless Chrome/Edge.

Usage: python3 -I md2pdf.py "<dir>/<Name> - Company.md" [more.md ...]
Writes the PDF next to each .md (same base name). Works on WSL (Windows Chrome/Edge) and native Linux.
Supported Markdown: '# ' name, next line headline, next line contact, '## ' sections, '### ' job titles,
'*...*' meta lines, '- ' bullets, **bold**, *italic*.
"""
import html
import re
import subprocess
import sys
import zlib
from pathlib import Path

import shutil

WIN_BROWSERS = ["/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
                "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
                "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"]
LINUX_BROWSERS = ["google-chrome", "chromium", "chromium-browser", "microsoft-edge"]


def find_browser():
    for b in WIN_BROWSERS:
        if Path(b).exists():
            return b, True
    for b in LINUX_BROWSERS:
        if shutil.which(b):
            return shutil.which(b), False
    sys.exit("No Chrome/Edge/Chromium found for PDF rendering")

CSS = """
@page { size: Letter; margin: 0.55in 0.6in; }
/* Text-layer rules (do not undo): Chrome splits a text run at every kerning pair, ligature, letter-spacing
   and fractional-px font size. Simple ATS parsers read each split as a space ("y ears", "P R O F I L E")
   and then miss the email and section headings. Keep kerning/ligatures off, no letter-spacing, and
   font sizes in whole px. check_pdf() enforces it. */
body { font-family: Calibri, Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.32; color: #111;
       font-kerning: none; font-variant-ligatures: none; }
h1 { font-size: 26px; margin: 0 0 2px 0; }
p.headline { font-size: 15px; font-weight: bold; margin: 0 0 2px 0; color: #222; }
p.contact { margin: 0 0 6px 0; font-size: 13px; }
a { color: inherit; text-decoration: none; }
h2 { font-size: 15px; text-transform: uppercase; border-bottom: 1px solid #444;
     margin: 10px 0 4px 0; padding-bottom: 1px; }
h3 { font-size: 14px; margin: 7px 0 0 0; }
p.meta { margin: 0 0 2px 0; font-style: italic; color: #333; }
p { margin: 2px 0; }
ul { margin: 2px 0 2px 0; padding-left: 16px; }
li { margin: 1px 0; }
h2, h3, p.meta { break-after: avoid; page-break-after: avoid; }
li { break-inside: avoid; page-break-inside: avoid; }
"""


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<em>\1</em>", s)
    return s


def link_contacts(s: str) -> str:
    """Make emails and bare URLs in the (already escaped) contact line clickable; the visible text is unchanged."""
    s = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", lambda m: f'<a href="mailto:{m[0]}">{m[0]}</a>', s)
    return re.sub(r"(?<![\w@/.])((?:https?://)?(?:www\.)?[\w-]+\.(?:com|io|dev|me|net|org)/[\w./-]*[\w/])",
                  lambda m: f'<a href="{m[1] if m[1].startswith("http") else "https://" + m[1]}">{m[1]}</a>', s)


def convert(md: str) -> str:
    out, in_list, header_lines = [], False, 0
    lines = md.splitlines()
    for raw in lines:
        line = raw.rstrip()
        if not line.startswith("- ") and in_list:
            out.append("</ul>")
            in_list = False
        if not line:
            continue
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
            header_lines = 1
        elif line.startswith("## "):
            header_lines = 0
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        elif header_lines == 1:
            out.append(f'<p class="headline">{inline(line.strip("*"))}</p>')
            header_lines = 2
        elif header_lines == 2:
            out.append(f'<p class="contact">{link_contacts(inline(line))}</p>')
            header_lines = 0
        elif re.fullmatch(r"\*[^*].*\*", line):
            out.append(f'<p class="meta">{inline(line[1:-1])}</p>')
        else:
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def render(md_path: Path, pdf_path: Path) -> None:
    md = md_path.read_text(encoding="utf-8")
    h1 = re.search(r"^# (.+)$", md, re.M)
    title = f"{h1.group(1)} - Resume" if h1 else md_path.stem
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
           f"<style>{CSS}</style></head><body>{convert(md)}</body></html>")
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(doc, encoding="utf-8")
    browser, is_win = find_browser()
    conv = (lambda p: subprocess.check_output(["wslpath", "-w", str(p.resolve())], text=True).strip()) \
        if is_win else (lambda p: str(p.resolve()))
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={conv(pdf_path)}", conv(html_path)],
                   check=True, capture_output=True, timeout=120)
    html_path.unlink()


def split_runs(pdf_path: Path) -> int:
    """Count text lines that Chrome wrote as more than one run (a kerning/letter-spacing split ATS parsers misread)."""
    splits = 0
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_path.read_bytes(), re.S):
        try:
            content = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        for block in re.findall(rb"BT(.*?)ET", content, re.S):
            splits += len(re.findall(rb"T[jJ]\b", block)) > 1
    return splits


def check_pdf(md_path: Path, pdf_path: Path) -> list[str]:
    """Read the PDF back the way an ATS does and report anything it would miss."""
    problems = []
    if n := split_runs(pdf_path):
        problems.append(f"{n} text line(s) split into pieces; ATS parsers may read spaces inside words")
    if not shutil.which("pdftotext"):
        return problems + ["pdftotext not installed (apt install poppler-utils); text extraction not checked"]
    text = subprocess.run(["pdftotext", "-raw", str(pdf_path), "-"], capture_output=True, text=True).stdout
    flat = re.sub(r"\s+", " ", text)
    md = md_path.read_text(encoding="utf-8")
    expected = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", md)[:1]
    expected += re.findall(r"\+\d[\d ()-]{7,}\d", md)[:1]
    expected += re.findall(r"linkedin\.com/in/[\w-]+", md)[:1]
    expected += [h.upper() for h in re.findall(r"^## (.+)$", md, re.M)]
    problems += [f"not found in extracted text: {e!r}" for e in expected if e not in flat]
    return problems


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    failed = False
    for md in sys.argv[1:]:
        p = Path(md)
        render(p, p.with_suffix(".pdf"))
        problems = check_pdf(p, p.with_suffix(".pdf"))
        print("FAIL" if problems else "ok", p.with_suffix(".pdf"))
        for problem in problems:
            print("   -", problem)
        failed = failed or bool(problems)
    sys.exit(1 if failed else 0)
