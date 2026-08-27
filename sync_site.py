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


#: ⚠ Reads ONE key out of the bot's .env and nothing else. That file holds live
#: payment keys and the webhook secret; this must never copy anything from it
#: onto a public page.
ENV = HERE.parent / "ciel_study_bot" / ".env"


def free_per_day() -> int | None:
    """The bot's real free daily allowance, or None if it can't be read.

    ⚠ Returns None rather than guessing. This number was hardcoded in ELEVEN
    places across the site and README; when the bot went from 3/day to 5/day on
    4 Aug, every one of them became a lie a user could catch in ten seconds.
    Writing a DEFAULT here would recreate exactly that failure quietly."""
    try:
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("FREE_PER_DAY="):
                return int(line.partition("=")[2].strip())
    except Exception:
        pass
    return None


_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
          6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}

#: ⚠⚠⚠ CURATED WHOLE PHRASES, NOT A PATTERN. THIS IS NOT A STYLE CHOICE.
#: The first version of this matched a number followed by "question(s)", which
#: looked tight and was not. In one run it rewrote:
#:    "fewer than 25 questions"      -> "fewer than 5"   (THE REFUND POLICY)
#:    "10, 25 or 50 question tests"  -> "or 5 question tests"
#:    "221 questions that carry the actual figure" -> "5 questions..."
#:    "One question at a time"       -> "5 question at a time"
#: A published refund commitment was silently altered. Reverted before pushing.
#: A curated map CANNOT do that — its only failure mode is "a phrase we missed",
#: never "a phrase we destroyed". Same conclusion the question-bank sweep
#: reached about medical text: when a transform touches text that matters,
#: hand-curation beats any heuristic.
#: {n} is the allowance; everything else must match literally.
_FREE_PHRASES = (
    "{n} free questions a day, forever.",
    "{n} free a day, forever.",
    '<p class="cta-note">{n} questions a day, free forever.',
    "<p>{n} free questions every day, forever.",
    "<h3>{n} questions every day</h3>",
    '<p class="per">{n} questions a day, forever</p>',
    "<p>Yes &mdash; {n} questions every day, indefinitely,",
    "<p>Yes — {n} questions every day, indefinitely,",
    "<h2>Start with {w} questions.</h2>",
    "<strong>Free &mdash; {n} questions per day, indefinitely.</strong>",
    "<strong>Free — {n} questions per day, indefinitely.</strong>",
    "you can practise {n} questions a day free of charge,",
    "| Free | ₹0 | {n} questions per day, indefinitely |",
)

_ANY_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"


def _sync_free(text: str, n: int) -> str:
    """Set the free-tier allowance in each KNOWN phrase. Nothing else moves."""
    word = _WORDS.get(n, str(n))
    for tpl in _FREE_PHRASES:
        pattern = re.escape(tpl).replace(r"\{n\}", _ANY_NUM).replace(r"\{w\}", _ANY_NUM)
        text = re.sub(pattern, tpl.format(n=n, w=word), text, flags=re.I)
    return text


#: ⚠⚠ THE TWO SITE BUILDERS WERE OVERWRITING EACH OTHER, AND THE CASUALTY WAS
#: THE ONE GUARD THAT KEEPS THE NUMBERS HONEST. `fixes.html` and `support.html`
#: are GENERATED here from a shell plus JSON, while `seo_build.py` INJECTS a
#: schema block into the finished file between `<!--SEO:start-->` and
#: `<!--SEO:end-->`. So a normal build left `sync_site.py --check` permanently
#: reporting OUT OF DATE — sync regenerating without the block, seo re-adding
#: it, forever. A check that is red in the shipped state is a check nobody can
#: use, which is exactly how the four simultaneously-wrong numbers of 2 August
#: got there. Regeneration now CARRIES THE EXISTING BLOCK ACROSS, so the two
#: scripts are order-independent and --check means something again.
SEO_START, SEO_END = "<!--SEO:start-->", "<!--SEO:end-->"


def _keep_seo(target: pathlib.Path, out: str) -> str:
    """Carry any existing SEO block from `target` into freshly generated `out`."""
    if SEO_START in out or not target.exists():
        return out
    live = target.read_text(encoding="utf-8")
    i, j = live.find(SEO_START), live.find(SEO_END)
    if i < 0 or j < i:
        return out
    block = live[i:j + len(SEO_END)]
    # The block belongs in <head>; seo_build puts it immediately before </head>.
    k = out.lower().find("</head>")
    if k < 0:
        return out
    return out[:k] + block + "\n" + out[k:]


_HELD_SOME = ("Around {k} image-based\n      questions are still held back because I "
              "couldn't read the figure well enough to\n      be certain, and they stay "
              "out until I can.")
_HELD_NONE = ("Every image-based question in the bank right now carries its own "
              "figure.\n      Where I couldn't read one well enough to be certain, the "
              "question stays out\n      of the bank rather than going in without it.")
#: Matches whichever of the two sentences is currently on the page, so the copy
#: can move between them in either direction and never end up with both.
_HELD_ANY = re.compile(
    r"Around \d+ image-based\s*questions are still held back because I couldn't read "
    r"the figure well enough to\s*be certain, and they stay out until I can\."
    r"|Every image-based question in the bank right now carries its own figure\.\s*"
    r"Where I couldn't read one well enough to be certain, the question stays out\s*"
    r"of the bank rather than going in without it\.",
    re.S)


def _sync_held_back(text: str, k: int) -> str:
    return _HELD_ANY.sub(lambda _m: (_HELD_NONE if not k else _HELD_SOME.format(k=k)), text)


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
    d["free_per_day"] = free_per_day()
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
    # ⚠⚠ "AROUND 0 IMAGE-BASED QUESTIONS ARE STILL HELD BACK" WENT LIVE ON THIS
    #   PAGE. The count is a real number that reached zero, and the sentence
    #   built around it stopped being English — inside the one paragraph whose
    #   whole subject is that these numbers are honest. ⇒ A SYNCED NUMBER NEEDS
    #   A SENTENCE FOR EVERY VALUE IT CAN TAKE, AND ZERO IS ALWAYS ONE OF THEM.
    #   Both forms are curated whole sentences, per the rule above the phrase map.
    s = _sync_held_back(s, n["held_back"])
    fpd = n.get("free_per_day")
    if fpd:
        s = _sync_free(s, fpd)
    if s != old:
        if not CHECK:
            idx.write_text(s, encoding="utf-8", newline="\n")
        changed.append("index.html")

    # The free allowance is quoted on the policy pages and the README too.
    # ⚠ These pages are REVIEWED POLICY TEXT — only the number may move, so each
    # write is checked for an unchanged length-of-prose beyond the digits.
    if fpd:
        for name in ("pricing.html", "refunds.html", "README.md"):
            f = HERE / name
            if not f.exists():
                continue
            before = f.read_text(encoding="utf-8")
            after = _sync_free(before, fpd)
            if after != before:
                if not CHECK:
                    f.write_text(after, encoding="utf-8", newline="\n")
                changed.append(name)
    return changed


# ── public fixes log ─────────────────────────────────────────────────────────
#
# ⚠ PRIVACY: entries are written by hand and must NEVER name a reporter, quote
# their message, or carry a Telegram id. The point is to show that reports get
# fixed, not to expose who reported.
FIXES_JSON = HERE / "fixes.json"

FIXES_TEMPLATE = """<h3>{year}</h3>
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

    # ── what's next (one roadmap) ────────────────────────────────────────────
    # ⚠ ONE section, not two. This was "Milestones" AND "What's next" until
    # 4 Aug, and four of the six planned items were already milestones — the
    # same facts written twice, which is the exact drift this whole file exists
    # to prevent. Merged at Nawar's call.
    # ⚠ NO DATES, deliberately: a missed date on a public page is a promise
    # broken in writing. Each item is gated on a CONDITION instead, which is
    # both honest and checkable.
    # ⚠ Never publish customer counts or revenue here. "When running costs are
    # covered" says what matters without turning the page into a balance sheet.
    planned = data.get("planned", [])
    if planned:
        rows = "\n".join(
            "<tr><td>{s}</td><td><b>{g}</b><br><span class=\"fine\">{w}</span></td>"
            "<td>{u}</td></tr>".format(
                s={"done": "✅", "building": "🔨", "next": "⏭"}.get(e.get("status"), "•"),
                g=_esc(e.get("goal", "")), w=_esc(e.get("why", "")),
                u=_esc(e.get("when", "")))
            for e in planned)
        nxt = ("<h2>What's next</h2>\n"
               "<p>What I'm building, and what each one is waiting on. No dates "
               "&mdash; I would rather ship something than promise a day and miss "
               "it.</p>\n"
               '<div class="table-scroll"><table>\n'
               "<tr><th></th><th>Goal</th><th>Happens when</th></tr>\n"
               + rows + "\n</table></div>\n")
    else:
        nxt = ""
    mstone = ""          # section merged into "What's next"

    page = (HERE / "_fixes_shell.html").read_text(encoding="utf-8")
    out = page.replace("<!--FIXES-->", "\n".join(blocks)) \
              .replace("<!--MILESTONES-->", mstone) \
              .replace("<!--PLANNED-->", nxt) \
              .replace("<!--COUNT-->", str(len(entries))) \
              .replace("<!--UPDATED-->", datetime.date.today().strftime("%d %B %Y"))
    target = HERE / "fixes.html"
    out = _keep_seo(target, out)
    if not target.exists() or target.read_text(encoding="utf-8") != out:
        if not CHECK:
            target.write_text(out, encoding="utf-8", newline="\n")
        return ["fixes.html"]
    return []


def donate_url() -> str | None:
    """The Razorpay payment link for voluntary contributions, or None.

    ⚠ Returns None rather than a guess, exactly like free_per_day(). A donate
    button pointing at a dead or wrong URL is worse than no button: the person
    who taps it either loses money into the wrong account or concludes the
    product is broken at the moment they were feeling generous.
    ⚠ This reads ONE key and copies no secret onto a public page. A Razorpay
    PAYMENT LINK is public by design — it is the thing you send to a payer —
    unlike the API keys and webhook secret that live in the same file.
    """
    try:
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DONATE_URL="):
                v = line.partition("=")[2].strip().strip('"').strip("'")
                if v.startswith("https://"):
                    return v
    except Exception:
        pass
    return None


def render_support() -> list[str]:
    """support.html — the voluntary-contribution page.

    ⚠ NO AMOUNT IS SUGGESTED ANYWHERE. A default of "₹500" turns a gift into a
    price, and the moment it reads as a price a contributor reasonably expects
    something back — which is the one thing this page promises not to give.
    Razorpay's own page collects whatever the payer chooses.
    """
    url = donate_url()
    if url:
        # The button sits inside a .cta-band that already carries the heading
        # and the "any amount, once" line, so this is only the button.
        block = ('<a class="btn btn-primary" href="{u}" rel="noopener">'
                 '❤️ Contribute through Razorpay</a>').format(u=_esc(url))
    else:
        # ⚠ The honest empty state. Publishing a dead button to look finished
        # is how a user loses money or trust; saying "not open yet" costs
        # nothing and is true.
        block = ('<p class="fine">Not open yet — I am still setting the '
                 'payment link up. The free ways to help above matter more '
                 'anyway.</p>')
    page = (HERE / "_support_shell.html").read_text(encoding="utf-8")
    out = page.replace("<!--DONATE_BLOCK-->", block) \
              .replace("<!--CONTRIBUTORS-->", render_contributors()[0]) \
              .replace("<!--UPDATED-->", datetime.date.today().strftime("%d %B %Y"))
    target = HERE / "support.html"
    out = _keep_seo(target, out)
    if not target.exists() or target.read_text(encoding="utf-8") != out:
        if not CHECK:
            target.write_text(out, encoding="utf-8", newline="\n")
        return ["support.html"]
    return []


def render_contributors() -> list[str]:
    """The Credits list on the support page, from contributors.json.

    ⚠⚠ CONSENT, NOT CONVENIENCE. Names go in that file only after the person has
    said yes in the bot. The standing rule everywhere else in this product is that
    one person never learns another's identity from it, and this page is the single
    deliberate exception — so it is opt-in, per person, and the page says so.
    ⚠ No amount, no plan, no ranking. "Paid for a month of the server" is as
    specific as money is ever allowed to get here; a list ordered by rupees turns
    a thank-you into a leaderboard.
    ⚠ The EMPTY STATE IS HONEST AND SHIPS. An invented placeholder name, or a
    real name lifted from the users table, would both be worse than a short list.
    """
    src = HERE / "contributors.json"
    people = []
    if src.exists():
        try:
            people = json.loads(src.read_text(encoding="utf-8")).get("credits", [])
        except Exception as e:
            print(f"⚠ contributors.json unreadable ({e}) — rendering empty")
    if people:
        rows = "\n".join(
            '  <li><strong>{}</strong>{}</li>'.format(
                _esc(p.get("name", "").strip() or "anonymous"),
                (" — " + _esc(p["for"])) if p.get("for") else "")
            for p in people)
        block = f'<ul class="plan-list">\n{rows}\n</ul>'
    else:
        block = ('<p class="fine">Nobody is listed yet. Several people have '
                 'already reported wrong keys and mangled text — I have not asked '
                 'them yet whether they want naming, and I will not add anyone '
                 'before I do.</p>')
    return [block]


def render_milestones(n: dict) -> list[str]:
    """The home page's milestone band, from milestones.json + the live count.

    ⚠ HISTORY FROM THE FILE, THE CURRENT NUMBER FROM THE DATABASE. That split is
    the point: a past milestone is a fixed fact and belongs in version control, but
    "how many questions now" moves every session and must never be typed into HTML.
    ⚠ It deliberately does NOT duplicate fixes.html. That page answers "what changed
    and what is next"; this band answers "how far has this come". If a milestone
    starts explaining a fix, it belongs on the other page.
    """
    src = HERE / "milestones.json"
    if not src.exists():
        return []
    try:
        items = json.loads(src.read_text(encoding="utf-8")).get("milestones", [])
    except Exception as e:
        print(f"⚠ milestones.json unreadable ({e}) — band left untouched")
        return []
    items = sorted(items, key=lambda m: m.get("date", ""), reverse=True)
    lis = []
    for m in items:
        try:
            when = datetime.date.fromisoformat(m["date"]).strftime("%d %b %Y")
        except Exception:
            when = _esc(m.get("date", ""))
        note = f'<span>{_esc(m["note"])}</span>' if m.get("note") else ""
        lis.append(f'    <li><b>{_esc(m.get("label",""))}</b>'
                   f'<time>{when}</time>{note}</li>')
    block = ("\n".join([
        '  <p class="eyebrow">How far this has come</p>',
        f'  <h2>{n["round"]} questions today, from a few hundred in July</h2>',
        '  <p class="lede">Small numbers, honestly counted. Every figure here is '
        'read out of the live database, not typed in.</p>',
        '  <ol class="milestones">',
        *lis,
        '  </ol>',
    ]))
    idx = HERE / "index.html"
    s = old = idx.read_text(encoding="utf-8")
    pat = re.compile(r"(<!--MILESTONES:START-->).*?(<!--MILESTONES:END-->)", re.S)
    if not pat.search(s):
        print("⚠ index.html has no MILESTONES markers — band not injected")
        return []
    s = pat.sub(lambda _m: f"<!--MILESTONES:START-->\n{block}\n  <!--MILESTONES:END-->", s)
    if s != old:
        if not CHECK:
            idx.write_text(s, encoding="utf-8", newline="\n")
        return ["index.html (milestones)"]
    return []


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


if __name__ == "__main__":
    n = counts()
    print(f"study.db -> servable {n['servable']} ({n['round']}), "
          f"{n['subjects']} subjects, {n['figures']} figures, {n['held_back']} held back")
    print(f".env     -> free tier {n['free_per_day']}/day"
          if n.get("free_per_day") else
          "⚠ .env unreadable - free-tier numbers left untouched")
    print(f".env     -> donate link " + ("configured" if donate_url() else "NOT SET (support page will say 'not open yet')"))
    changed = (sync_stats(n) + render_fixes() + render_support()
               + render_milestones(n))
    if CHECK:
        # ⚠ ASCII ONLY ON THIS LINE. It used to print a tick emoji and crashed with
        # UnicodeEncodeError under Windows' cp1252 console — after having already
        # done all the work, so --check could not be used as a gate at all. The
        # project has hit this before (see the state file's note about setting
        # PYTHONIOENCODING), and requiring an environment variable to read your own
        # tool's output is not a fix.
        print("OUT OF DATE:" if changed else "up to date [ok]", ", ".join(changed))
        sys.exit(1 if changed else 0)
    print("rewrote:", ", ".join(changed) if changed else "(nothing — already current)")
