#!/usr/bin/env python3
"""
tylerhost_keepalive_config.py

Bootstraps the TylerHost session (disclaimer flow), submits a search with
required fields (dates + document types), optionally fetches the first
results page, then keeps the session alive by periodic pings.

Edit the CONFIG section below to suit your needs.
"""

import time
import random
from datetime import datetime
from urllib.parse import urljoin

import requests

# =========================
# ======= CONFIG ==========
# =========================
BASE = "https://pimacountyaz-web.tylerhost.net"

# Date range (MM/DD/YYYY)
START_DATE = "10/01/2025"
END_DATE   = "10/16/2025"

# Document types:
#   - Use codes only: ["NTSALE", "CNLNT"]
#   - Or code:label pairs: ["NTSALE:NOTICE SALE", "CNLNT:CANCELLATION NOTICE SALE"]
DOC_TYPES = ["NTSALE", "CNLNT"]

# Pagination: which results page to fetch after posting search
RESULTS_PAGE = 1               # 1-based

# Keep-alive interval (seconds). Use < server idle timeout.
KEEPALIVE_INTERVAL = 300       # 5 minutes

# Extra small pause between bootstrap steps (seconds)
STEP_DELAY = 0.5

# Verbose logging
VERBOSE = True

# Browser-y UA (some gateways are picky)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
# =========================
# ==== END CONFIG =========
# =========================

S = requests.Session()
S.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
})

def vprint(*a, **k):
    if VERBOSE:
        print(*a, **k)

def epoch_ms() -> str:
    return str(int(time.time() * 1000))

def ensure_ok(resp: requests.Response, label: str):
    if not resp.ok:
        raise RuntimeError(f"{label}: HTTP {resp.status_code}")
    return resp

def ajax_get(url, referer=None, accept="text/html, */*; q=0.01", params=None, timeout=30):
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": accept,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    r = S.get(url, params=params, headers=headers, timeout=timeout)
    return r

def ajax_post(url, referer=None, origin=None, accept="*/*", data=b"", timeout=30):
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": accept,
    }
    if origin:
        headers["Origin"] = origin
    if referer:
        headers["Referer"] = referer
    r = S.post(url, headers=headers, data=data, timeout=timeout)
    return r

def disclaimer_flow():
    """Replicates:
       1) GET  /web/user/disclaimer
       2) POST /web/user/disclaimer (Ajax)
       3) GET  /web/?_=...
       4) POST /web/homeActions (Ajax)
       5) GET  /web/action/ACTIONGROUP55S1?_=...
       6) GET  /web/search/DOCSEARCH55S8?_=...
    """
    # 1) GET disclaimer
    disclaimer = urljoin(BASE, "/web/user/disclaimer")
    r1 = S.get(disclaimer, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
    }, timeout=30)
    ensure_ok(r1, "GET /web/user/disclaimer")
    vprint("1) GET disclaimer →", r1.status_code)
    time.sleep(STEP_DELAY)

    # 2) POST disclaimer (accept)
    r2 = ajax_post(
        disclaimer, referer=disclaimer, origin=BASE,
        accept="application/json, text/javascript, */*; q=0.01", data=b""
    )
    ensure_ok(r2, "POST /web/user/disclaimer")
    vprint("2) POST disclaimer →", r2.status_code, "; cookies:", S.cookies.get_dict())
    time.sleep(STEP_DELAY)

    # 3) GET /web/?_=...
    web_root = urljoin(BASE, "/web/")
    r3 = ajax_get(web_root, referer=disclaimer, accept="text/html, */*; q=0.01",
                  params={"_": epoch_ms()})
    ensure_ok(r3, "GET /web/?_")
    vprint("3) GET /web/?_ →", r3.status_code)
    time.sleep(STEP_DELAY)

    # 4) POST /web/homeActions
    home_actions = urljoin(BASE, "/web/homeActions")
    r4 = ajax_post(home_actions, referer=disclaimer, origin=BASE, data=b"")
    ensure_ok(r4, "POST /web/homeActions")
    vprint("4) POST /web/homeActions →", r4.status_code)
    time.sleep(STEP_DELAY)

    # 5) GET ACTIONGROUP
    action = urljoin(BASE, "/web/action/ACTIONGROUP55S1")
    r5 = ajax_get(action, referer=web_root, params={"_": epoch_ms()})
    ensure_ok(r5, "GET /web/action/ACTIONGROUP55S1")
    vprint("5) GET ACTIONGROUP55S1 →", r5.status_code)
    time.sleep(STEP_DELAY)

    # 6) GET DOCSEARCH page
    search = urljoin(BASE, "/web/search/DOCSEARCH55S8")
    r6 = ajax_get(search, referer=action, params={"_": epoch_ms()})
    ensure_ok(r6, "GET /web/search/DOCSEARCH55S8")
    vprint("6) GET DOCSEARCH55S8 →", r6.status_code)
    time.sleep(STEP_DELAY)

def submit_search():
    """POST the search criteria so results are available server-side."""
    # Validate dates
    for d in (START_DATE, END_DATE):
        try:
            datetime.strptime(d, "%m/%d/%Y")
        except ValueError:
            raise SystemExit(f"Invalid date '{d}'. Use MM/DD/YYYY.")

    # Build x-www-form-urlencoded body with repeated keys
    form = [
        ("field_RecordingDateID_DOT_StartDate", START_DATE),
        ("field_RecordingDateID_DOT_EndDate",   END_DATE),
    ]
    for entry in DOC_TYPES:
        if ":" in entry:
            code, label = entry.split(":", 1)
        else:
            code, label = entry, entry
        form.append(("field_selfservice_documentTypes-holderInput", code.strip()))
        form.append(("field_selfservice_documentTypes-holderValue", label.strip()))
    form.append(("field_selfservice_documentTypes-containsInput", "Contains Any"))
    form.append(("field_selfservice_documentTypes", ""))

    url = urljoin(BASE, "/web/searchPost/DOCSEARCH55S8")
    r = requests.post(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "ajaxRequest": "true",
            "Origin": BASE,
            "Referer": urljoin(BASE, "/web/search/DOCSEARCH55S8"),
        },
        data=form,
        cookies=S.cookies,  # keep same session
        timeout=30,
    )
    ensure_ok(r, "POST /web/searchPost/DOCSEARCH55S8")
    try:
        js = r.json()
        vprint(f"7) POST searchPost → {r.status_code}; pages={js.get('totalPages')} current={js.get('currentPage')}")
    except Exception:
        vprint(f"7) POST searchPost → {r.status_code}; non-JSON response")
    time.sleep(STEP_DELAY)

def fetch_results_page(page: int):
    """GET the results page after the search has been posted."""
    url = urljoin(BASE, "/web/searchResults/DOCSEARCH55S8")
    final = f"{url}?page={page}&_={epoch_ms()}"
    backoff = 0.7
    for attempt in range(1, 5):
        r = S.get(final, headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Referer": urljoin(BASE, "/web/search/DOCSEARCH55S8"),
        }, timeout=30)
        if r.status_code >= 500:
            if attempt == 4:
                vprint(f"WARN: searchResults 500 after retries; body preview: {r.text[:200].replace(chr(10),' ')}")
                return None
            vprint(f"searchResults attempt {attempt} failed; retrying in {backoff:.1f}s …")
            time.sleep(backoff)
            backoff = backoff * 1.8 + random.uniform(0, 0.5)
            continue
        ensure_ok(r, "GET /web/searchResults/DOCSEARCH55S8")
        vprint(f"8) GET searchResults page={page} →", r.status_code)
        return r
    return None

def keepalive():
    ping = urljoin(BASE, "/web/session/pingSession")
    vprint(f"9) Starting keep-alive: {ping} every {KEEPALIVE_INTERVAL}s")
    while True:
        try:
            r = S.get(ping, params={"_": epoch_ms()}, headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                "Referer": urljoin(BASE, "/web/search/DOCSEARCH55S8"),
            }, timeout=30)
            vprint(f"PING → {r.status_code} ; {r.text.strip()[:120]}")
            if r.status_code in (401, 403):
                print("Session rejected (401/403). Exiting.")
                break
        except requests.RequestException as e:
            vprint(f"PING error: {e}")
        time.sleep(max(5, KEEPALIVE_INTERVAL * (1 + random.uniform(-0.1, 0.1))))

def main():
    try:
        disclaimer_flow()
        submit_search()
        fetch_results_page(RESULTS_PAGE)
        keepalive()
    except KeyboardInterrupt:
        print("Stopped.")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
