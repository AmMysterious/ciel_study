# -*- coding: utf-8 -*-
"""indexnow_ping.py - tell Bing (and the other IndexNow engines: Yandex, Seznam, Naver...) that pages changed.  0.1.0

27 Nov 2026: first used after the 19 topic pages went live (HTTP 200). ChatGPT's web search leans on Bing's index, so
this is the quickest way to get new pages seen there. Google does not use IndexNow; it reads sitemap.xml by itself.

Run it AFTER a push is live (GitHub Pages takes about a minute):
    python indexnow_ping.py            every URL in sitemap.xml
    python indexnow_ping.py pyt-ent.html faq.html     only these pages

The key is the public file 972e1ac7739b4d6ba56cb4ca2f956459.txt at the site root (its content is the key itself);
it is meant to be public. Sends only this site's own public page addresses.
"""
import json, re, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://ammysterious.github.io/ciel_study"
KEY = "972e1ac7739b4d6ba56cb4ca2f956459"

pages = sys.argv[1:]
urls = ([f"{BASE}/{p}" for p in pages] if pages
        else re.findall(r"<loc>([^<]+)</loc>", (HERE / "sitemap.xml").read_text(encoding="utf-8")))
body = json.dumps({"host": "ammysterious.github.io", "key": KEY, "keyLocation": f"{BASE}/{KEY}.txt",
                   "urlList": urls}).encode("utf-8")
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                             headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"IndexNow: HTTP {r.status} for {len(urls)} URL(s)")   # 200/202 = accepted
except Exception as e:
    print(f"IndexNow failed: {e}")
