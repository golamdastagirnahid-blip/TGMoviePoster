"""Resilient HTTP helper used by all API wrappers.
- Retries on network errors, timeouts, 429 (rate limit) and 5xx.
- Exponential backoff with jitter.
- Never raises; always returns Response or None so callers stay clean.
"""
import random
import time

import requests

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3


def request(method, url, *, retries=MAX_RETRIES, timeout=DEFAULT_TIMEOUT, **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
            # Retry on transient server / rate-limit errors
            if r.status_code == 429 or 500 <= r.status_code < 600:
                wait = float(r.headers.get("Retry-After", 0)) or (
                    2 ** attempt + random.uniform(0, 1)
                )
                print(f"[http] {r.status_code} -> retry in {wait:.1f}s")
                time.sleep(wait)
                continue
            return r
        except (requests.ConnectionError, requests.Timeout) as e:
            last_err = e
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f"[http] {type(e).__name__}: {e} -> retry in {wait:.1f}s")
            time.sleep(wait)
        except Exception as e:
            last_err = e
            print(f"[http] unexpected: {e}")
            break
    if last_err:
        print(f"[http] giving up after {retries} attempts: {last_err}")
    return None


def get(url, **kw):
    return request("GET", url, **kw)


def post(url, **kw):
    return request("POST", url, **kw)
