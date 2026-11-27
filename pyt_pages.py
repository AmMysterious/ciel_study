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
    override = N.get("sections", {})          # optional {"id prefix": "section name"}; longest prefix wins
    for tid, sec, topic, rank, marks, _ in rows:
        pre = max((k for k in override if tid == k or tid.startswith(k + ".")), key=len, default=None)
        sec = override[pre] if pre else (sec or subject)
        if sec not in sections:
            sections[sec] = {"rank": rank, "marks": marks, "ids": set(), "topics": []}
            order.append(sec)
        S = sections[sec]
        S["ids"] |= qids[tid]
        S["rank"] = max(S["rank"], rank)
        title = notes.get(tid, {}).get("title")
        if len(qids[tid]) < 3 and tid not in notes:
            continue                            # 0-2 questions and no note: nothing useful to show yet
        if topic:
            S["topics"].append((tid, title or topic, rank, marks, len(qids[tid])))
        elif tid in notes:                      # a whole-section topic (e.g. "Most repeated antidotes")
            S["topics"].append((tid, title or sec, rank, marks, len(qids[tid])))
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

    body, quiz, toc = [], [], []
    for s in order:
        S = sections[s]
        if not S["topics"]:
            continue
        sid = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
        toc.append(f'<a href="#{e(sid)}">{e(s)}</a>')
        body.append(f'<section class="sec" id="{e(sid)}">')
        body.append(f'<h2>{e(s)} <small>{len(S["ids"]):,} questions</small></h2>')
        for tid, topic, rank, marks, n in S["topics"]:
            note = notes.get(tid, {})
            body.append(f'<article class="topic" id="t-{e(tid.replace(".", "-"))}">')
            INDEX.append({"s": subject, "t": topic, "u": f"pyt-{slug}.html#t-{tid.replace('.', '-')}", "n": n})
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
            # the same block seo_build.py injects, so the two scripts never fight over it
            f'<!--SEO:start-->\n<link rel="canonical" href="{url}">\n<meta property="og:url" content="{url}">\n\n<!--SEO:end-->\n'
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
            + (f'<nav class="toc" aria-label="Sections"><span>Jump to</span>{"".join(toc)}</nav>\n' if len(toc) > 1 else "")
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


def NOTES():
    """Only notes the lead has reviewed ("reviewed" set) become public pages. A helper's draft has no such key, so a
    rebuild for another subject can never publish it or link to it by accident (27 Nov: helpers draft some subjects)."""
    return [nf for nf in sorted((HERE / "pyt_notes").glob("*.json"))
            if json.loads(nf.read_text(encoding="utf-8")).get("reviewed")]


ICONS = {"anatomy": "🦴", "physiology": "🫀", "biochemistry": "🧪", "pathology": "🔬", "pharmacology": "💊",
         "microbiology": "🦠", "forensic-medicine": "⚖️", "community-medicine": "🏘️", "medicine": "🩺",
         "surgery": "🔪", "obstetrics-gynaecology": "🤰", "paediatrics": "🧒", "ophthalmology": "👁️", "ent": "👂",
         "orthopaedics": "🦿", "dermatology": "🧴", "psychiatry": "🧠", "radiodiagnosis": "🩻", "anaesthesia": "😷"}
INDEX: list = []      # every topic on every page, for the topic search on the home and hub pages


def main():
    changed = []
    for nf in NOTES():
        name, page = build(nf)
        f = HERE / name
        old = f.read_text(encoding="utf-8") if f.exists() else ""
        # the date stamp alone is not a change: compare with today's date blanked
        strip = lambda s: re.sub(r"Updated \d+ \w+ \d{4}|\"dateModified\": \"[\d-]+\"", "", s)
        if strip(old) != strip(page):
            changed.append(name)
            if not CHECK:
                f.write_text(page, encoding="utf-8", newline="\n")
    # pyt_index.json feeds the "find a topic" box (27 Nov: Nawar wanted the Topics block more interactive)
    ix = HERE / "pyt_index.json"
    data = json.dumps(sorted(INDEX, key=lambda r: (r["s"], -r["n"])), ensure_ascii=False, separators=(",", ":"))
    if not ix.exists() or ix.read_text(encoding="utf-8") != data:
        changed.append(ix.name)
        if not CHECK:
            ix.write_text(data, encoding="utf-8")
    # the FMGE PYQ page lists every subject page that exists, between its PYT markers
    hub = HERE / "fmge-previous-year-questions.html"
    subs = sorted((json.loads(nf.read_text(encoding="utf-8")) for nf in NOTES()),
                  key=lambda n: n["subject"])
    links = ", ".join(f'<a href="pyt-{n["slug"]}.html">{e(n["subject"])}</a>' for n in subs)
    h = hub.read_text(encoding="utf-8")
    h2 = re.sub(r"<!--PYT:list-->.*?<!--/PYT-->", lambda _: f"<!--PYT:list-->{links}<!--/PYT-->", h, flags=re.S)
    if h2 != h:
        changed.append(hub.name)
        if not CHECK:
            hub.write_text(h2, encoding="utf-8", newline="\n")
    # the home page's Topics band: one tile per subject page, with its topic count (27 Nov tidy-up)
    home = HERE / "index.html"
    tiles = []
    for n in subs:
        pg = HERE / f'pyt-{n["slug"]}.html'
        k = pg.read_text(encoding="utf-8").count('class="topic"') if pg.exists() else 0
        name = n["subject"].replace(" (PSM)", "").replace("Obstetrics & Gynaecology", "OBG")
        ic = ICONS.get(n["slug"], "📘")
        tiles.append(f'<li><a href="pyt-{n["slug"]}.html"><i aria-hidden="true">{ic}</i><b>{e(name)}</b>'
                     f'<span>{k} topics</span></a></li>')
    # a search box over pyt_index.json (topic-find.js); without JavaScript it stays hidden and the tiles still work
    finder = ('<div class="topic-find" hidden><input type="search" placeholder="Find a topic: anaemia, glaucoma, '
              'rabies..." aria-label="Find a topic" autocomplete="off"><ul class="topic-hits"></ul></div>'
              '<script defer src="topic-find.js"></script>')
    grid = finder + '<ul class="topic-tiles">' + "".join(tiles) + "</ul>"
    h = home.read_text(encoding="utf-8")
    h2 = re.sub(r"<!--PYT:grid-->.*?<!--/PYT-->", lambda _: f"<!--PYT:grid-->{grid}<!--/PYT-->", h, flags=re.S)
    if h2 != h:
        changed.append(home.name)
        if not CHECK:
            home.write_text(h2, encoding="utf-8", newline="\n")
    print(("would change: " if CHECK else "written: ") + (", ".join(changed) or "nothing"))


if __name__ == "__main__":
    main()
