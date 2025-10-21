#!/usr/bin/env python3
"""
Pima County Document Search - Complete Multi-Page Scraper

This script:
1. Establishes session with Pima County Tyler Host system
2. Submits search query with date range and document types
3. Fetches ALL pages of results
4. Parses complete document information from each page
5. Consolidates everything into a single comprehensive JSON file

Features:
- Automatic pagination detection and processing
- Detailed document parsing including all available fields
- Robust error handling and retry logic
- Progress tracking and logging
- Session keep-alive during long operations
"""

import os
import time
import random
import re
import json
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

# =========================
# ======= CONFIG ==========
# =========================
BASE = "https://pimacountyaz-web.tylerhost.net"

# Date range (MM/DD/YYYY)
START_DATE = "07/01/2025"
END_DATE   = "10/21/2025"

# Document types:
DOC_TYPES = ["NTSALE", "CNLNT"]

# Output settings
OUTPUT_DIR = "Results"
OUTPUT_FILE = "pima_all_pages_complete.json"

# Request settings
STEP_DELAY = 0.5  # delay between requests
PAGE_DELAY = 1.0  # delay between pages
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# Verbose logging
VERBOSE = True

# =========================
# ==== END CONFIG =========
# =========================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

@dataclass
class DocumentRecord:
    """Structure for a single document record"""
    document_id: str = ""
    book_volume_page: str = ""
    document_type: str = ""
    document_type_description: str = ""
    recording_date: str = ""
    grantor: str = ""
    grantee: str = ""
    consideration: str = ""
    legal_description: str = ""
    document_url: str = ""
    additional_info: Dict[str, str] = None
    
    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}

@dataclass
class SearchResults:
    """Complete search results structure"""
    search_parameters: Dict[str, Any]
    total_pages: int
    total_records: int
    documents: List[DocumentRecord]
    search_timestamp: str
    processing_stats: Dict[str, Any]

class PimaCountyScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        })
        self.results = SearchResults(
            search_parameters={},
            total_pages=0,
            total_records=0,
            documents=[],
            search_timestamp=datetime.now().isoformat(),
            processing_stats={}
        )
        
    def vprint(self, *args, **kwargs):
        """Verbose print"""
        if VERBOSE:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}]", *args, **kwargs)
    
    def epoch_ms(self) -> str:
        """Current timestamp in milliseconds"""
        return str(int(time.time() * 1000))
    
    def ensure_ok(self, resp: requests.Response, label: str):
        """Ensure HTTP response is successful"""
        if not resp.ok:
            raise RuntimeError(f"{label}: HTTP {resp.status_code} - {resp.text[:200]}")
        return resp
    
    def ajax_get(self, url, referer=None, accept="text/html, */*; q=0.01", params=None, timeout=30):
        """Make AJAX GET request"""
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": accept,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if referer:
            headers["Referer"] = referer
        return self.session.get(url, params=params, headers=headers, timeout=timeout)
    
    def ajax_post(self, url, referer=None, origin=None, accept="*/*", data=b"", timeout=30):
        """Make AJAX POST request"""
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": accept,
        }
        if origin:
            headers["Origin"] = origin
        if referer:
            headers["Referer"] = referer
        return self.session.post(url, headers=headers, data=data, timeout=timeout)
    
    def establish_session(self):
        """Complete session establishment flow"""
        self.vprint("🔐 Establishing session...")
        
        # 1) GET disclaimer
        disclaimer = urljoin(BASE, "/web/user/disclaimer")
        r1 = self.session.get(disclaimer, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
        }, timeout=REQUEST_TIMEOUT)
        self.ensure_ok(r1, "GET disclaimer")
        self.vprint("✓ GET disclaimer")
        time.sleep(STEP_DELAY)
        
        # 2) POST disclaimer acceptance
        r2 = self.ajax_post(
            disclaimer, referer=disclaimer, origin=BASE,
            accept="application/json, text/javascript, */*; q=0.01", data=b""
        )
        self.ensure_ok(r2, "POST disclaimer")
        self.vprint("✓ POST disclaimer acceptance")
        time.sleep(STEP_DELAY)
        
        # 3) GET web root
        web_root = urljoin(BASE, "/web/")
        r3 = self.ajax_get(web_root, referer=disclaimer, accept="text/html, */*; q=0.01",
                          params={"_": self.epoch_ms()})
        self.ensure_ok(r3, "GET web root")
        self.vprint("✓ GET web root")
        time.sleep(STEP_DELAY)
        
        # 4) POST home actions
        home_actions = urljoin(BASE, "/web/homeActions")
        r4 = self.ajax_post(home_actions, referer=disclaimer, origin=BASE, data=b"")
        self.ensure_ok(r4, "POST home actions")
        self.vprint("✓ POST home actions")
        time.sleep(STEP_DELAY)
        
        # 5) GET action group
        action = urljoin(BASE, "/web/action/ACTIONGROUP55S1")
        r5 = self.ajax_get(action, referer=web_root, params={"_": self.epoch_ms()})
        self.ensure_ok(r5, "GET action group")
        self.vprint("✓ GET action group")
        time.sleep(STEP_DELAY)
        
        # 6) GET search page
        search = urljoin(BASE, "/web/search/DOCSEARCH55S8")
        r6 = self.ajax_get(search, referer=action, params={"_": self.epoch_ms()})
        self.ensure_ok(r6, "GET search page")
        self.vprint("✓ GET search page")
        time.sleep(STEP_DELAY)
        
        self.vprint("🔓 Session established successfully")
    
    def submit_search(self):
        """Submit search with configured parameters"""
        self.vprint(f"🔍 Submitting search: {START_DATE} to {END_DATE}, types: {DOC_TYPES}")
        
        # Validate dates
        for d in (START_DATE, END_DATE):
            try:
                datetime.strptime(d, "%m/%d/%Y")
            except ValueError:
                raise SystemExit(f"Invalid date '{d}'. Use MM/DD/YYYY.")
        
        # Build form data
        form = [
            ("field_RecordingDateID_DOT_StartDate", START_DATE),
            ("field_RecordingDateID_DOT_EndDate", END_DATE),
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
        
        # Store search parameters
        self.results.search_parameters = {
            "start_date": START_DATE,
            "end_date": END_DATE,
            "document_types": DOC_TYPES,
            "search_timestamp": self.results.search_timestamp
        }
        
        # Submit search
        url = urljoin(BASE, "/web/searchPost/DOCSEARCH55S8")
        r = self.session.post(
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
            timeout=REQUEST_TIMEOUT,
        )
        self.ensure_ok(r, "POST search")
        
        # Parse response to get total pages
        try:
            response_data = r.json()
            self.results.total_pages = response_data.get("totalPages", 1)
            self.vprint(f"✓ Search submitted - {self.results.total_pages} pages found")
        except json.JSONDecodeError:
            self.vprint("⚠️ Could not parse search response JSON, assuming 1 page")
            self.results.total_pages = 1
        
        time.sleep(STEP_DELAY)
    
    def fetch_page(self, page_num: int) -> Optional[str]:
        """Fetch a specific results page"""
        url = urljoin(BASE, "/web/searchResults/DOCSEARCH55S8")
        final_url = f"{url}?page={page_num}&_={self.epoch_ms()}"
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.get(final_url, headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                    "Referer": urljoin(BASE, "/web/search/DOCSEARCH55S8"),
                }, timeout=REQUEST_TIMEOUT)
                
                if r.status_code >= 500:
                    if attempt == MAX_RETRIES:
                        self.vprint(f"❌ Page {page_num} failed after {MAX_RETRIES} attempts")
                        return None
                    backoff = 0.7 * (1.8 ** (attempt - 1)) + random.uniform(0, 0.5)
                    self.vprint(f"⚠️ Page {page_num} attempt {attempt} failed, retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue
                
                self.ensure_ok(r, f"GET page {page_num}")
                return r.text
                
            except requests.RequestException as e:
                if attempt == MAX_RETRIES:
                    self.vprint(f"❌ Page {page_num} request failed: {e}")
                    return None
                self.vprint(f"⚠️ Page {page_num} request error, retrying: {e}")
                time.sleep(1)
        
        return None
    
    def parse_document_from_row(self, row_soup) -> Optional[DocumentRecord]:
        """Parse a single document row into a DocumentRecord"""
        try:
            doc = DocumentRecord()
            
            # Extract document ID from data-documentid attribute
            doc.document_id = row_soup.get('data-documentid', '')
            if not doc.document_id:
                # Fallback to ID attribute
                row_id = row_soup.get('id', '')
                if row_id.startswith('searchRow'):
                    doc.document_id = row_id.replace('searchRow', '')
            
            # Extract document number and type from header h1
            h1_elem = row_soup.find('h1')
            if h1_elem:
                h1_text = h1_elem.get_text(strip=True)
                # Pattern: document_number • document_type
                parts = h1_text.split('•')
                if len(parts) >= 1:
                    doc.book_volume_page = parts[0].strip()
                if len(parts) >= 2:
                    doc.document_type_description = parts[1].strip()
                    # Extract document type code
                    if 'NOTICE SALE' in doc.document_type_description:
                        doc.document_type = 'NTSALE'
                    elif 'CANCELLATION' in doc.document_type_description:
                        doc.document_type = 'CNLNT'
            
            # Extract document URL
            href_attr = row_soup.get('data-href', '')
            if href_attr:
                doc.document_url = urljoin(BASE, href_attr)
            
            # Parse the three-column structure
            columns = row_soup.find_all('div', class_='searchResultThreeColumn')
            
            for column in columns:
                # Get the column header
                header_li = column.find('li')
                if not header_li:
                    continue
                
                header_text = header_li.get_text(strip=True).lower()
                
                # Get all value list items (excluding the header)
                value_lis = column.find_all('li')[1:]  # Skip first li which is the header
                
                if 'recording date' in header_text:
                    for li in value_lis:
                        date_text = li.get_text(strip=True)
                        # Clean up the date - remove bold tags and extra text
                        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_text)
                        if date_match:
                            doc.recording_date = date_match.group(1)
                            break
                
                elif 'grantor' in header_text:
                    grantors = []
                    for li in value_lis:
                        grantor_name = li.get_text(strip=True)
                        if grantor_name:
                            grantors.append(grantor_name)
                    if grantors:
                        doc.grantor = ' | '.join(grantors)  # Join multiple grantors
                
                elif 'grantee' in header_text:
                    grantees = []
                    for li in value_lis:
                        grantee_name = li.get_text(strip=True)
                        if grantee_name:
                            grantees.append(grantee_name)
                    if grantees:
                        doc.grantee = ' | '.join(grantees)  # Join multiple grantees
                
                elif 'consideration' in header_text:
                    for li in value_lis:
                        consideration_text = li.get_text(strip=True)
                        if consideration_text:
                            doc.consideration = consideration_text
                            break
                
                elif 'legal' in header_text or 'description' in header_text:
                    for li in value_lis:
                        legal_text = li.get_text(strip=True)
                        if legal_text:
                            doc.legal_description = legal_text
                            break
            
            # Extract additional information
            additional_info = {}
            
            # Get all data attributes from the main row
            for attr, value in row_soup.attrs.items():
                if attr.startswith('data-') and value:
                    key = attr.replace('data-', '').replace('-', '_')
                    additional_info[key] = str(value)
            
            # Look for any action links (print, view, cart)
            action_links = row_soup.find_all('a', href=True)
            for link in action_links:
                href = link.get('href', '')
                title = link.get('title', '')
                if title:
                    if 'view' in title.lower():
                        additional_info['view_url'] = urljoin(BASE, href)
                    elif 'print' in title.lower():
                        additional_info['print_function'] = link.get('data-function', '')
                    elif 'cart' in title.lower():
                        additional_info['cart_function'] = link.get('data-function', '')
            
            # Get avatar information (document status indicator)
            avatar = row_soup.find('div', class_=re.compile(r'ss-facet-avatar'))
            if avatar:
                avatar_class = ' '.join(avatar.get('class', []))
                avatar_text = avatar.get_text(strip=True)
                additional_info['status_indicator'] = avatar_text
                additional_info['status_class'] = avatar_class
            
            doc.additional_info = additional_info
            
            # Only return if we have meaningful data
            if any([doc.document_id, doc.recording_date, doc.grantor, doc.grantee, doc.document_type_description, doc.book_volume_page]):
                return doc
            
        except Exception as e:
            self.vprint(f"⚠️ Error parsing document row: {e}")
        
        return None
    
    def parse_page(self, html_content: str, page_num: int) -> List[DocumentRecord]:
        """Parse all documents from a page of HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            documents = []
            
            # Look for the specific search results container
            search_result_container = soup.find('ul', class_='selfServiceSearchResultList')
            
            if search_result_container:
                # Find all document rows within the container
                document_rows = search_result_container.find_all('li', class_='ss-search-row')
                
                self.vprint(f"📄 Page {page_num}: Found {len(document_rows)} document rows in main container")
                
                # Parse each row
                for i, row in enumerate(document_rows):
                    doc = self.parse_document_from_row(row)
                    if doc:
                        documents.append(doc)
                        self.vprint(f"  ✓ Parsed document {i+1}: ID={doc.document_id}, Type={doc.document_type_description}")
                    else:
                        self.vprint(f"  ⚠️ Could not parse row {i+1}")
            else:
                # Fallback: look for any elements with ss-search-row class
                document_rows = soup.find_all('li', class_='ss-search-row')
                
                if document_rows:
                    self.vprint(f"📄 Page {page_num}: Found {len(document_rows)} document rows (fallback method)")
                    
                    for i, row in enumerate(document_rows):
                        doc = self.parse_document_from_row(row)
                        if doc:
                            documents.append(doc)
                            self.vprint(f"  ✓ Parsed document {i+1}: ID={doc.document_id}, Type={doc.document_type_description}")
                        else:
                            self.vprint(f"  ⚠️ Could not parse row {i+1}")
                else:
                    self.vprint(f"⚠️ Page {page_num}: No document rows found with expected structure")
                    
                    # Debug: save the page content for analysis
                    debug_file = os.path.join(OUTPUT_DIR, f"debug_page_{page_num}.html")
                    os.makedirs(OUTPUT_DIR, exist_ok=True)
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    self.vprint(f"  💾 Saved page content to {debug_file} for debugging")
            
            return documents
            
        except Exception as e:
            self.vprint(f"❌ Error parsing page {page_num}: {e}")
            
            # Save error page for debugging
            error_file = os.path.join(OUTPUT_DIR, f"error_page_{page_num}.html")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            try:
                with open(error_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.vprint(f"  💾 Saved error page to {error_file}")
            except:
                pass
                
            return []
    
    def ping_session(self):
        """Send keep-alive ping to maintain session"""
        try:
            ping_url = urljoin(BASE, "/web/session/pingSession")
            r = self.session.get(ping_url, params={"_": self.epoch_ms()}, headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                "Referer": urljoin(BASE, "/web/search/DOCSEARCH55S8"),
            }, timeout=10)
            
            if r.status_code in (401, 403):
                self.vprint("⚠️ Session expired, may need to re-authenticate")
                return False
            return True
        except:
            return False
    
    def scrape_all_pages(self):
        """Main method to scrape all pages"""
        self.vprint(f"🚀 Starting complete scrape of {self.results.total_pages} pages...")
        
        start_time = time.time()
        successful_pages = 0
        failed_pages = []
        
        for page_num in range(1, self.results.total_pages + 1):
            self.vprint(f"📑 Processing page {page_num}/{self.results.total_pages}...")
            
            # Periodic session ping
            if page_num % 5 == 0:
                self.ping_session()
            
            # Fetch page
            html_content = self.fetch_page(page_num)
            if html_content is None:
                failed_pages.append(page_num)
                continue
            
            # Parse documents from page
            page_documents = self.parse_page(html_content, page_num)
            self.results.documents.extend(page_documents)
            successful_pages += 1
            
            self.vprint(f"✓ Page {page_num} complete: {len(page_documents)} documents extracted")
            
            # Delay between pages to be respectful
            if page_num < self.results.total_pages:
                time.sleep(PAGE_DELAY)
        
        # Calculate final stats
        end_time = time.time()
        total_time = end_time - start_time
        
        self.results.total_records = len(self.results.documents)
        self.results.processing_stats = {
            "total_pages_attempted": self.results.total_pages,
            "successful_pages": successful_pages,
            "failed_pages": failed_pages,
            "total_documents_extracted": self.results.total_records,
            "processing_time_seconds": round(total_time, 2),
            "average_time_per_page": round(total_time / max(successful_pages, 1), 2),
            "completion_rate": round(successful_pages / self.results.total_pages * 100, 1) if self.results.total_pages > 0 else 0
        }
        
        self.vprint(f"🎉 Scraping complete!")
        self.vprint(f"   📊 Total documents: {self.results.total_records}")
        self.vprint(f"   ⏱️ Total time: {total_time:.1f}s")
        self.vprint(f"   ✅ Success rate: {self.results.processing_stats['completion_rate']}%")
        
        if failed_pages:
            self.vprint(f"   ❌ Failed pages: {failed_pages}")
    
    def save_results(self):
        """Save all results to JSON file"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        
        # Convert dataclasses to dictionaries
        results_dict = {
            "search_parameters": self.results.search_parameters,
            "total_pages": self.results.total_pages,
            "total_records": self.results.total_records,
            "documents": [asdict(doc) for doc in self.results.documents],
            "search_timestamp": self.results.search_timestamp,
            "processing_stats": self.results.processing_stats
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        self.vprint(f"💾 Results saved to: {output_path}")
        self.vprint(f"   📄 File size: {os.path.getsize(output_path) / 1024:.1f} KB")
        
        return output_path
    
    def run(self):
        """Main execution method"""
        try:
            self.establish_session()
            self.submit_search()
            
            if self.results.total_pages > 0:
                self.scrape_all_pages()
                output_file = self.save_results()
                
                self.vprint("\n" + "="*60)
                self.vprint("🏁 SCRAPING COMPLETED SUCCESSFULLY")
                self.vprint("="*60)
                self.vprint(f"📂 Output file: {output_file}")
                self.vprint(f"📊 Documents extracted: {self.results.total_records}")
                self.vprint(f"📄 Pages processed: {self.results.processing_stats.get('successful_pages', 0)}/{self.results.total_pages}")
                self.vprint(f"⏱️ Total time: {self.results.processing_stats.get('processing_time_seconds', 0)}s")
                self.vprint("="*60)
            else:
                self.vprint("❌ No search results found")
                
        except KeyboardInterrupt:
            self.vprint("\n⚠️ Process interrupted by user")
            if self.results.documents:
                self.vprint("💾 Saving partial results...")
                self.save_results()
        except Exception as e:
            self.vprint(f"\n❌ Error during execution: {e}")
            if self.results.documents:
                self.vprint("💾 Saving partial results...")
                self.save_results()
            raise

def main():
    """Main entry point"""
    print("🌟 Pima County Complete Document Scraper")
    print("="*50)
    print(f"📅 Date range: {START_DATE} to {END_DATE}")
    print(f"📋 Document types: {DOC_TYPES}")
    print(f"💾 Output: {os.path.join(OUTPUT_DIR, OUTPUT_FILE)}")
    print("="*50)
    
    scraper = PimaCountyScraper()
    scraper.run()

if __name__ == "__main__":
    main()