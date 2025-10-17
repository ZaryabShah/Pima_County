#!/usr/bin/env python3
"""
tylerhost_keepalive.py
- Bootstraps a session exactly like your capture:
  (1) GET  /web/user/disclaimer  -> receives JSESSIONID
  (2) POST /web/user/disclaimer  -> sets disclaimerAccepted=true
  (3) Loops GET /web/session/pingSession with cache-busting param

Usage:
  python tylerhost_keepalive.py --interval 300 --verbose
"""

import argparse
import logging
import random
import time
import sys
from urllib.parse import urljoin

import requests


BASE = "https://pimacountyaz-web.tylerhost.net"
DISCLAIMER_PATH = "/web/user/disclaimer"
PING_PATH = "/web/session/pingSession"

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/140.0.0.0 Safari/537.36'
)

def start_session(base: str, verbose: bool = False) -> requests.Session:
    s = requests.Session()
    # Helpful defaults matching your capture
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })

    # 1) GET /web/user/disclaimer
    url = urljoin(base, DISCLAIMER_PATH)
    r = s.get(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
        },
        timeout=30,
    )
    r.raise_for_status()
    if verbose:
        print("GET disclaimer →", r.status_code)
    # JSESSIONID is now in s.cookies (Set-Cookie from response)
    if "JSESSIONID" not in s.cookies.get_dict():
        raise RuntimeError("No JSESSIONID received on GET /web/user/disclaimer")

    # 2) POST /web/user/disclaimer with Ajax-ish headers to set disclaimerAccepted
    r2 = s.post(
        url,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": base,
            "Referer": url,
        },
        data=b"",  # capture showed Content-Length: 0
        timeout=30,
    )
    r2.raise_for_status()
    if verbose:
        print("POST disclaimer →", r2.status_code, "cookies:", s.cookies.get_dict())
    return s

def ping_loop(s: requests.Session, base: str, interval: int, verbose: bool):
    ping_url = urljoin(base, PING_PATH)

    backoff = 5
    backoff_max = 300
    if verbose:
        print(f"Starting ping loop every {interval}s → {ping_url}")

    while True:
        params = {"_": str(int(time.time() * 1000))}
        try:
            r = s.get(
                ping_url,
                params=params,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                    "Referer": urljoin(base, "/web/search/DOCSEARCH55S8"),
                },
                timeout=30,
            )
            status = r.status_code
            if verbose:
                body_preview = r.text[:120].replace("\n", " ")
                print(f"PING → HTTP {status} ; {body_preview}")
            if status in (401, 403):
                print(f"Auth rejected (HTTP {status}). Session likely expired.")
                sys.exit(1)
            if status >= 500:
                # transient server issue; back off
                if verbose:
                    print(f"Server error {status}. Backing off {backoff}s …")
                time.sleep(backoff)
                backoff = min(backoff * 2, backoff_max)
                continue
            # success resets backoff
            backoff = 5
        except requests.RequestException as e:
            if verbose:
                print(f"Request error: {e} ; backoff {backoff}s …")
            time.sleep(backoff)
            backoff = min(backoff * 2, backoff_max)
            continue

        # jitter the sleep to avoid a perfect cadence
        jitter = random.uniform(-0.1, 0.1) * interval
        sleep_s = max(5, interval + jitter)
        time.sleep(sleep_s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE, help="Base URL of the site")
    ap.add_argument("--interval", type=int, default=300, help="Seconds between pings")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = ap.parse_args()

    try:
        sess = start_session(args.base, verbose=args.verbose)
    except Exception as e:
        print("Failed to start session:", e)
        sys.exit(1)

    try:
        ping_loop(sess, args.base, args.interval, args.verbose)
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()
