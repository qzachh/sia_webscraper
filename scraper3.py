# DNW
"""
Scrape iamarchitect.sg 'Find Architect Specialist' directory
and save as architect_specialists.csv
"""

import time
import csv
import requests
from bs4 import BeautifulSoup

BASE_URL   = "https://iamarchitect.sg/search-specialist/?find"
TOTAL_PAGES = 21
OUTPUT_FILE = "architect_specialists.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def cf_decode(hex_str: str) -> str:
    """Decode Cloudflare email protection hex string."""
    key = int(hex_str[:2], 16)
    return "".join(
        chr(int(hex_str[i:i + 2], 16) ^ key)  # XOR each byte with the key
        for i in range(2, len(hex_str), 2)
    )

def scrape_page(p: int):
    """Yield (name, company, email) tuples for one page."""
    url = f"{BASE_URL}&pg={p}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    for card in soup.select("div.testimonial-cite"):
        name = card.select_one("h2.testimonial-entry-title")
        company = card.select_one("p.search-specialist-grey-txt")
        encoded = card.select_one("a.__cf_email__")

        name_txt    = name.get_text(strip=True) if name else ""
        company_txt = company.get_text(strip=True) if company else ""

        # decode e-mail if present
        if encoded and encoded.has_attr("data-cfemail"):
            email_txt = cf_decode(encoded["data-cfemail"])
        else:
            email_txt = ""

        yield (name_txt, company_txt, email_txt)

def main():
    print("Starting scrape…")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Company Name", "Email"])

        total = 0
        for page in range(1, TOTAL_PAGES + 1):
            print(f"· Page {page}/{TOTAL_PAGES}")
            try:
                for record in scrape_page(page):
                    writer.writerow(record)
                    total += 1
            except Exception as e:
                print(f"  ! Page {page} skipped ({e})")
            time.sleep(1)                       # be polite

    print(f"Done – {total} specialists saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
