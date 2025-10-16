#!/usr/bin/env python3
# Hardcoded downloader using provided cookies/headers.
# Tries the raw PDF endpoints discovered in the viewer HTML.
# Run: python get_pima_pdf_v6.py
import sys
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE = "https://pimacountyaz-web.tylerhost.net"
# Endpoints to try (order matters)
CANDIDATE_PATHS = [
    "/web/document-image-pdf/DOC334S176//20252830551-1.pdf?index=1",
    "/web/document-image-pdfjs/DOC334S176/20252830551.pdf?allowDownload=true&index=1",
    "/web/document/servepdf/DEGRADED-DOC334S176.1.pdf/20252830551.pdf?index=1&allowDownload=true&allowPrint=true",
]
OUT = "pima_document_20252830551.pdf"

# >>> Paste your current JSESSIONID value here (from DevTools)
JSESSIONID = "168B0656C702BC3042A3D68C26FFBAC4"   # <-- update when it changes

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "application/pdf, */*;q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE + "/web/resources/pdfjs/web/tylerPdfJsViewer.html",
    "Connection": "keep-alive",
}

def is_pdf_prefix(b: bytes) -> bool:
    return b.startswith(b"%PDF")

def fetch(sess: requests.Session, url: str) -> bytes|None:
    r = sess.get(url, headers=COMMON_HEADERS, stream=True, allow_redirects=True, timeout=60)
    if r.status_code >= 400:
        return None
    it = r.iter_content(chunk_size=8192)
    first = next(it, b"")
    if not is_pdf_prefix(first):
        return None
    # stream to file
    tmp = Path(OUT + ".part").open("wb")
    with tmp as f:
        f.write(first)
        for chunk in it:
            if chunk:
                f.write(chunk)
    Path(OUT + ".part").rename(OUT)
    return b"ok"

def main():
    if not JSESSIONID or len(JSESSIONID) < 8:
        print("Please set a valid JSESSIONID near the top of this script.", file=sys.stderr)
        sys.exit(2)

    s = requests.Session()
    # Set cookies exactly like the browser
    s.cookies.set("JSESSIONID", JSESSIONID, domain="pimacountyaz-web.tylerhost.net", path="/")
    s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/")
    s.cookies.set("disclaimerAccepted", "true", domain="pimacountyaz-web.tylerhost.net", path="/web")

    # Some AJAX endpoints check these headers — add as general headers when needed
    s.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "ajaxRequest": "true",
    })

    # Try each candidate
    for path in CANDIDATE_PATHS:
        url = urljoin(BASE, path)
        print("[*] Trying", url)
        ok = fetch(s, url)
        if ok:
            print("[✓] Saved to", OUT)
            return 0

    # If nothing worked, dump last response HTML for debugging
    # Hit the viewer file to capture the HTML it serves
    viewer = urljoin(BASE, "/web/resources/pdfjs/web/tylerPdfJsViewer.html")
    r = s.get(viewer, headers={"Referer": BASE + "/web/user/disclaimer"})
    Path("debug_response.html").write_text(r.text, encoding="utf-8", errors="ignore")
    print("[!] Could not obtain PDF. Wrote debug_response.html", file=sys.stderr)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
