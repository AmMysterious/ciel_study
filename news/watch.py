"""Exam news for the Ciel Study site - runs on GitHub Actions every 3 hours (.github/workflows/news.yml). 8 Nov 2026.

Independent of everything else (his rule, 8 Nov): no laptop, no Ciel, no bot token here.

AUTHENTIC ONLY. An item is published only when it is an OFFICIAL notice, read from the exam body's own site, and it
always links there. Its title is the body's own words; nothing is summarised or rewritten.
  NBEMS  natboard.edu.in/deptnotice        FMGE, NEET-PG   (dated rows)
  AIIMS  aiimsexams.ac.in home + notices   INI-CET          (dated; needs a real browser - Playwright)
  UPSC   upsc.gov.in/whats-new             UPSC CMS         (no date on the site: the date first seen here)
  MCC    mcc.nic.in/pg-medical-counselling NEET-PG counselling (date from the PDF's own upload name)
News sites (Google News RSS) are read only as a CROSS-CHECK: a fresh headline about a result / admit card / date that
has no official notice yet is listed under "unconfirmed" in news.json and never shown. If one stays unconfirmed for
long, a source parser may be broken - the run summary says so.

Writes news/news.json and the <!--NEWS:x--> ... <!--/NEWS--> blocks in exams.html and exam-*.html.
The Study Bot reads news.json from the site and posts new items in the group's Exam News topic.
usage: python news/watch.py [--offline news/news.json]   (offline = re-render pages only)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

SITE = Path(__file__).resolve().parent.parent
STORE = SITE / "news" / "news.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
KEEP = 80                  # items kept in news.json
SHOW_DAYS = 180            # older notices stay in news.json but leave the pages
PAGES = {"all": ("exams.html", 8), "FMGE": ("exam-fmge.html", 5), "NEET-PG": ("exam-neet-pg.html", 5),
         "INI-CET": ("exam-ini-cet.html", 5)}
#: UPSC CMS news is PARKED (his call, 8 Nov: build the CMS bank first; upsc.gov.in also refuses GitHub's servers)


def now() -> dt.datetime:
    return dt.datetime.now(IST)


DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def clean(t: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("�", "–")
    t = re.sub(r"\s+", " ", t).strip()
    if DEVANAGARI.search(t):                 # NBEMS posts "Hindi / English": keep the English half
        parts = [x.strip() for x in t.split(" / ") if x.strip() and not DEVANAGARI.search(x)]
        t = parts[-1] if parts else ""       # a Hindi-only row has an English twin of its own
    return t.rstrip(".").strip()


def get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=40)
    r.raise_for_status()
    return r.content.decode("utf-8", errors="replace")


def which_exam(title: str) -> str | None:
    if re.search(r"NEET[- ]?(SS|MDS)|DNB|FDST|GPAT|INI[- ]?SS", title, re.I):
        return None
    if re.search(r"\bFMGE\b|Foreign Medical Graduate", title, re.I):
        return "FMGE"
    if re.search(r"NEET[- ]?PG", title, re.I):
        return "NEET-PG"
    if re.search(r"INI[- ]?CET", title, re.I):
        return "INI-CET"
    if re.search(r"Combined Medical Services|\bCMSE?\b", title, re.I):
        return "UPSC CMS"
    return None


def nbems() -> list[dict]:
    s = get("https://www.natboard.edu.in/deptnotice")
    out = []
    for d, href, t in re.findall(r'<td[^>]*>(\d{4}-\d{2}-\d{2})</td>\s*<td[^>]*><a href="([^"]+)"[^>]*>(.*?)</a>', s, re.S):
        t = clean(t)
        ex = which_exam(t) if t else None
        if ex in ("FMGE", "NEET-PG"):
            out.append({"exam": ex, "title": t, "date": d, "source": "NBEMS",
                        "url": urllib.parse.urljoin("https://www.natboard.edu.in/", href)})
    if not re.search(r"\d{4}-\d{2}-\d{2}", s):
        raise RuntimeError("no dated rows - page layout changed?")
    return out


def aiims() -> list[dict]:
    """Two AIIMS lists: the home page's "Results & Announcements" (where the INI-CET result goes - found 8 Nov:
    it never appears in the notice list) and page 1 of the notice list. Both print "Published: <date>"."""
    from playwright.sync_api import sync_playwright
    pages = ("https://www.aiimsexams.ac.in/", "https://www.aiimsexams.ac.in/landingpage/notice")
    out, seen_rows = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA)
        for page_url in pages:
            pg.goto(page_url, wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(3000)
            rows = re.findall(r"\n([^\n]{12,400})\n(?:notifications|download)\s*\n\s*calendar_today\s*\n"
                              r"Published: (\d{1,2} \w+ \d{4})", pg.inner_text("body"))
            seen_rows += len(rows)
            for t, d in rows:
                t = clean(t)
                if which_exam(t) == "INI-CET":
                    day = dt.datetime.strptime(d, "%d %B %Y").date().isoformat()
                    out.append({"exam": "INI-CET", "title": t, "date": day, "source": "AIIMS", "url": page_url})
        b.close()
    if not seen_rows:
        raise RuntimeError("no dated rows on either page - layout changed?")
    return out


def upsc() -> list[dict]:
    s = get("https://upsc.gov.in/whats-new")
    out = []
    for href, t in re.findall(r'<a href="(/whats-new/[^"]+)"[^>]*>(.*?)</a>', s, re.S):
        t = clean(t)
        if which_exam(t) == "UPSC CMS":
            out.append({"exam": "UPSC CMS", "title": t, "date": None, "source": "UPSC",
                        "url": "https://upsc.gov.in" + href})
    if "/whats-new/" not in s:
        raise RuntimeError("no notices found - page layout changed?")
    return out


def mcc() -> list[dict]:
    s = get("https://mcc.nic.in/pg-medical-counselling/")
    i = s.find("Current Events")
    if i < 0:
        raise RuntimeError("no Current Events list - page layout changed?")
    out = []
    for href, t in re.findall(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', s[i:i + 20000], re.S):
        t = clean(t)
        m = re.search(r"/(20\d{6})\d*\.pdf$", href)
        d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else None
        if t:
            out.append({"exam": "NEET-PG", "title": f"PG counselling: {t}", "date": d, "source": "MCC", "url": href})
    return out


EVENT = r"result|admit card|scorecard|answer key|exam date|schedule|counsell?ing|registration|application|cut[- ]?off|postpone|declared|released"
QUERIES = {"FMGE": "FMGE", "NEET-PG": '"NEET PG"', "INI-CET": '"INI CET"', "UPSC CMS": '"UPSC CMS"'}


def headlines() -> list[dict]:
    """Fresh news-site headlines about an exam event (last 2 days). Cross-check only - never published."""
    out = []
    for ex, q in QUERIES.items():
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{q} when:2d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        for it in ET.fromstring(get(url)).iter("item"):
            t = clean(it.findtext("title") or "")
            if re.search(EVENT, t, re.I):
                out.append({"exam": ex, "title": t, "url": it.findtext("link") or "",
                            "date": it.findtext("pubDate") or ""})
    return out


def key(it: dict) -> str:
    return hashlib.sha1(f"{it['source']}|{it['title'].lower()}".encode()).hexdigest()[:12]


def words(t: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", t.lower())} - {"2025", "2026", "2027", "exam", "examination", "notice"}


def render(store: dict) -> list[str]:
    since = (now().date() - dt.timedelta(days=SHOW_DAYS)).isoformat()
    items = [i for i in store["items"] if not i.get("hidden") and i["date"] >= since]
    items.sort(key=lambda i: (i["date"] or "", i["first_seen"]), reverse=True)
    changed = []
    for exam, (page, n) in PAGES.items():
        show = [i for i in items if exam == "all" or i["exam"] == exam][:n]
        li = "\n".join(
            f'<li><time datetime="{i["date"]}">{dt.date.fromisoformat(i["date"]).strftime("%d %b %Y").lstrip("0")}</time>'
            + (f'<span class="news-exam">{i["exam"]}</span>' if exam == "all" else "")
            + f'<a href="{html.escape(i["url"])}" rel="noopener" target="_blank">{html.escape(i["title"])}</a>'
            + f'<span class="news-src">{i["source"]}</span></li>' for i in show)
        body = (f'<ul class="news-list">\n{li}\n</ul>' if show else '<p class="news-none">No new official notice yet.</p>')
        block = (f'<!--NEWS:{exam}-->\n<section class="news" aria-labelledby="news-{PAGES[exam][0][:-5]}">\n'
                 f'<h2 id="news-{PAGES[exam][0][:-5]}">Latest official notices</h2>\n{body}\n'
                 f'<p class="news-note">Straight from NBEMS, MCC and AIIMS, each linked to the original. '
                 f'Read every 3 hours.</p>\n</section>\n<!--/NEWS-->')
        f = SITE / page
        s = f.read_text(encoding="utf-8")
        new = re.sub(rf"<!--NEWS:{re.escape(exam)}-->.*?<!--/NEWS-->", lambda _: block, s, flags=re.S)
        if new == s and f"<!--NEWS:{exam}-->" not in s:
            raise SystemExit(f"{page}: no <!--NEWS:{exam}--> marker")
        if new != s:
            f.write_text(new, encoding="utf-8")
            changed.append(page)
    return changed


def signature(store: dict) -> str:
    return json.dumps([[i["id"] for i in store["items"]],
                       {n: (s.get("ok"), s.get("failing_since")) for n, s in store["sources"].items()}])


def main() -> int:
    store = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {"items": [], "sources": {}}
    before = signature(store)
    if "--offline" in sys.argv:
        print("rendered:", render(store))
        return 0
    seeding = not store["items"]
    today = now().date().isoformat()
    have = {i["id"]: i for i in store["items"]}
    seen = set(store.get("seen", [])) | set(have)   # every id ever read - an old notice that fell off the
                                                    # 80 kept is NOT new when the board still lists it
    found, new = [], []
    # UPSC is OFF on GitHub: upsc.gov.in times out from GitHub's (US) servers every run (8 Nov, two runs) - it reads
    # fine from India. Turn it back on (add ("UPSC", upsc)) only from a runner that can reach it.
    for name, fn in (("NBEMS", nbems), ("AIIMS", aiims), ("MCC", mcc)):
        try:
            got = fn()
            store["sources"][name] = {"ok": True, "at": now().isoformat(timespec="minutes"), "found": len(got)}
            found += got
        except Exception as e:                       # one broken source never stops the others
            prev = store["sources"].get(name, {})
            store["sources"][name] = {"ok": False, "at": now().isoformat(timespec="minutes"),
                                      "error": str(e)[:200], "failing_since": prev.get("failing_since") or today}
    for it in found:
        it["id"] = key(it)
        if it["id"] in have or it["id"] in seen:
            continue
        it["first_seen"] = today
        if it["date"] is None:                       # UPSC (and an odd MCC file): no date on the site
            it["date"] = today
            it["hidden"] = seeding                   # never show an old notice with a made-up date
        it["posted"] = seeding                       # the bot announces only what is new after the first run
        store["items"].append(it)
        have[it["id"]] = it
        new.append(it)
    store["items"].sort(key=lambda i: (i["date"], i["first_seen"]), reverse=True)
    store["items"] = store["items"][:KEEP]
    store["seen"] = sorted(seen | {i["id"] for i in found})
    # cross-check: news headlines with no official notice of the same exam in the last 4 days
    try:
        recent = [i for i in store["items"]
                  if (now().date() - dt.date.fromisoformat(i["date"])).days <= 4]
        store["unconfirmed"] = [h for h in headlines()
                                if not any(i["exam"] == h["exam"] and len(words(i["title"]) & words(h["title"])) >= 2
                                           for i in recent)][:20]
    except Exception as e:
        store["unconfirmed_error"] = str(e)[:200]
    store["checked"] = now().isoformat(timespec="minutes")
    # write only when a notice or a source's health changed: a timestamp alone would republish the site 8x a day
    changed = []
    if signature(store) != before:
        STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        changed = render(store)
    bad = [f"{n}: {s.get('error')}" for n, s in store["sources"].items() if not s.get("ok")]
    print(f"{'SEEDED' if seeding else 'new'}: {len(new)} · shown: {sum(1 for i in store['items'] if not i.get('hidden'))}"
          f" · unconfirmed headlines: {len(store.get('unconfirmed', []))} · pages: {changed or 'none'}")
    for i in new[:20]:
        print(f"  + {i['date']} [{i['exam']}] {i['title'][:100]}")
    for b in bad:
        print("  ! source failing -", b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
