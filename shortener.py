"""Cuty.io URL shortener. Earns per click via interstitial ad.
Get API key: https://cuty.io/member/tools/api  (free signup)
Set env var CUTY_API_KEY. If unset, shortener is bypassed (returns original URL).

Never shorten:
  - amazon.* links (breaks affiliate tracking)
  - t.me/* links (your own channel)
"""
import os
import requests

API_KEY = os.environ.get("CUTY_API_KEY", "")
ENDPOINT = "https://cuty.io/api"

# In-memory cache for the run (avoids re-shortening same URL)
_CACHE: dict[str, str] = {}

SKIP_DOMAINS = ("amazon.", "t.me/", "telegram.me/")


def _should_skip(url: str) -> bool:
    low = url.lower()
    return any(d in low for d in SKIP_DOMAINS)


def shorten(url: str) -> str:
    if not API_KEY or not url or _should_skip(url):
        return url
    if url in _CACHE:
        return _CACHE[url]
    try:
        r = requests.get(
            ENDPOINT,
            params={"api": API_KEY, "url": url, "format": "text"},
            timeout=15,
        )
        if r.ok and r.text.startswith("http"):
            _CACHE[url] = r.text.strip()
            return _CACHE[url]
        print("shorten failed:", r.text[:200])
    except Exception as e:
        print("shorten error:", e)
    return url
