# Newest PUBLIC "PYT Explained" lesson -> the "Free lesson" block on the home and exam pages (26 Nov 2026, Nawar:
# "every week we post a newer PYT video, it's the one that should be visible first").
# Reads the channel's public feed (no key, no login; a private/unlisted video never appears there, so a lesson shows on
# the site only after HE publishes it). Runs in the exam-news workflow every 3 hours. Writes a page only on change.
# Tap-to-play: a thumbnail + play button; the youtube-nocookie player loads only on tap (fast pages, no YouTube
# cookies for visitors who never press play).
import html, json, re, sys, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
STORE = SITE / "news" / "lesson.json"
CHANNEL_ID = "UCRpj9vGYVN2l-ZfZXmOXazA"
CHANNEL_URL = "https://www.youtube.com/@Ciel_Study_bot"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
# page -> wrap the block in .wrap (pages whose <main> is not already a .wrap)
PAGES = {"index.html": True, "exams.html": False, "exam-fmge.html": False, "exam-neet-pg.html": False,
         "exam-ini-cet.html": False}
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def latest() -> dict | None:
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (Ciel Study site)"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    for e in root.findall("a:entry", NS):              # newest first
        title = e.findtext("a:title", default="", namespaces=NS)
        if title.startswith("PYT Explained"):
            return {"id": e.findtext("yt:videoId", default="", namespaces=NS), "title": title,
                    "published": e.findtext("a:published", default="", namespaces=NS)[:10]}
    return None


def block(it: dict, wrap: bool) -> str:
    vid = html.escape(it["id"])
    topic = html.escape(it["title"].split("|")[0].replace("PYT Explained:", "").strip())
    inner = (
        f'<p class="eyebrow">Free lesson · a new one every week</p>\n'
        f'<h2 id="lesson-h">PYT Explained: {topic}</h2>\n'
        f'<p class="lede">A 10-minute high-yield revision built from past exam questions, '
        f'for FMGE, NEET-PG and INI-CET.</p>\n'
        f'<button type="button" class="yt-lite" data-yt="{vid}" aria-label="Play the lesson: {topic}">'
        f'<img src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg" alt="" loading="lazy" width="480" height="360">'
        f'<span class="yt-play" aria-hidden="true"></span></button>\n'
        f'<p class="lesson-more"><a href="{CHANNEL_URL}" rel="noopener" target="_blank">All lessons on YouTube →</a></p>\n'
        '<script>(function(){var b=document.querySelector(".yt-lite");if(!b)return;b.addEventListener("click",function(){'
        'var f=document.createElement("iframe");f.src="https://www.youtube-nocookie.com/embed/"+b.dataset.yt+"?autoplay=1&rel=0";'
        'f.title=b.getAttribute("aria-label");f.allow="autoplay; encrypted-media; picture-in-picture; fullscreen";'
        'f.allowFullscreen=true;f.className="yt-frame";b.replaceWith(f);});})();</script>')
    body = f'<div class="wrap">\n{inner}\n</div>' if wrap else inner
    return f'<!--LESSON-->\n<section class="lesson-band" aria-labelledby="lesson-h">\n{body}\n</section>\n<!--/LESSON-->'


def render(it: dict) -> list[str]:
    changed = []
    for page, wrap in PAGES.items():
        f = SITE / page
        s = f.read_text(encoding="utf-8")
        if "<!--LESSON-->" not in s:
            raise SystemExit(f"{page}: no <!--LESSON--> marker")
        new = re.sub(r"<!--LESSON-->.*?<!--/LESSON-->", lambda _: block(it, wrap), s, flags=re.S)
        if new != s:
            f.write_text(new, encoding="utf-8")
            changed.append(page)
    return changed


def main() -> int:
    old = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    if "--offline" in sys.argv:
        it = old
    else:
        try:
            it = latest()
        except Exception as e:                          # never fail the news run over the lesson block
            print("lesson: feed failed -", str(e)[:160]); return 0
    if not it:
        print("lesson: no public PYT Explained video yet"); return 0
    changed = render(it)
    if it != old:
        STORE.write_text(json.dumps(it, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"lesson: {it['title'][:60]} ({it['id']}) · pages: {changed or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
