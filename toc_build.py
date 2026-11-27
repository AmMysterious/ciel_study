# -*- coding: utf-8 -*-
"""toc_build.py - an "On this page" jump list at the top of the long hand-written pages.  0.1.0

27 Nov 2026 (Nawar: tidy EVERY page, not just home). On a phone Terms is 9 screens, Refunds 7, Privacy 6, Pricing 7.
Nothing is hidden or removed: every <h2> in <main> gets an id, and a row of jump links goes under the <h1> (after the
"Last updated" line when there is one). Rerun-safe: the list sits between <!--TOC--> markers and is rebuilt each run.
The topic pages (pyt-*.html) get their own list from pyt_pages.py. support.html is built by sync_site.py from
_support_shell.html, so the list goes into the shell.

    python toc_build.py            write
    python toc_build.py --check    say what would change
"""
import re, sys, html
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = ["terms.html", "privacy.html", "refunds.html", "pricing.html", "_support_shell.html", "faq.html", "exam-fmge.html"]
CHECK = "--check" in sys.argv


def slug(t):
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"^\d+\.\s*", "", html.unescape(t)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def label(t):
    t = re.sub(r"<[^>]+>", "", t)
    return html.escape(re.sub(r"^\d+[a-z]?\.\s*", "", html.unescape(t)).strip(), quote=False)


changed = []
for name in PAGES:
    f = HERE / name
    s = old = f.read_text(encoding="utf-8")
    s = re.sub(r"<!--TOC-->.*?<!--/TOC-->\n?", "", s, flags=re.S)
    main = re.search(r'<main[^>]*>.*?</main>', s, re.S)
    if not main:
        continue
    seen, links = set(), []

    def add_id(m):
        attrs, inner = m.group(1), m.group(2)
        hid = re.search(r'id="([^"]+)"', attrs)
        if hid:
            i = hid.group(1)
        else:
            i = base = slug(inner) or "section"
            k = 2
            while i in seen:
                i, k = f"{base}-{k}", k + 1
            attrs = f'{attrs} id="{i}"'
        seen.add(i)
        links.append(f'<a href="#{i}">{label(inner)}</a>')
        return f"<h2{attrs}>{inner}</h2>"

    body = re.sub(r"<h2([^>]*)>(.*?)</h2>", add_id, main.group(0), flags=re.S)
    if len(links) >= 4:
        toc = '<!--TOC--><nav class="toc" aria-label="On this page"><span>On this page</span>' + "".join(links) + "</nav><!--/TOC-->\n"
        upd = re.search(r'(<h1[^>]*>.*?</h1>\s*(?:<p class="updated">.*?</p>\s*)?)', body, re.S)
        if upd:
            body = body[:upd.end()] + toc + body[upd.end():]
    s = s[:main.start()] + body + s[main.end():]
    if s != old:
        changed.append(name)
        if not CHECK:
            f.write_text(s, encoding="utf-8", newline="\n")
# 27 Nov: phones kept an old style.css after a push (Nawar's screenshot showed the new Topics tiles as a bare list).
# Every page links the stylesheet as style.css?v=<first 8 of its sha256>, so a changed file is a new address.
import hashlib
ver = hashlib.sha256((HERE / "style.css").read_bytes()).hexdigest()[:8]
for f in sorted(HERE.rglob("*.html")):
    if "vendor" in f.parts:
        continue
    s = old = f.read_text(encoding="utf-8")
    s = re.sub(r'href="((?:\.\./)*)style\.css(?:\?v=[0-9a-f]+)?"', lambda m: f'href="{m.group(1)}style.css?v={ver}"', s)
    if s != old:
        changed.append(f.name)
        if not CHECK:
            f.write_text(s, encoding="utf-8", newline="\n")
print(("would change: " if CHECK else "written: ") + (", ".join(changed) or "nothing"))
