# Ciel Study — policy site

The public policy pages for **Ciel Study**, a previous-year question bank for FMGE, NEET-PG
and INI-CET aspirants, delivered through Telegram as [@Ciel_Study_bot](https://t.me/Ciel_Study_bot).

**Live at:** https://ammysterious.github.io/ciel_study/

## What the bot actually is

4,908+ previous-year questions across 19 subjects, every one with a hand-checked answer key
and a written explanation — not auto-generated, each independently re-solved and confirmed
against the stored key before it ships. 410 questions carry an attached figure, 75 are
video-based. Features: Tutor mode, timed Exam Mode with full-length Grand Tests built to the
official subject weighting, spaced repetition of questions answered wrong, streaks, a referral
program, and a public fix log (`fixes.html`) — every reported defect and its resolution, logged
without naming the reporter.

Free tier: 5 questions a day, forever, no card and no time-limited trial.

## Pages

| Page | Purpose |
|---|---|
| `index.html` | What the bot is, what it contains, who operates it |
| `pricing.html` | Plans, prices in INR, and how access is granted |
| `terms.html` | Terms and conditions of use |
| `privacy.html` | What data is collected and how it is handled |
| `refunds.html` | Refund and cancellation policy |
| `contact.html` | Operator details and how to get support |
| `fixes.html` | Public log of reported issues and their fixes |
| `support.html` | Help and FAQ |

`style.css` is the only stylesheet. There is no JavaScript beyond a copyright year,
no build step, no dependencies and no tracking.

## Plans

| Plan | Price | Access |
|---|---|---|
| Free | ₹0 | 5 questions per day, indefinitely |
| 1 week | ₹129 | 7 days |
| 1 month | ₹349 | 30 days, includes 2 Grand Tests |
| 1 month + extra Grand Tests | ₹449 | 30 days, includes 4 Grand Tests |

Payments are processed by Razorpay. Payment details are entered on Razorpay's hosted
page and are never handled by Ciel Study.

## Refund policy summary

A refund is offered where **fewer than 25 questions** have been attempted on the paid
plan **and** the request falls inside the window for that plan:

| Plan | Window |
|---|---|
| 1 week (₹129) | 1 day from payment |
| 1 month (₹349) | 3 days from payment |
| 1 month + Grand Tests (₹449) | 3 days from payment |

`refunds.html` is the authoritative version; this table is a summary.

## Contact

Support runs through the bot itself — `/feedback` opens a ticket and returns a number,
`/myfeedback` shows its status and any reply. Direct contact details are on
[the contact page](https://ammysterious.github.io/ciel_study/contact.html).

## Editing

These are plain static files served by GitHub Pages from `main` at the repository root.
Edit and push; the site rebuilds in about a minute.

The site's numbers (servable count, subjects, figures, videos, prices) are generated FROM
`study.db` and `.env` by `sync_site.py`, not hand-typed — run `python sync_site.py --check`
after any bank change to see what's stale, then `python sync_site.py` to rewrite it, and
`python seo_build.py` to refresh `sitemap.xml`/`llms.txt`. Keep the operator details on
`contact.html` consistent with the details registered with the payment provider.

---

Ciel Study is operated by an individual (sole proprietor) in India and is not affiliated
with, endorsed by, or connected to the National Board of Examinations (NBE) or any
official examination body.
