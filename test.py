import time
import pathlib
import requests
from urllib.parse import urljoin

BASE = "https://pimacountyaz-web.tylerhost.net"
SEARCH_PAGE = "/web/search/DOCSEARCH55S8"
RESULTS_PATH = "/web/searchResults/DOCSEARCH55S8"

# ---------- CONFIG ----------
USE_HARDCODED_SESSION = True  # set True to force a specific JSESSIONID
HARDCODED_JSESSIONID = "7E013FDD5C73FD5894861A42109C6D28"  # <-- replace if you want to hardcode
MAX_PAGES = 1                    # how many pages to fetch
OUT_DIR = pathlib.Path("pima_results_html")
OUT_DIR.mkdir(exist_ok=True)
# ----------------------------

def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": urljoin(BASE, "/web/"),  # keeps it close to how the app calls it
    })

    if USE_HARDCODED_SESSION:
        # Mode B: use a fixed cookie (your risk: it may expire anytime)
        s.cookies.set("JSESSIONID", HARDCODED_JSESSIONID, domain="pimacountyaz-web.tylerhost.net", path="/")
        s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/")
        return s

    # Mode A (preferred): get a fresh JSESSIONID by visiting the search page
    resp = s.get(urljoin(BASE, SEARCH_PAGE), timeout=30)
    resp.raise_for_status()

    # Accept disclaimer by setting the cookie (matches what you captured)
    s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/")
    return s

def fetch_results_page(sess: requests.Session, page_num: int) -> str:
    url = urljoin(BASE, RESULTS_PATH)
    # Match the XHR-style headers you observed:
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "ajaxrequest": "true",
        "Referer": urljoin(BASE, SEARCH_PAGE),
        "Accept": "*/*",
    }
    params = {
        "page": page_num,
        # cache-buster (the portal includes a millis param in your capture)
        "_": int(time.time() * 1000),
    }
    r = sess.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    # Expecting text/html;charset=UTF-8 (HTML snippet/page)
    return r.text

def main():
    sess = make_session()

    last_sig = None
    for page in range(1, MAX_PAGES + 1):
        html = fetch_results_page(sess, page)

        # Save raw HTML so you can parse later with BeautifulSoup/lxml
        out_file = OUT_DIR / f"results_page_{page}.html"
        out_file.write_text(html, encoding="utf-8")
        print(f"[saved] {out_file}")

        # Simple stop condition if content stops changing (optional)
        sig = (len(html), hash(html))
        if last_sig is not None and sig == last_sig:
            print("[info] page content identical to previous; stopping.")
            break
        last_sig = sig

        # Optional: be polite if you loop many pages
        time.sleep(0.8)

if __name__ == "__main__":
    main()
