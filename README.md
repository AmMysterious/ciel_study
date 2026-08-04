# Ciel Study — policy site

The public policy pages for **Ciel Study**, a previous-year question bank for FMGE
aspirants delivered through Telegram as [@Ciel_Study_bot](https://t.me/Ciel_Study_bot).

**Live at:** https://ammysterious.github.io/ciel_study/

## Pages

| Page | Purpose |
|---|---|
| `index.html` | What the bot is, what it contains, who operates it |
| `pricing.html` | Plans, prices in INR, and how access is granted |
| `terms.html` | Terms and conditions of use |
| `privacy.html` | What data is collected and how it is handled |
| `refunds.html` | Refund and cancellation policy |
| `contact.html` | Operator details and how to get support |

`style.css` is the only stylesheet. There is no JavaScript beyond a copyright year,
no build step, no dependencies and no tracking.

## Plans

| Plan | Price | Access |
|---|---|---|
| Free | ₹0 | 5 questions per day, indefinitely |
| 1 week | ₹100 | 7 days |
| 1 month | ₹300 | 30 days |
| 1 month, auto-renew | ₹239/month | 30 days, recurring until cancelled |

Payments are processed by Razorpay. Payment details are entered on Razorpay's hosted
page and are never handled by Ciel Study.

## Refund policy summary

A refund is offered where **fewer than 25 questions** have been attempted on the paid
plan **and** the request falls inside the window for that plan:

| Plan | Window |
|---|---|
| 1 week | 1 day from payment |
| 1 month | 3 days from payment |
| Auto-renew | 7 days from the charge |

`refunds.html` is the authoritative version; this table is a summary.

## Contact

Support runs through the bot itself — `/feedback` opens a ticket and returns a number,
`/myfeedback` shows its status and any reply. Direct contact details are on
[the contact page](https://ammysterious.github.io/ciel_study/contact.html).

## Editing

These are plain static files served by GitHub Pages from `main` at the repository root.
Edit and push; the site rebuilds in about a minute.

Keep the operator details on `contact.html` consistent with the details registered with
the payment provider, and keep the prices here consistent with `pricing.html` and with
the bot.

---

Ciel Study is operated by an individual (sole proprietor) in India and is not affiliated
with, endorsed by, or connected to the National Board of Examinations (NBE) or any
official examination body.
