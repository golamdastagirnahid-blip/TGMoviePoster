"""Exchange a short-lived User token for a NEVER-EXPIRING Page token.

USAGE:
    1. Open https://developers.facebook.com/tools/explorer/
    2. Top-right: select your App.
    3. "User or Page": select **User Token**.
    4. Click "Add a Permission" and tick at minimum:
         - pages_show_list
         - pages_read_engagement
         - pages_manage_posts        <-- REQUIRED to post on a Page
         - pages_manage_metadata
    5. Click "Generate Access Token" (login + approve permissions).
    6. Copy the token shown at the top.
    7. Run this script:

         python scripts/get_page_token.py YOUR_USER_TOKEN YOUR_APP_ID YOUR_APP_SECRET

       App ID / Secret are found at
       https://developers.facebook.com/apps/<app>/settings/basic/

    8. The script prints a long-lived USER token, then converts it to
       per-Page tokens. Copy the Page Access Token for your Movie Bell page.

    9. In GitHub: Settings -> Secrets and variables -> Actions
         - Update FB_PAGE_ACCESS_TOKEN to that Page token.
         - Update FB_PAGE_ID with the Page id printed for that page.

       Page tokens from a long-lived user token DO NOT EXPIRE. You only
       redo this if you change FB password or revoke the app.
"""
import sys

import requests

GRAPH = "https://graph.facebook.com/v20.0"


def die(msg):
    print("ERROR:", msg)
    sys.exit(1)


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    user_token, app_id, app_secret = sys.argv[1:4]

    # Step 1: short-lived user token -> long-lived user token
    r = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_token,
        },
        timeout=30,
    )
    if not r.ok:
        die(f"long-lived user token exchange failed: {r.text}")
    long_user = r.json().get("access_token")
    print("\n== LONG-LIVED USER TOKEN (keep private) ==")
    print(long_user)

    # Step 2: list pages + their never-expiring page tokens
    r = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": long_user},
        timeout=30,
    )
    if not r.ok:
        die(f"failed to list pages: {r.text}")
    pages = r.json().get("data", [])
    if not pages:
        die("no pages found on this account. Make sure your user owns the page.")

    print("\n== PAGES YOU OWN ==")
    for p in pages:
        print(f"\nPage name: {p.get('name')}")
        print(f"Page id:   {p.get('id')}")
        print("Page token (never expires):")
        print(p.get("access_token"))


if __name__ == "__main__":
    main()
