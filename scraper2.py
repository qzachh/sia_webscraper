#!/usr/bin/env python3
"""
Scrape iamarchitect.sg 'Find Architect Specialist' directory
and save as architect_specialists.csv
"""

import time
import csv
import requests
from bs4 import BeautifulSoup
import html
import re

BASE_URL = "https://iamarchitect.sg/search-specialist/?find"
TOTAL_PAGES = 21
OUTPUT_FILE = "architect_specialists.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

def cf_decode(hex_str: str) -> str:
    """Decode Cloudflare email protection hex string."""
    try:
        # Clean the hex string
        hex_str = hex_str.strip()
        if len(hex_str) < 2:
            return ""
            
        key = int(hex_str[:2], 16)
        result = ""
        
        for i in range(2, len(hex_str), 2):
            if i + 1 < len(hex_str):
                byte_val = int(hex_str[i:i + 2], 16)
                result += chr(byte_val ^ key)
        
        return result
    except Exception as e:
        print(f"    Error decoding hex: {hex_str} - {e}")
        return ""

def decode_html_entities(text: str) -> str:
    """Decode HTML entities like &#64; to actual characters."""
    return html.unescape(text)

def extract_email_from_text(text: str) -> str:
    """Extract email from text that may contain HTML entities."""
    # First decode HTML entities
    decoded = decode_html_entities(text)
    
    # Look for email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, decoded)
    
    if match:
        return match.group(0)
    return ""

def clean_company_name(company: str) -> str:
    """Clean company name by removing PTE LTD and converting to title case."""
    if not company:
        return ""
    
    # Remove PTE LTD (case insensitive)
    cleaned = re.sub(r'\s*PTE\s*LTD\s*', '', company, flags=re.IGNORECASE)
    
    # Convert to title case
    return cleaned.strip().title()

def parse_name(full_name: str) -> tuple:
    """Parse full name into first name and last name."""
    if not full_name:
        return "", ""
    
    # Convert to title case first
    full_name = full_name.strip().title()
    
    # Split by spaces and commas
    parts = re.split(r'[,\s]+', full_name)
    parts = [part.strip() for part in parts if part.strip()]
    
    if not parts:
        return "", ""
    elif len(parts) == 1:
        # Only one name, treat as first name
        return parts[0], ""
    else:
        # Multiple parts - typically first name is first, last name is last
        first_name = parts[0]
        last_name = parts[-1]
        return first_name, last_name

def scrape_page(p: int):
    """Yield (name, company, email) tuples for one page."""
    url = f"{BASE_URL}&pg={p}"
    print(f"  Scraping: {url}")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  ! Error fetching page {p}: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try the testimonial-cite selector first
    cards = soup.select("div.testimonial-cite")
    
    if cards:
        print(f"  Found {len(cards)} cards using testimonial-cite selector")
        for card in cards:
            name = card.select_one("h2.testimonial-entry-title")
            company = card.select_one("p.search-specialist-grey-txt")
            encoded = card.select_one("a.__cf_email__")

            name_txt = name.get_text(strip=True) if name else ""
            company_txt = company.get_text(strip=True) if company else ""

            # Decode email if present
            if encoded and encoded.has_attr("data-cfemail"):
                email_txt = cf_decode(encoded["data-cfemail"])
                print(f"    Primary method - CF email: {email_txt}")
            else:
                # Try to find email in other ways
                email_txt = ""
                
                # Look for any email protection links
                protection_links = card.select("a[href*='email-protection']")
                for link in protection_links:
                    href = link.get("href", "")
                    text = link.get_text(strip=True)
                    print(f"    Protection link: href='{href}', text='{text}'")
                    
                    if "#" in href:
                        hex_part = href.split("#")[-1]
                        decoded = cf_decode(hex_part)
                        if decoded and "@" in decoded:
                            email_txt = decoded
                            print(f"    Decoded from protection link: {email_txt}")
                            break
                    
                    # Also check link text for email
                    if "@" in text:
                        decoded = extract_email_from_text(text)
                        if decoded:
                            email_txt = decoded
                            print(f"    Email from link text: {email_txt}")
                            break
                
                # If still no email, look for @ in card text
                if not email_txt:
                    card_text = card.get_text()
                    if "@" in card_text:
                        email_txt = extract_email_from_text(card_text)
                        print(f"    Email from card text: {email_txt}")
                
                # Check all links in the card
                if not email_txt:
                    all_links = card.select("a")
                    for link in all_links:
                        href = link.get("href", "")
                        text = link.get_text(strip=True)
                        print(f"    All links: href='{href}', text='{text}'")
                        
                        if "mailto:" in href:
                            email_txt = href.replace("mailto:", "")
                            print(f"    Mailto found: {email_txt}")
                            break

            # Clean and format the data
            first_name, last_name = parse_name(name_txt)
            full_name = name_txt.strip().title() if name_txt else ""
            cleaned_company = clean_company_name(company_txt)

            yield (first_name, last_name, full_name, cleaned_company, email_txt)
    else:
        # Fallback: Try alternative selectors
        print(f"  No testimonial-cite cards found, trying alternative selectors...")
        
        # Try other possible card selectors
        alternative_selectors = [
            "div.search-result-item",
            "div.search-specialist-result-item",
            "div[class*='result']",
            "div[class*='specialist']"
        ]
        
        cards_found = False
        for selector in alternative_selectors:
            cards = soup.select(selector)
            if cards:
                print(f"  Found {len(cards)} cards using {selector}")
                cards_found = True
                
                for card in cards:
                    # Extract name - try multiple possible selectors
                    name = (card.select_one("h2") or 
                           card.select_one("h3") or 
                           card.select_one("h4") or 
                           card.select_one("h5") or
                           card.select_one(".name") or
                           card.select_one(".title"))
                    
                    # Extract company - try multiple possible selectors
                    company = (card.select_one("p.search-specialist-grey-txt") or
                              card.select_one("p.sub-title-1") or
                              card.select_one("p.subtitle") or
                              card.select_one(".company") or
                              card.select_one(".organisation"))
                    
                    # Extract email - try multiple approaches
                    email_txt = ""
                    
                    # Method 1: Cloudflare protected email with data-cfemail
                    encoded = card.select_one("a.__cf_email__")
                    if encoded and encoded.has_attr("data-cfemail"):
                        email_txt = cf_decode(encoded["data-cfemail"])
                        print(f"    Method 1 - CF email: {email_txt}")
                    
                    # Method 2: Regular mailto link
                    if not email_txt:
                        mailto_link = card.select_one("a[href^='mailto:']")
                        if mailto_link:
                            email_txt = mailto_link.get("href", "").replace("mailto:", "")
                            print(f"    Method 2 - Mailto: {email_txt}")
                    
                    # Method 3: Look for email protection links in href
                    if not email_txt:
                        protection_links = card.select("a[href*='email-protection']")
                        for link in protection_links:
                            href = link.get("href", "")
                            print(f"    Found protection link: {href}")
                            if "#" in href:
                                hex_part = href.split("#")[-1]
                                decoded = cf_decode(hex_part)
                                if decoded and "@" in decoded:
                                    email_txt = decoded
                                    print(f"    Method 3 - Protection link: {email_txt}")
                                    break
                    
                    # Method 4: Look for span with CF email class
                    if not email_txt:
                        cf_span = card.select_one("span.__cf_email__")
                        if cf_span and cf_span.has_attr("data-cfemail"):
                            email_txt = cf_decode(cf_span["data-cfemail"])
                            print(f"    Method 4 - CF span: {email_txt}")
                    
                    # Method 5: Look for email in text content with @ symbol
                    if not email_txt:
                        card_text = card.get_text()
                        if "@" in card_text:
                            email_txt = extract_email_from_text(card_text)
                            print(f"    Method 5 - Text extraction: {email_txt}")
                    
                    # Method 6: Parse all links in the card for any email patterns
                    if not email_txt:
                        all_links = card.select("a")
                        for link in all_links:
                            href = link.get("href", "")
                            text = link.get_text(strip=True)
                            print(f"    Link found: href='{href}', text='{text}'")
                            
                            # Check if link text contains email
                            if "@" in text:
                                decoded = extract_email_from_text(text)
                                if decoded:
                                    email_txt = decoded
                                    print(f"    Method 6 - Link text: {email_txt}")
                                    break
                    
                    name_txt = name.get_text(strip=True) if name else ""
                    company_txt = company.get_text(strip=True) if company else ""
                    
                    # Clean and format the data
                    first_name, last_name = parse_name(name_txt)
                    full_name = name_txt.strip().title() if name_txt else ""
                    cleaned_company = clean_company_name(company_txt)
                    
                    yield (first_name, last_name, full_name, cleaned_company, email_txt)
                
                break  # Stop trying other selectors if we found cards
        
        if not cards_found:
            print(f"  No cards found with any selector on page {p}")
            
            # Last resort: Parse the entire page content
            print(f"  Trying to parse entire page content...")
            
            # Look for email protection patterns in the raw HTML
            email_protection_pattern = r'/cdn-cgi/l/email-protection#([a-fA-F0-9]+)'
            email_matches = re.findall(email_protection_pattern, resp.text)
            
            if email_matches:
                print(f"  Found {len(email_matches)} email protection codes")
                for email_code in email_matches:
                    decoded_email = cf_decode(email_code)
                    if decoded_email:
                        # Try to find context around this email
                        first_name, last_name = parse_name("Name not found")
                        full_name = "Name Not Found"
                        cleaned_company = clean_company_name("Company not found")
                        yield (first_name, last_name, full_name, cleaned_company, decoded_email)

def main():
    print("Starting scrape of iamarchitect.sg specialist directory...")
    
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["First Name", "Last Name", "Full Name", "Company Name", "Email"])

        total = 0
        for page in range(1, TOTAL_PAGES + 1):
            print(f"Page {page}/{TOTAL_PAGES}")
            try:
                page_count = 0
                for record in scrape_page(page):
                    if any(record):  # Only write if at least one field has data
                        writer.writerow(record)
                        total += 1
                        page_count += 1
                
                print(f"  Extracted {page_count} records from page {page}")
                
                if page_count == 0:
                    print(f"  No records found on page {page} - might be end of results")
                
            except Exception as e:
                print(f"  ! Page {page} skipped due to error: {e}")
            
            time.sleep(1)  # Be polite to the server

    print(f"\nDone! {total} specialists saved to {OUTPUT_FILE}")
    
    # Show some statistics
    if total > 0:
        print(f"\nReading back the file to show statistics...")
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                data = list(reader)
                
                names_found = sum(1 for row in data if (row["First Name"] and row["First Name"] != "Name") or (row["Last Name"] and row["Last Name"] != "Not"))
                companies_found = sum(1 for row in data if row["Company Name"] and row["Company Name"] != "Found")
                emails_found = sum(1 for row in data if row["Email"] and "@" in row["Email"])
                
                print(f"Statistics:")
                print(f"- Names found: {names_found}/{total}")
                print(f"- Companies found: {companies_found}/{total}")
                print(f"- Emails found: {emails_found}/{total}")
                
                if len(data) > 0:
                    print(f"\nFirst few records:")
                    for i, row in enumerate(data[:3]):
                        print(f"  {i+1}. {row['First Name']} {row['Last Name']} | {row['Full Name']} | {row['Company Name']} | {row['Email']}")
        
        except Exception as e:
            print(f"Error reading back file: {e}")

if __name__ == "__main__":
    main()
