"""
Monthly Sync Script for Motorcycle Specifications (Cron Job)

Security Document: 
This script connects to the source URLs specified in the Firestore catalog and scrapes them to update the `ficha_tecnica` field. 
It mitigates LLM hallucinations by providing a constantly updated ground truth. 
To prevent injection attacks and minimize storage bloat, URLs are parsed using beautifulsoup and all HTML is stripped away, saving only raw text truncated to 2000 characters.

Fail-Continuous Architecture: Wrapped inside a try/except so if one URL fails, it moves to the next.
"""

import os
import sys
import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from google.cloud import firestore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_SPECS_LENGTH = 2000
TIMEOUT_SECONDS = 15

async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    """Fetch URL and return text/html."""
    try:
        # Use headers to mimic a regular browser in case of basic anti-bot measures
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = await client.get(url, headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return ""

def sanitize_html(html_content: str) -> str:
    """Strip HTML tags and truncate string to avoid NoSQL injection or large payloads."""
    if not html_content:
        return ""
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "header", "footer"]):
        script.extract()
        
    # Get text
    text = soup.get_text(separator=' ', strip=True)
    
    # Truncate
    if len(text) > MAX_SPECS_LENGTH:
        text = text[:MAX_SPECS_LENGTH] + "..."
        
    return text

async def sync_catalog(dry_run: bool = False):
    """Main synchronization function triggered by cron."""
    logger.info("🚀 Starting Monthly Catalog Specs Sync...")
    if dry_run:
        logger.info("🧪 RUNNING IN DRY-RUN MODE (No Firebase writes will occur)")
    
    try:
        # Initialize Firestore using Application Default Credentials
        db = firestore.Client(project="tiendalasmotos")
        
        # Reference the catalog collection
        items_ref = db.collection("pagina").document("catalogo").collection("items")
        docs = items_ref.stream()
        
        # Async HTTP client
        async with httpx.AsyncClient() as client:
            for doc in docs:
                try: # Fail-Continuous loop
                    data = doc.to_dict()
                    item_id = doc.id
                    name = data.get("referencia") or data.get("nombre") or data.get("title") or item_id
                    
                    # Check for URL
                    url = data.get("url") or data.get("link")
                    
                    if not url:
                        logger.info(f"⏭️ Skipping {name} ({item_id}) - No URL found.")
                        continue
                        
                    logger.info(f"⏳ Processing {name} ({item_id}) from URL: {url}")
                    
                    # Fetch content
                    html_content = await fetch_url(client, url)
                    
                    if not html_content:
                        logger.warning(f"⚠️ Could not fetch content for {name}, skipping.")
                        continue
                        
                    # Sanitize and extract
                    specs_text = sanitize_html(html_content)
                    
                    if not specs_text:
                        logger.warning(f"⚠️ No text extracted for {name}, skipping.")
                        continue
                        
                    # Update Firestore
                    logger.info(f"💾 Updating ficha_tecnica for {name} ({len(specs_text)} chars).")
                    
                    if not dry_run:
                        doc_ref = items_ref.document(item_id)
                        doc_ref.update({
                            "ficha_tecnica": specs_text
                        })
                        logger.info(f"✅ Successfully updated {name}.")
                    else:
                        logger.info(f"🧪 [DRY-RUN] Would have updated {name} with: {specs_text[:100]}...")
                        break # Only process one in dry run for testing

                except Exception as loop_err:
                    logger.error(f"❌ Error processing document {doc.id}: {loop_err}")
                    continue # Ensure the loop continues even if one fails
                    
        logger.info("🎉 Catalog Specs Sync Complete!")
        
    except Exception as e:
        logger.error(f"❌ Critical error during sync: {e}", exc_info=True)

def main():
    """Synchronous entry point for the script."""
    # Check if this is a dry run
    dry_run = "--dry-run" in sys.argv
    asyncio.run(sync_catalog(dry_run=dry_run))

if __name__ == "__main__":
    main()
