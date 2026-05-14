"""Facebook Page poster using Graph API.
Needs FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN (long-lived Page token).
Posts a multi-photo album with caption on the first photo.
"""
import os
import requests

PAGE_ID = os.environ.get("FB_PAGE_ID", "")
TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
GRAPH = "https://graph.facebook.com/v20.0"


def _enabled():
    return bool(PAGE_ID and TOKEN)


def _upload_unpublished(image_url):
    """Upload a photo to the Page without publishing it. Returns photo id."""
    r = requests.post(
        f"{GRAPH}/{PAGE_ID}/photos",
        data={"url": image_url, "published": "false", "access_token": TOKEN},
        timeout=60,
    )
    if not r.ok:
        print("FB upload error:", r.text)
        return None
    return r.json().get("id")


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
        return False
    import json
    r = requests.post(
        f"{GRAPH}/{PAGE_ID}/feed",
        data={
            "message": caption,
            "attached_media": json.dumps(media_fbids),
            "access_token": TOKEN,
        },
        timeout=60,
    )
    if not r.ok:
        print("FB feed post error:", r.text)
    return r.ok
