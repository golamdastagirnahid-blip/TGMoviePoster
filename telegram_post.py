"""Thin wrapper around Telegram Bot HTTP API."""
import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_media_group(chat_id, image_urls, caption):
    """Post 2-10 images as an album. Caption attaches to the first image."""
    import json
    if not image_urls:
        return False
    media = []
    for i, url in enumerate(image_urls[:10]):
        item = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = caption[:1024]
            item["parse_mode"] = "Markdown"
        media.append(item)
    r = requests.post(
        f"{BASE}/sendMediaGroup",
        data={"chat_id": chat_id, "media": json.dumps(media)},
        timeout=120,
    )
    if not r.ok:
        print("sendMediaGroup error:", r.text)
    return r.ok


def send_photo(chat_id, photo_url, caption):
    r = requests.post(
        f"{BASE}/sendPhoto",
        data={
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption[:1024],
            "parse_mode": "Markdown",
        },
        timeout=60,
    )
    if not r.ok:
        print("sendPhoto error:", r.text)
    return r.ok


def send_message(chat_id, text):
    r = requests.post(
        f"{BASE}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=60,
    )
    if not r.ok:
        print("sendMessage error:", r.text)
    return r.ok


def send_video_file(chat_id, file_path, caption):
    with open(file_path, "rb") as f:
        r = requests.post(
            f"{BASE}/sendVideo",
            data={"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"},
            files={"video": f},
            timeout=600,
        )
    if not r.ok:
        print("sendVideo error:", r.text)
    return r.ok
