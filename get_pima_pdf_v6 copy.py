#!/usr/bin/env python3
# Hardcoded downloader using provided cookies/headers.
# Tries the raw PDF endpoints discovered in the viewer HTML.
# Run: python get_pima_pdf_v6.py
import sys
import time
from pathlib import Path
from urllib.parse import urljoin
import requests
from datetime import datetime

BASE = "https://pimacountyaz-web.tylerhost.net"
# Endpoints to try (order matters)
CANDIDATE_PATHS = [
    "/web/document-image-pdf/DOC334S176//20252830551-1.pdf?index=1",
    "/web/document-image-pdfjs/DOC334S176/20252830551.pdf?allowDownload=true&index=1",
    "/web/document/servepdf/DEGRADED-DOC334S176.1.pdf/20252830551.pdf?index=1&allowDownload=true&allowPrint=true",
]
OUT = "pima_document_20252830551.pdf"

# Configuration for stress testing
NUM_DOWNLOADS = 50  # Number of times to download the PDF
DELAY_BETWEEN_REQUESTS = 0.1  # Seconds between requests (0.1 = 100ms)

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

def fetch(sess: requests.Session, url: str, attempt_num: int = 1) -> tuple[bytes|None, int, float]:
    """Fetch PDF and return (result, status_code, response_time)"""
    start_time = time.time()
    try:
        r = sess.get(url, headers=COMMON_HEADERS, stream=True, allow_redirects=True, timeout=60)
        response_time = time.time() - start_time
        
        if r.status_code >= 400:
            return None, r.status_code, response_time
        
        it = r.iter_content(chunk_size=8192)
        first = next(it, b"")
        if not is_pdf_prefix(first):
            return None, r.status_code, response_time
        
        # Save with attempt number to avoid overwriting
        output_file = f"pima_document_20252830551_attempt_{attempt_num}.pdf"
        tmp = Path(output_file + ".part").open("wb")
        with tmp as f:
            f.write(first)
            for chunk in it:
                if chunk:
                    f.write(chunk)
        Path(output_file + ".part").rename(output_file)
        return b"ok", r.status_code, response_time
    except Exception as e:
        response_time = time.time() - start_time
        print(f"[!] Error in attempt {attempt_num}: {e}")
        return None, 0, response_time

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

    # Statistics tracking
    successful_downloads = 0
    failed_downloads = 0
    total_time = 0
    status_codes = {}
    
    print(f"[*] Starting stress test: {NUM_DOWNLOADS} downloads with {DELAY_BETWEEN_REQUESTS}s delay")
    print(f"[*] Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Find working endpoint first
    working_url = None
    for path in CANDIDATE_PATHS:
        url = urljoin(BASE, path)
        print(f"[*] Testing endpoint: {url}")
        result, status_code, response_time = fetch(s, url, 0)
        if result:
            working_url = url
            print(f"[✓] Found working endpoint: {url}")
            break
        else:
            print(f"[✗] Endpoint failed with status {status_code}")
    
    if not working_url:
        print("[!] No working endpoints found!")
        return 2
    
    # Now stress test the working endpoint
    for attempt in range(1, NUM_DOWNLOADS + 1):
        print(f"\n[*] Download attempt {attempt}/{NUM_DOWNLOADS}")
        
        result, status_code, response_time = fetch(s, working_url, attempt)
        total_time += response_time
        
        # Track status codes
        status_codes[status_code] = status_codes.get(status_code, 0) + 1
        
        if result:
            successful_downloads += 1
            print(f"[✓] Success! Response time: {response_time:.2f}s")
        else:
            failed_downloads += 1
            print(f"[✗] Failed! Status: {status_code}, Response time: {response_time:.2f}s")
        
        # Add delay between requests
        if attempt < NUM_DOWNLOADS and DELAY_BETWEEN_REQUESTS > 0:
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Print final statistics
    print(f"\n{'='*50}")
    print("STRESS TEST RESULTS")
    print(f"{'='*50}")
    print(f"Total attempts: {NUM_DOWNLOADS}")
    print(f"Successful downloads: {successful_downloads}")
    print(f"Failed downloads: {failed_downloads}")
    print(f"Success rate: {(successful_downloads/NUM_DOWNLOADS)*100:.1f}%")
    print(f"Average response time: {total_time/NUM_DOWNLOADS:.2f}s")
    print(f"Total time: {total_time:.2f}s")
    print(f"Ended at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nStatus code distribution:")
    for code, count in sorted(status_codes.items()):
        print(f"  {code}: {count} times")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
