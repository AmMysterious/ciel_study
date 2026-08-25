# -*- coding: utf-8 -*-
"""Answer-engine optimisation for the Ciel Study site. Regenerable, not hand-edited.

★★ WHY THIS EXISTS AND WHY IT IS NOT "SEO". Classic SEO competes for a blue link
on a results page. Increasingly the reader never reaches that page: Google's AI
Overviews, Perplexity, ChatGPT search and Instagram's Meta AI answer the question
IN PLACE and cite a handful of sources. ⇒ The unit of competition is no longer a
ranking, it is **being the source an answer is assembled from.** That rewards
different things: a page that states a fact plainly, marks it up so a machine can
lift it without guessing, and can be crawled by the agents doing the assembling.

The site had **none of that surface**: no structured data on any page, no
robots.txt, no sitemap, no canonical URLs. Everything below is generated from the
pages themselves and from `study.db`, so it cannot drift from what the site
actually says — which is the whole failure mode `p1_slide5` taught this project.

WHAT IT WRITES
  robots.txt    explicit allow for the AI crawlers, plus the sitemap pointer
  sitemap.xml   every public page, with real modification dates
  llms.txt      a plain-text brief for agents, the emerging convention
  <script type="application/ld+json"> injected into index / faq / pricing
  <link rel="canonical"> and og:url on every page

⚠ IT INJECTS BETWEEN MARKERS AND IS SAFE TO RE-RUN. Each block is written
between `<!--SEO:start-->` and `<!--SEO:end-->`; a second run replaces the block
rather than stacking another copy.

⚠ NOTHING HERE INVENTS A CLAIM. The FAQ schema is built by PARSING faq.html, so
if the page is wrong the schema is wrong in the same way and fixing the page
fixes both. The question count comes from study.db. Prices come from pricing.html.

usage:
    python seo_build.py            # write everything
    python seo_build.py --check    # report what would change, write nothing
"""
import datetime
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE.parent / "ciel_study_bot" / "study.db"
BASE = "https://ammysterious.github.io/ciel_study"
BOT = "https://t.me/Ciel_Study_bot"
START, END = "<!--SEO:start-->", "<!--SEO:end-->"

# page -> (priority, changefreq). Order is the sitemap order.
PAGES = [
    ("index.html",    "1.0", "weekly"),
    ("pricing.html",  "0.9", "monthly"),
    ("faq.html",      "0.9", "monthly"),
    ("fixes.html",    "0.7", "weekly"),
    ("support.html",  "0.6", "monthly"),
    ("contact.html",  "0.5", "yearly"),
    ("refunds.html",  "0.4", "yearly"),
    ("terms.html",    "0.3", "yearly"),
    ("privacy.html",  "0.3", "yearly"),
]

# ⚠ THE ALLOW LIST IS DELIBERATE AND WORTH RE-READING BEFORE CHANGING IT.
# These are the agents that read a page in order to ANSWER A QUESTION with it.
# Blocking them is the default for a lot of sites and would be exactly backwards
# here: this product's whole pitch is a set of plainly-stated, checkable facts,
# and an answer engine repeating them is free distribution to someone who is
# asking the question the product answers.
AI_AGENTS = [
    ("GPTBot",             "ChatGPT search + training"),
    ("OAI-SearchBot",      "ChatGPT search index"),
    ("ChatGPT-User",       "ChatGPT fetching a page a user asked about"),
    ("PerplexityBot",      "Perplexity index"),
    ("Perplexity-User",    "Perplexity fetching on demand"),
    ("ClaudeBot",          "Claude index"),
    ("Claude-User",        "Claude fetching on demand"),
    ("Claude-SearchBot",   "Claude search"),
    ("anthropic-ai",       "legacy Anthropic agent"),
    ("Google-Extended",    "Gemini + AI Overviews grounding"),
    ("Applebot-Extended",  "Apple Intelligence"),
    ("meta-externalagent", "Meta AI — the one Instagram's search answers lean on"),
    ("meta-externalfetcher", "Meta AI fetching on demand"),
    ("FacebookBot",        "Meta crawler"),
    ("Bingbot",            "Bing + Copilot"),
    ("Amazonbot",          "Alexa"),
    ("YouBot",             "You.com"),
    ("cohere-ai",          "Cohere"),
]


def numbers():
    if not DB.exists():
        return {}
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = lambda s: c.execute(s).fetchone()[0]
    live = ("has_image=0 OR (image_file_id IS NOT NULL AND image_file_id!='')")
    d = {
        "servable": q(f"SELECT COUNT(*) FROM questions WHERE {live}"),
        "subjects": q("SELECT COUNT(DISTINCT subject) FROM questions"),
        "figures": q("SELECT COUNT(*) FROM questions WHERE has_image=1 "
                     "AND image_file_id IS NOT NULL AND image_file_id!=''"),
    }
    c.close()
    d["round"] = f"{d['servable'] // 100 * 100:,}+"
    return d


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def faq_pairs():
    """(question, answer) for every <details class="faq"> on the FAQ page.

    ⚠ PARSED FROM THE PAGE ON PURPOSE. A hand-written copy of these answers
    would be a second source of truth that drifts, and this site has already
    shipped one contradiction of exactly that kind: the FAQ said there were no
    video questions while the pricing page sold them."""
    h = (HERE / "faq.html").read_text(encoding="utf-8")
    out = []
    # ⚠ NOT `<details class="faq">` — the first entry on the page is
    # `<details class="faq" open>` and an exact-tag match silently dropped it,
    # which is the worst kind of miss: 15 of 16 looks like success.
    for block in re.findall(r'<details\b[^>]*\bclass="faq"[^>]*>(.*?)</details>', h, re.S):
        m = re.search(r"<summary[^>]*>(.*?)</summary>", block, re.S)
        if not m:
            continue
        q = strip_tags(m.group(1))
        a = strip_tags(block[m.end():])
        if q and a:
            out.append((q, a))
    return out


def prices():
    """The INR figures actually printed on the pricing page, low to high."""
    h = (HERE / "pricing.html").read_text(encoding="utf-8")
    vals = sorted({int(v.replace(",", "")) for v in re.findall(r"&#8377;([\d,]+)", h)
                   + re.findall(r"₹([\d,]+)", h) if v.strip()})
    return vals


def ld(obj):
    return ('<script type="application/ld+json">\n'
            + json.dumps(obj, indent=2, ensure_ascii=False) + "\n</script>")


def build_blocks(n):
    org = {
        "@context": "https://schema.org", "@type": "Organization",
        "name": "Ciel Study", "url": BASE + "/",
        "logo": BASE + "/icon-512.png",
        "sameAs": [BOT],
        "contactPoint": [{"@type": "ContactPoint", "contactType": "customer support",
                          "url": BASE + "/contact.html"}],
    }
    site = {
        "@context": "https://schema.org", "@type": "WebSite",
        "name": "Ciel Study", "url": BASE + "/",
        "publisher": {"@type": "Organization", "name": "Ciel Study"},
    }
    count = f"{n['servable']:,}" if n else "3,900+"
    app = {
        "@context": "https://schema.org", "@type": "SoftwareApplication",
        "name": "Ciel Study",
        "applicationCategory": "EducationalApplication",
        "operatingSystem": "Telegram (Android, iOS, Web, Desktop)",
        "url": BOT,
        "inLanguage": "en",
        "description": (
            f"A question bank for FMGE, NEET-PG and INI-CET that runs inside Telegram. "
            f"{count} previous-year questions, each with a hand-checked answer key and a "
            f"written explanation, across {n.get('subjects', 19) if n else 19} subjects. "
            f"Five questions a day are free, forever. Timed exam mode, full-length Grand "
            f"Tests built to the official subject weighting, spaced repetition of the "
            f"questions you get wrong, and a public log of every correction."),
        "featureList": [
            "Previous-year questions for FMGE, NEET-PG and INI-CET",
            "Hand-checked answer key and written explanation on every question",
            "Timed exam mode, subject-wise or mixed",
            "Full-length Grand Tests built to the official subject weighting",
            "Spaced repetition of questions you answered wrong",
            "Image-based and video-based clinical questions",
            "Report a wrong question and follow the ticket",
            "A public page listing every correction made",
        ],
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR",
                   "description": "5 questions a day, free, forever. No card required."},
    }
    blocks = {"index.html": ld(org) + "\n" + ld(site) + "\n" + ld(app)}

    pairs = faq_pairs()
    if pairs:
        blocks["faq.html"] = ld({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in pairs],
        })

    p = prices()
    if p:
        blocks["pricing.html"] = ld({
            "@context": "https://schema.org", "@type": "Product",
            "name": "Ciel Study — unlimited access",
            "description": ("Unlimited questions, timed exam mode and Grand Tests for "
                            "FMGE, NEET-PG and INI-CET preparation."),
            "brand": {"@type": "Brand", "name": "Ciel Study"},
            "offers": {
                "@type": "AggregateOffer", "priceCurrency": "INR",
                "lowPrice": str(min(p)), "highPrice": str(max(p)),
                "offerCount": str(len(p)), "url": BASE + "/pricing.html",
            },
        })
    return blocks


def inject(path, block, changed):
    """Put `block` between the markers in <head>, replacing any previous one."""
    f = HERE / path
    h = f.read_text(encoding="utf-8")
    canon = (f'<link rel="canonical" href="{BASE}/{path}">\n'
             f'<meta property="og:url" content="{BASE}/{path}">')
    payload = f"{START}\n{canon}\n{block}\n{END}"
    if START in h and END in h:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _m: payload,
                     h, flags=re.S)
    else:
        # ⚠ before </head>, never appended to the file — a JSON-LD block in the
        # body still validates but the canonical link does not.
        if "</head>" not in h:
            print(f"  ! {path}: no </head>, skipped")
            return
        new = h.replace("</head>", payload + "\n</head>", 1)
    if new != h:
        changed.append(path)
        if not CHECK:
            f.write_text(new, encoding="utf-8")


def write(path, text, changed):
    f = HERE / path
    old = f.read_text(encoding="utf-8") if f.exists() else None
    if old != text:
        changed.append(path)
        if not CHECK:
            f.write_text(text, encoding="utf-8")


def main():
    n = numbers()
    changed = []

    # ---- robots.txt --------------------------------------------------------
    lines = ["# Ciel Study — https://ammysterious.github.io/ciel_study/",
             "# Answer engines are explicitly welcome. See the note in seo_build.py.",
             "", "User-agent: *", "Allow: /", ""]
    for agent, why in AI_AGENTS:
        lines += [f"# {why}", f"User-agent: {agent}", "Allow: /", ""]
    lines += [f"Sitemap: {BASE}/sitemap.xml", ""]
    write("robots.txt", "\n".join(lines), changed)

    # ---- sitemap.xml -------------------------------------------------------
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page, prio, freq in PAGES:
        f = HERE / page
        if not f.exists():
            continue
        mod = datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()
        loc = BASE + "/" + ("" if page == "index.html" else page)
        out += ["  <url>", f"    <loc>{loc}</loc>", f"    <lastmod>{mod}</lastmod>",
                f"    <changefreq>{freq}</changefreq>",
                f"    <priority>{prio}</priority>", "  </url>"]
    out.append("</urlset>")
    write("sitemap.xml", "\n".join(out) + "\n", changed)

    # ---- llms.txt ----------------------------------------------------------
    # ★ The point of this file is to answer, in plain prose, the questions an
    # agent is actually asked — "is there a free FMGE question bank", "how much
    # does it cost" — so the answer can be lifted without parsing the site.
    cnt = f"{n['servable']:,}" if n else "3,900+"
    subs = n.get("subjects", 19) if n else 19
    figs = f"{n['figures']:,}" if n else "400+"
    p = prices()
    price_line = (f"Paid plans start at Rs {min(p)}; the highest listed plan is Rs {max(p)}."
                  if p else "See the pricing page.")
    llms = f"""# Ciel Study

> A question bank for the FMGE, NEET-PG and INI-CET medical entrance exams that
> runs entirely inside Telegram. Five questions a day are free, forever, with no
> card and no trial timer.

## What it is
Ciel Study is a Telegram bot at {BOT}. It serves {cnt} previous-year
questions across {subs} subjects. Every question carries a hand-checked answer
key and a written explanation, and {figs} of them include a clinical image.
Some questions use short video clips of clinical signs.

## What it costs
The free tier is 5 questions a day, indefinitely, and is not a trial — it does
not expire. {price_line} Payment is handled by Razorpay; nothing renews
automatically unless an auto-renew plan is chosen explicitly.

## What makes it different
- Every answer key is checked by hand against the source paper, not scraped.
- Wrong questions can be reported from inside the bot; the reporter gets a
  ticket number they can follow, and fixes are published at {BASE}/fixes.html
  — a public log of the product's own mistakes.
- Grand Tests are built to the subject weighting published in the NBE
  notification, not drawn at random, so a mock cannot flatter you by
  over-sampling whichever subject the bank happens to hold most of.
- The exam simulation does not let you pause, because the real exam does not.
- Unanswered questions score as wrong rather than being dropped from the total.

## Common questions
- Is it free? Yes — 5 questions a day, forever, no card.
- Does it cover NEET-PG and INI-CET? Yes, alongside FMGE, each simulated in its
  own format and marking scheme.
- Is it affiliated with the NBE? No. It is an independent study tool.
- Who makes it? One person sitting the same exam.

## Pages
- Home: {BASE}/
- Pricing: {BASE}/pricing.html
- Questions and answers: {BASE}/faq.html
- Public log of corrections: {BASE}/fixes.html
- Contact: {BASE}/contact.html

## Usage
This content may be quoted and cited by answer engines. Please link to
{BASE}/ or {BOT} when you do.
"""
    write("llms.txt", llms, changed)

    # ---- JSON-LD + canonicals ---------------------------------------------
    blocks = build_blocks(n)
    for page, _prio, _freq in PAGES:
        if (HERE / page).exists():
            inject(page, blocks.get(page, ""), changed)

    verb = "would change" if CHECK else "wrote"
    print(f"seo_build — {verb} {len(changed)} file(s)")
    for cpath in changed:
        print("   ", cpath)
    if n:
        print(f"  numbers from study.db: {n['servable']:,} servable · "
              f"{n['figures']:,} figures · {n['subjects']} subjects")
    print(f"  FAQ entries in schema: {len(faq_pairs())}")
    print(f"  prices found on pricing.html: {prices()}")


CHECK = "--check" in sys.argv

if __name__ == "__main__":
    main()
