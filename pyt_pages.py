# -*- coding: utf-8 -*-
"""pyt_pages.py - one public page per subject: its previous-year topics (PYTs), most-asked first.  0.1.0

27 Nov 2026 (Nawar's idea): students search "FMGE <subject> PYTs / PYQs". Each page lists the subject's exam
topics with a short key point, how many past questions the bank has on it, and one real past question with its
answer, then links into the bot. Search engines and AI assistants can read and quote it; the full questions stay
in the bot.

    python pyt_pages.py            build every subject that has pyt_notes/<slug>.json
    python pyt_pages.py --check    say what would change, write nothing

Where things come from - nothing here is typed twice:
  topic names, ranks, marks, counts  study.db  (pyt_topics, mcq_pyt; same tables the bot's "Revise" block reads)
  sample question                    study.db  questions (id chosen in the notes file; FMGE recalls, no images)
  key point + one-line why           pyt_notes/<slug>.json  (hand-written and reviewed by the lead)
A topic without a note is still listed (name, badges, count), just without the key point.

Public-text rules: no source names (never "Ed8", no coaching names), no counts of payers or money.
"""
from __future__ import annotations
import datetime, html, json, re, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "ciel_study_bot" / "study.db"
BASE = "https://ammysterious.github.io/ciel_study"
BOT = "https://t.me/Ciel_Study_bot"
CHECK = "--check" in sys.argv

RANK = {3: ("Must-do", "must"), 2: ("High-yield", "hy"), 1: ("Asked", "asked")}
EXAMS = (("F", "FMGE"), ("N", "NEET-PG"), ("I", "INI-CET"))
e = lambda s: html.escape(str(s), quote=True)


def start_tag(topic_id: str) -> str:
    """t.me start payloads allow A-Z a-z 0-9 _ - and 64 chars; the bot keeps 32 as the source."""
    return ("pyt_" + re.sub(r"[^A-Za-z0-9_-]", "_", topic_id))[:32]


def load(subject: str):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute(
        "SELECT t.id, t.section, t.topic, t.rank, COALESCE(t.marks,''), t.ord FROM pyt_topics t "
        "WHERE t.subject=? AND t.rank BETWEEN 1 AND 3 ORDER BY t.ord", (subject,)).fetchall()
    qids = {r[0]: {q for (q,) in c.execute("SELECT mcq_id FROM mcq_pyt WHERE topic_id=?", (r[0],))} for r in rows}
    return c, rows, qids


def sample(c, qid):
    r = c.execute("SELECT question, option_a, option_b, option_c, option_d, correct FROM questions WHERE id=?",
                  (qid,)).fetchone()
    if not r:
        return None
    stem, *opts, key = r
    return stem.strip(), [o.strip() for o in opts], "abcd".index(key.strip().lower())


def badges(rank, marks):
    out = []
    if rank in RANK:
        label, cls = RANK[rank]
        out.append(f'<span class="b b-{cls}">{label}</span>')
    if "R" in marks:
        out.append('<span class="b b-rep">Repeated</span>')
    ex = [n for k, n in EXAMS if k in marks]
    if ex:
        out.append(f'<span class="b b-ex">{" · ".join(ex)}</span>')
    return "".join(out)


def build(notes_file: Path) -> tuple[str, str]:
    N = json.loads(notes_file.read_text(encoding="utf-8"))
    subject, slug, notes = N["subject"], N["slug"], N["topics"]
    c, rows, qids = load(subject)

    # group rows into sections, keeping the bank's order; a section row with no topic name only adds questions
    sections, order = {}, []
    for tid, sec, topic, rank, marks, _ in rows:
        sec = sec or subject
        if sec not in sections:
            sections[sec] = {"rank": rank, "marks": marks, "ids": set(), "topics": []}
            order.append(sec)
        S = sections[sec]
        S["ids"] |= qids[tid]
        S["rank"] = max(S["rank"], rank)
        if topic:
            S["topics"].append((tid, topic, rank, marks, len(qids[tid])))
        elif tid in notes:                      # a whole-section topic (e.g. "Most repeated antidotes")
            S["topics"].append((tid, sec, rank, marks, len(qids[tid])))
    # most-asked first: rank, then how many past questions
    order.sort(key=lambda s: (-sections[s]["rank"], -len(sections[s]["ids"])))
    total = len(set().union(*qids.values())) if qids else 0
    n_topics = sum(len(sections[s]["topics"]) for s in order)

    today = datetime.date.today()
    stamp = f"{today.day} {today:%b %Y}"
    title = f"FMGE {subject} previous year topics (PYTs) with key points"
    desc = (f"All {n_topics} {subject} topics asked in FMGE, NEET-PG and INI-CET, most-asked first, each with the key "
            f"point to remember and a real past question with its answer. {total:,} {subject} questions to practise "
            f"free on Telegram.")
    url = f"{BASE}/pyt-{slug}.html"

    body, quiz = [], []
    for s in order:
        S = sections[s]
        if not S["topics"]:
            continue
        body.append(f'<section class="sec" id="{e(re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-"))}">')
        body.append(f'<h2>{e(s)} <small>{len(S["ids"]):,} questions</small></h2>')
        for tid, topic, rank, marks, n in S["topics"]:
            note = notes.get(tid, {})
            body.append('<article class="topic">')
            body.append(f'<h3>{e(topic)}</h3><p class="badges">{badges(rank, marks)}'
                        f'<span class="n">{n:,} past questions</span></p>')
            if note.get("note"):
                body.append(f'<p class="key">{e(note["note"])}</p>')
            q = sample(c, note["sample"]) if note.get("sample") else None
            if q:
                stem, opts, k = q
                ans = ' class="ans"'
                lis = "".join(f'<li{ans if i == k else ""}><b>{"ABCD"[i]}.</b> {e(o)}</li>'
                              for i, o in enumerate(opts))
                why = f'<p class="why"><b>Answer: {"ABCD"[k]}.</b> {e(note.get("why", ""))}</p>'
                body.append(f'<details class="pq"><summary>Try a past question</summary><p class="stem">{e(stem)}</p>'
                            f'<ol class="opts">{lis}</ol>{why}</details>')
                quiz.append({"@type": "Question", "name": stem, "eduQuestionType": "Multiple choice",
                             "about": topic,
                             "suggestedAnswer": [{"@type": "Answer", "text": o} for i, o in enumerate(opts) if i != k],
                             "acceptedAnswer": {"@type": "Answer", "text": opts[k],
                                                "answerExplanation": {"@type": "Comment",
                                                                      "text": note.get("why", "")}}})
            body.append(f'<a class="go" href="{BOT}?start={start_tag(tid)}" rel="noopener">'
                        f'Practise {n:,} questions on this, free on Telegram &rarr;</a>')
            body.append('</article>')
        body.append('</section>')
    c.close()

    ld = [{"@context": "https://schema.org", "@type": "Quiz", "name": title, "about": subject,
           "educationalLevel": "Medical licensing exam (FMGE, NEET-PG, INI-CET)", "dateModified": today.isoformat(),
           "hasPart": quiz},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Ciel Study", "item": f"{BASE}/"},
              {"@type": "ListItem", "position": 2, "name": "FMGE previous year topics", "item": f"{BASE}/fmge-previous-year-questions.html"},
              {"@type": "ListItem", "position": 3, "name": subject, "item": url}]}]

    shell = (HERE / "fmge-previous-year-questions.html").read_text(encoding="utf-8")
    head_end = shell.index("<style>")
    head = shell[:head_end]
    head = re.sub(r"<title>.*?</title>", f"<title>{e(title)} — Ciel Study</title>", head, flags=re.S)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + e(title), head)
    head = re.sub(r'(<meta (?:property="og:description"|name="description") content=")[^"]*',
                  lambda m: m.group(1) + e(desc), head)
    top = shell[shell.index("</head>"):shell.index('<main id="main"')]
    foot = shell[shell.index("</main>"):]

    page = (head + STYLE +
            f'<link rel="canonical" href="{url}">\n<meta property="og:url" content="{url}">\n'
            + "\n".join('<script type="application/ld+json">\n' + json.dumps(x, ensure_ascii=False, indent=1)
                        + "\n</script>" for x in ld) + "\n"
            + top +
            f'<main id="main" class="wrap doc guide pyt">\n'
            f'<p class="crumb"><a href="fmge-previous-year-questions.html">FMGE previous year topics</a> &rsaquo; {e(subject)}</p>\n'
            f'<h1>FMGE {e(subject)}: previous year topics</h1>\n'
            f'<p class="lede">{e(N["intro"])}</p>\n'
            f'<ul class="facts"><li><b>{n_topics}</b>topics asked</li><li><b>{total:,}</b>past questions</li>'
            f'<li><b>Free</b>5 a day, no sign-up</li></ul>\n'
            f'<p class="fine">Badges: <span class="b b-must">Must-do</span> asked again and again · '
            f'<span class="b b-hy">High-yield</span> asked often · <span class="b b-rep">Repeated</span> the same '
            f'idea has come back in later papers. A question can belong to more than one topic, so the topic counts '
            f'add up to more than {total:,}. Updated {stamp}, rebuilt from the question bank.</p>\n'
            + "\n".join(body) +
            f'\n<p class="end"><a class="btn btn-primary" href="{BOT}?start=pyt_{slug}" rel="noopener">'
            f'Practise {subject} free on Telegram</a></p>\n' + foot)
    return f"pyt-{slug}.html", page


STYLE = """<style>
.doc.guide { padding-top: 22px; }
.pyt .crumb { font-size: .85rem; margin: 0 0 6px; }
.pyt h1 { margin: 0 0 8px; }
.pyt .lede { margin: 0 0 12px; }
.pyt .facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 0 0 10px; padding: 0; list-style: none; }
.pyt .facts li { margin: 0; padding: 9px 10px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); font-size: .85rem; line-height: 1.25; }
.pyt .facts b { display: block; color: var(--text); font-size: 1.1rem; }
.pyt .sec { margin: 26px 0 0; }
.pyt .sec h2 { margin: 0 0 10px; font-size: 1.25rem; }
.pyt .sec h2 small { font-size: .8rem; color: var(--text-dim); font-weight: 600; margin-left: 6px; }
.pyt .topic { padding: 12px 14px; margin: 0 0 10px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); }
.pyt .topic h3 { margin: 0 0 6px; font-size: 1.02rem; color: var(--text); }
.pyt .badges { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 8px; }
.pyt .b { display: inline-block; padding: 1px 8px; border-radius: 99px; font-size: .74rem; font-weight: 700; border: 1px solid var(--line); }
.pyt .b-must { color: #ff8a7a; border-color: rgba(255,138,122,.45); }
.pyt .b-hy { color: var(--amber); border-color: rgba(245,197,66,.45); }
.pyt .b-rep, .pyt .b-ex, .pyt .b-asked { color: var(--text-dim); }
.pyt .n { font-size: .8rem; color: var(--text-dim); margin-left: auto; }
.pyt .key { margin: 0 0 8px; font-size: .93rem; }
.pyt details.pq { margin: 0 0 8px; border-left: 3px solid var(--amber); padding: 2px 0 2px 12px; }
.pyt details.pq summary { cursor: pointer; font-weight: 700; color: var(--text); font-size: .9rem; }
.pyt .stem { margin: 8px 0 6px; color: var(--text); font-size: .92rem; }
.pyt .opts { list-style: none; margin: 0 0 6px; padding: 0; font-size: .9rem; }
.pyt .opts li { margin: 0 0 2px; }
.pyt .opts li.ans { color: var(--text); font-weight: 700; }
.pyt .why { margin: 0; font-size: .88rem; }
.pyt .go { font-size: .88rem; font-weight: 700; }
.pyt .end { margin: 28px 0 0; }
@media (max-width: 620px) { .pyt .n { margin-left: 0; width: 100%; } }
</style>
"""


def main():
    changed = []
    for nf in sorted((HERE / "pyt_notes").glob("*.json")):
        name, page = build(nf)
        f = HERE / name
        old = f.read_text(encoding="utf-8") if f.exists() else ""
        # the date stamp alone is not a change: compare with today's date blanked
        strip = lambda s: re.sub(r"Updated \d+ \w+ \d{4}|\"dateModified\": \"[\d-]+\"", "", s)
        if strip(old) != strip(page):
            changed.append(name)
            if not CHECK:
                f.write_text(page, encoding="utf-8", newline="\n")
    print(("would change: " if CHECK else "written: ") + (", ".join(changed) or "nothing"))


if __name__ == "__main__":
    main()
