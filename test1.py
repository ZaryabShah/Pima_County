import time
import pathlib
import requests
from urllib.parse import urljoin

BASE = "https://pimacountyaz-web.tylerhost.net"
SEARCH_PAGE = "/web/search/DOCSEARCH55S8"
RESULTS_PATH = "/web/searchResults/DOCSEARCH55S8"
Document_Download = "https://pimacountyaz-web.tylerhost.net/web/search/loadRelatedDocuments/DOCSEARCH55S8/DOC334S176"
# ===== CONFIG =====
USE_HARDCODED_SESSION = True  # <- set True to force a working JSESSIONID
HARDCODED_JSESSIONID = "7E013FDD5C73FD5894861A42109C6D28"
MAX_PAGES = 1
OUT_DIR = pathlib.Path("pima_results_html"); OUT_DIR.mkdir(exist_ok=True)
VERBOSE = True
# ===================

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": BASE + "/web/",
}

AJAX_HEADERS = {
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "ajaxrequest": "true",
    "Referer": BASE + SEARCH_PAGE,
}

def log_cookies(sess, label):
    if not VERBOSE: return
    print(f"[cookies:{label}]")
    for c in sess.cookies:
        print(f"  {c.domain} {c.path} {c.name}={c.value}")

def make_session():
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)

    if USE_HARDCODED_SESSION:
        # Use your working cookie exactly as captured
        s.cookies.set("JSESSIONID", HARDCODED_JSESSIONID, domain="pimacountyaz-web.tylerhost.net", path="/")
        s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/")
        s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/web")  # path-scoped too
        print("[info] Using hardcoded JSESSIONID + disclaimerAccepted.")
        log_cookies(s, "after-hardcode")
        return s

    # Mode A: get fresh cookies like a browser would
    print("[info] Seeding: GET /web/ …")
    r = s.get(urljoin(BASE, "/web/"), timeout=30); r.raise_for_status()

    print("[info] Seeding: GET search page …")
    r = s.get(urljoin(BASE, SEARCH_PAGE), timeout=30); r.raise_for_status()

    # Accept disclaimer via cookie (both / and /web paths)
    s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/")
    s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/web")
    print("[info] disclaimerAccepted=true set on / and /web.")
    log_cookies(s, "after-seed")

    return s

def priming_hit(sess: requests.Session):
    url = urljoin(BASE, RESULTS_PATH)
    params = {"_": int(time.time() * 1000)}
    print(f"[info] Priming GET {url} …")
    r = sess.get(url, headers=AJAX_HEADERS, params=params, timeout=30)
    print(f"[info] Priming status: {r.status_code}")
    # Some deployments 500 on priming—don’t fail the run; just continue.

def fetch_results_page(sess: requests.Session, page_num: int) -> str:
    url = urljoin(BASE, RESULTS_PATH)
    params = {"page": page_num, "_": int(time.time() * 1000)}
    print(f"[info] GET {url}?page={page_num}")
    r = sess.get(url, headers=AJAX_HEADERS, params=params, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        snippet = (r.text or "")[:800].replace("\n", " ")
        raise SystemExit(f"[error] {e}  Body (truncated): {snippet}")
    # Should be text/html
    if "text/html" not in r.headers.get("Content-Type",""):
        print(f"[warn] Unexpected content-type: {r.headers.get('Content-Type')}")
    return r.text

def main():
    sess = make_session()
    time.sleep(0.3)

    priming_hit(sess)  # ignore result; it just helps on some stacks
    time.sleep(0.3)

    last_sig = None
    for page in range(1, MAX_PAGES + 1):
        html = fetch_results_page(sess, page)
        out = OUT_DIR / f"results_page_{page}.html"
        out.write_text(html, encoding="utf-8")
        print(f"[saved] {out}")

        sig = (len(html), hash(html))
        if last_sig and sig == last_sig:
            print("[info] Page identical to previous; stopping.")
            break
        last_sig = sig
        time.sleep(0.6)

if __name__ == "__main__":
    main()
