"""Facebook Page poster using Graph API.
Needs FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN (long-lived Page token).
Posts a multi-photo album with caption on the first photo.
Resilient: retries network errors, surfaces token-expiry clearly.
"""
import json
import os

import _http

PAGE_ID = os.environ.get("FB_PAGE_ID", "")
TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
GRAPH = "https://graph.facebook.com/v20.0"


def _enabled():
    return bool(PAGE_ID and TOKEN)


def _log_error(label, resp):
    if resp is None:
        print(f"[fb] {label}: no response")
        return
    body = resp.text[:400]
    if "OAuth" in body or "expired" in body.lower() or "access token" in body.lower():
        print(f"[fb] {label}: TOKEN EXPIRED/INVALID -> regenerate via refresh_fb_tokens.py")
    print(f"[fb] {label} error: {body}")


def _upload_unpublished(image_url):
    """Upload a photo to the Page without publishing it. Returns photo id."""
    r = _http.post(
        f"{GRAPH}/{PAGE_ID}/photos",
        data={"url": image_url, "published": "false", "access_token": TOKEN},
        timeout=60,
    )
    if r is None or not r.ok:
        _log_error("photo upload", r)
        return None
    try:
        return r.json().get("id")
    except Exception:
        return None


def post_album(image_urls, caption):
    """Publish a feed post with attached photos (album style)."""
    if not _enabled():
        print("[fb] skipped (no token)")
        return False
    media_fbids = []
    for url in image_urls[:10]:
        pid = _upload_unpublished(url)
        if pid:
            media_fbids.append({"media_fbid": pid})
    if not media_fbids:
        print("[fb] no photos uploaded; aborting album post")
        return False
    r = _http.post(
        f"{GRAPH}/{PAGE_ID}/feed",
        data={
            "message": caption,
            "attached_media": json.dumps(media_fbids),
            "access_token": TOKEN,
        },
        timeout=60,
    )
    if r is None or not r.ok:
        _log_error("feed post", r)
        return False
    return True
