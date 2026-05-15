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


# Facebook error codes that mean "stop posting today":
# 368 = temporarily blocked for policy violations
# 506 = duplicate post
# 1404006 = posting too frequently
# 1404102 = page suspended/restricted
POLICY_ERROR_CODES = {368, 1404006, 1404102}


def _classify_error(resp):
    """Return ('policy'|'duplicate'|'transient'|None) based on FB response."""
    if resp is None:
        return "transient"
    try:
        err = resp.json().get("error", {})
        code = err.get("code")
        sub = err.get("error_subcode")
        msg = (err.get("message") or "").lower()
        if code in POLICY_ERROR_CODES or sub in POLICY_ERROR_CODES:
            return "policy"
        if "spam" in msg or "policy" in msg or "violates" in msg or "restricted" in msg:
            return "policy"
        if "duplicate" in msg or code == 506:
            return "duplicate"
        if code == 4 or code == 17 or code == 32:  # rate limit codes
            return "rate_limit"
    except Exception:
        pass
    return "transient"


def post_album(image_urls, caption):
    """Publish a feed post with attached photos (album style).
    Returns (status, info):
      status in {'ok','policy','duplicate','rate_limit','error'}
    """
    if not _enabled():
        print("[fb] skipped (no token)")
        return ("error", "no token")
    media_fbids = []
    for url in image_urls[:10]:
        pid = _upload_unpublished(url)
        if pid:
            media_fbids.append({"media_fbid": pid})
    if not media_fbids:
        print("[fb] no photos uploaded; aborting album post")
        return ("error", "no photos")
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
        kind = _classify_error(r)
        return (kind, r.text[:200] if r is not None else "no response")
    return ("ok", "")
