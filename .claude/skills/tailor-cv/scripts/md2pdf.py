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
body { font-family: Calibri, Arial, Helvetica, sans-serif; font-size: 10.5pt; line-height: 1.32; color: #111; }
h1 { font-size: 20pt; margin: 0 0 2px 0; }
p.headline { font-size: 11.5pt; font-weight: bold; margin: 0 0 2px 0; color: #222; }
p.contact { margin: 0 0 6px 0; font-size: 10pt; }
h2 { font-size: 11.5pt; text-transform: uppercase; letter-spacing: .5px; border-bottom: 1px solid #444;
     margin: 10px 0 4px 0; padding-bottom: 1px; }
h3 { font-size: 10.8pt; margin: 7px 0 0 0; }
p.meta { margin: 0 0 2px 0; font-style: italic; color: #333; }
p { margin: 2px 0; }
ul { margin: 2px 0 2px 0; padding-left: 16px; }
li { margin: 1px 0; }
h3, p.meta { page-break-after: avoid; }
li { page-break-inside: avoid; }
"""


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<em>\1</em>", s)
    return s


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
            out.append(f'<p class="contact">{inline(line)}</p>')
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
    title = re.search(r"^# (.+)$", md, re.M).group(1)
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)} - Resume</title>'
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for md in sys.argv[1:]:
        p = Path(md)
        render(p, p.with_suffix(".pdf"))
        print("ok", p.with_suffix(".pdf"))
