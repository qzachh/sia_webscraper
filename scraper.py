# DNW
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re # Import the regular expressions module

# --- Configuration ---
SEARCH_PAGE_URL = "https://iamarchitect.sg/search-specialist/?find"
API_URL = "https://iamarchitect.sg/wp-admin/admin-ajax.php"
TOTAL_PAGES = 21
OUTPUT_FILENAME = 'architect_specialists.csv'

# --- Main Script ---

# Headers to make our script look like a regular browser
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
}

# --- Step 1: Get the Security Token ---
print("➡️ Step 1: Fetching the main page to find the security token...")
try:
    # First, visit the main search page to get the HTML and cookies
    main_page_response = requests.get(SEARCH_PAGE_URL, headers=headers)
    main_page_response.raise_for_status()
    
    # Use BeautifulSoup to parse the page content
    soup = BeautifulSoup(main_page_response.text, 'html.parser')
    
    # Find the specific script tag containing the token
    # We search for a script tag that contains the text 'sia_specialist_obj'
    script_tag = soup.find('script', string=re.compile(r'sia_specialist_obj'))
    
    # Use a regular expression to extract the security token from the script's text
    match = re.search(r'"security":"(.*?)"', script_tag.string)
    
    if match:
        security_token = match.group(1)
        print(f"✅ Security token found: {security_token}")
    else:
        print("❌ Could not find security token. The website structure may have changed. Exiting.")
        exit() # Exit the script if no token is found

except requests.exceptions.RequestException as e:
    print(f"❌ Could not load the main page: {e}. Exiting.")
    exit()
except AttributeError:
    print("❌ Could not find the script tag containing the security token. Exiting.")
    exit()

# --- Step 2: Scrape the Data Using the Token ---
print("\n➡️ Step 2: Starting to scrape data from the API...")
all_specialists_data = []

for page_num in range(1, TOTAL_PAGES + 1):
    print(f"Requesting data for page {page_num} of {TOTAL_PAGES}...")

    # The data payload now INCLUDES the security token
    payload = {
        'action': 'search_specialist',
        'find': '',
        'pg': page_num,
        'security': security_token # Add the token here
    }

    try:
        response = requests.post(API_URL, data=payload, headers=headers)
        response.raise_for_status()
        
        json_response = response.json()
        
        # Check if the API call was successful from the server's perspective
        if not json_response.get('success'):
            print(f"API returned an error for page {page_num}: {json_response.get('data')}")
            continue

        html_content = json_response.get('data', '')

        if not html_content:
            print(f"No HTML content returned for page {page_num}.")
            break
        
        soup = BeautifulSoup(html_content, 'html.parser')
        specialist_cards = soup.find_all('div', class_='search-result-item')

        if not specialist_cards:
            print(f"No specialists found in the HTML for page {page_num}. This might be the last page.")
            break

        for card in specialist_cards:
            name_tag = card.find('h5')
            name = name_tag.text.strip() if name_tag else "Not available"
            
            company_tag = card.find('p', class_='sub-title-1')
            company = company_tag.text.strip() if company_tag else "Not available"

            email_tag = card.find('a', href=lambda href: href and href.startswith('mailto:'))
            email = email_tag['href'].replace('mailto:', '').strip() if email_tag else "Not available"

            all_specialists_data.append({
                "Name": name, "Company Name": company, "Email": email
            })
            
        time.sleep(1)

    except requests.exceptions.RequestException as e:
        print(f"Error requesting page {page_num}: {e}")
        continue
    except Exception as e:
        print(f"An unexpected error occurred on page {page_num}: {e}")
        continue

# --- Step 3: Save the Data ---
if all_specialists_data:
    print("\n➡️ Step 3: Saving data to CSV file...")
    df = pd.DataFrame(all_specialists_data)
    df.to_csv(OUTPUT_FILENAME, index=False, encoding='utf-8')
    print(f"✅ Scraping complete! All data saved to '{OUTPUT_FILENAME}'")
    print(f"Total specialists extracted: {len(df)}")
else:
    print("\nNo data was extracted. The website's API may have changed or blocked the request.")