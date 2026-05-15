"""Thin wrapper around Telegram Bot HTTP API. Uses resilient _http helper."""
import json
import os

import _http

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def _ok(resp, label):
    if resp is None:
        print(f"[tg] {label}: no response")
        return False
    if not resp.ok:
        print(f"[tg] {label} error: {resp.text[:300]}")
        return False
    return True


def _check_token():
    if not TOKEN:
        print("[tg] TELEGRAM_BOT_TOKEN not set")
        return False
    return True


def send_media_group(chat_id, image_urls, caption):
    """Post 2-10 images as an album. Caption attaches to the first image."""
    if not _check_token() or not image_urls:
        return False
    media = []
    for i, url in enumerate(image_urls[:10]):
        item = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = caption[:1024]
            item["parse_mode"] = "Markdown"
        media.append(item)
    r = _http.post(
        f"{BASE}/sendMediaGroup",
        data={"chat_id": chat_id, "media": json.dumps(media)},
        timeout=120,
    )
    return _ok(r, "sendMediaGroup")


def send_photo(chat_id, photo_url, caption):
    if not _check_token():
        return False
    r = _http.post(
        f"{BASE}/sendPhoto",
        data={
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption[:1024],
            "parse_mode": "Markdown",
        },
        timeout=60,
    )
    return _ok(r, "sendPhoto")


def send_message(chat_id, text):
    if not _check_token():
        return False
    r = _http.post(
        f"{BASE}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=60,
    )
    return _ok(r, "sendMessage")


def send_video_file(chat_id, file_path, caption):
    if not _check_token():
        return False
    try:
        with open(file_path, "rb") as f:
            r = _http.post(
                f"{BASE}/sendVideo",
                data={"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"},
                files={"video": f},
                timeout=600,
                retries=1,
            )
        if _ok(r, "sendVideo"):
            return True
        # Fallback: parse error? retry without Markdown so the post still goes
        if r is not None and "can't parse entities" in r.text.lower():
            print("[tg] retrying sendVideo without Markdown")
            with open(file_path, "rb") as f:
                r2 = _http.post(
                    f"{BASE}/sendVideo",
                    data={"chat_id": chat_id, "caption": caption[:1024]},
                    files={"video": f},
                    timeout=600,
                    retries=1,
                )
            return _ok(r2, "sendVideo(plain)")
        return False
    except OSError as e:
        print(f"[tg] cannot read video: {e}")
        return False
