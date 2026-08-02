#!/usr/bin/env python
"""Regenerate the site's numbers and the public fixes log.

Run before pushing:  python sync_site.py          (writes)
                     python sync_site.py --check   (CI-style, writes nothing)

⚠⚠ WHY THIS EXISTS. On 2 Aug 2026 FOUR separate hardcoded numbers were wrong at
the same time — the site said "3,300+" and "310 image questions", the bot
welcome said "3,300+", and the paywall quoted a ₹150 plan that no longer
existed. Two of those had ALREADY been corrected elsewhere and drifted back.
A number that lives in two places drifts; this makes study.db the only source.

⚠ Counts here MUST match what the bot actually serves, not what the table
holds. 3,323 rows exist, 3,233 are servable: 89 image questions have no
uploaded figure and 1 is quarantined. Advertising 3,323 would be a lie a user
could catch.
"""
from __future__ import annotations
import json, re, sqlite3, sys, datetime, pathlib

HERE = pathlib.Path(__file__).parent
DB = HERE.parent / "ciel_study_bot" / "study.db"
CHECK = "--check" in sys.argv

# The bot's own serving filter, copied deliberately rather than imported: this
# script must keep working if the site is ever split from the bot repo.
ANSWERABLE = ("(has_image=0 OR (image_file_id IS NOT NULL AND image_file_id!=''))"
              " AND (vetted IS NULL OR vetted<>0)")
IBQ = "(has_image=1 AND image_file_id IS NOT NULL AND image_file_id!='')"


def counts() -> dict:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = lambda s: c.execute(s).fetchone()[0]
    d = {
        "servable":  q(f"SELECT COUNT(*) FROM questions WHERE {ANSWERABLE}"),
        "subjects":  q("SELECT COUNT(DISTINCT subject) FROM questions"),
        "figures":   q(f"SELECT COUNT(*) FROM questions WHERE {IBQ}"),
        "held_back": q("SELECT COUNT(*) FROM questions WHERE has_image=1 AND "
                       "(image_file_id IS NULL OR image_file_id='')"),
    }
    c.close()
    # Round DOWN for copy. Rounding up would overstate, which is the whole
    # failure mode this script exists to prevent.
    d["round"] = f"{d['servable'] // 100 * 100:,}+"
    return d


def sync_stats(n: dict) -> list[str]:
    """Rewrite every derived number on the site. Returns a list of changes."""
    changed = []
    idx = HERE / "index.html"
    s = old = idx.read_text(encoding="utf-8")

    # Machine-readable markers first — these cannot mangle prose.
    for key, val in (("questions", n["round"]), ("subjects", str(n["subjects"])),
                     ("figures", str(n["figures"]))):
        s = re.sub(rf'(<b data-stat="{key}">)[^<]*(</b>)', rf'\g<1>{val}\g<2>', s)

    # Prose, each anchored tightly enough that it cannot match anything else.
    s = re.sub(r"\b\d{1,3},\d00\+ (MCQs|previous-year)", lambda m: f"{n['round']} {m.group(1)}", s)
    s = re.sub(r"<p>\d+ questions that carry the actual figure",
               f"<p>{n['figures']} questions that carry the actual figure", s)
    s = re.sub(r"Around \d+ image-based\n?\s*questions are still held back",
               f"Around {n['held_back']} image-based\n      questions are still held back", s)
    if s != old:
        if not CHECK:
            idx.write_text(s, encoding="utf-8", newline="\n")
        changed.append("index.html")
    return changed


# ── public fixes log ─────────────────────────────────────────────────────────
#
# ⚠ PRIVACY: entries are written by hand and must NEVER name a reporter, quote
# their message, or carry a Telegram id. The point is to show that reports get
# fixed, not to expose who reported.
FIXES_JSON = HERE / "fixes.json"

FIXES_TEMPLATE = """<h2>{year}</h2>
<div class="table-scroll"><table>
<tr><th>Date</th><th>Area</th><th>What changed</th><th>Status</th></tr>
{rows}
</table></div>
"""


def render_fixes() -> list[str]:
    if not FIXES_JSON.exists():
        return []
    data = json.loads(FIXES_JSON.read_text(encoding="utf-8"))
    entries = sorted(data.get("fixes", []), key=lambda e: e.get("date", ""), reverse=True)
    by_year: dict[str, list] = {}
    for e in entries:
        by_year.setdefault((e.get("date") or "----")[:4], []).append(e)

    blocks = []
    for year in sorted(by_year, reverse=True):
        rows = "\n".join(
            "<tr><td>{d}</td><td>{a}</td><td>{w}</td><td>{s}</td></tr>".format(
                d=_esc(e.get("date", "")), a=_esc(e.get("area", "")),
                w=_esc(e.get("what", "")),
                s=("✅ " if e.get("status") == "fixed" else "⏳ ") + _esc(e.get("status", "")))
            for e in by_year[year])
        blocks.append(FIXES_TEMPLATE.format(year=year, rows=rows))

    # ── what's next ──────────────────────────────────────────────────────────
    # ⚠ NO DATES, deliberately. A missed date on a public page is a promise
    # broken in writing; "planned" with no date is a direction, not a contract.
    planned = data.get("planned", [])
    if planned:
        rows = "\n".join(
            "<tr><td>{a}</td><td>{w}</td></tr>".format(
                a=_esc(e.get("area", "")), w=_esc(e.get("what", "")))
            for e in planned)
        nxt = ("<h2>What's next</h2>\n"
               "<p>Things I intend to build. No dates — I would rather ship them than "
               "promise a day and miss it.</p>\n"
               '<div class="table-scroll"><table>\n'
               "<tr><th>Area</th><th>What</th></tr>\n" + rows + "\n</table></div>\n")
    else:
        nxt = ""

    page = (HERE / "_fixes_shell.html").read_text(encoding="utf-8")
    out = page.replace("<!--FIXES-->", "\n".join(blocks)) \
              .replace("<!--PLANNED-->", nxt) \
              .replace("<!--COUNT-->", str(len(entries))) \
              .replace("<!--UPDATED-->", datetime.date.today().strftime("%d %B %Y"))
    target = HERE / "fixes.html"
    if not target.exists() or target.read_text(encoding="utf-8") != out:
        if not CHECK:
            target.write_text(out, encoding="utf-8", newline="\n")
        return ["fixes.html"]
    return []


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


if __name__ == "__main__":
    n = counts()
    print(f"study.db -> servable {n['servable']} ({n['round']}), "
          f"{n['subjects']} subjects, {n['figures']} figures, {n['held_back']} held back")
    changed = sync_stats(n) + render_fixes()
    if CHECK:
        print("OUT OF DATE:" if changed else "up to date ✅", ", ".join(changed))
        sys.exit(1 if changed else 0)
    print("rewrote:", ", ".join(changed) if changed else "(nothing — already current)")
