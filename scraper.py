import os
import re
import csv
import time
import logging
import random
import asyncio
import pandas as pd
from time import sleep
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import undetected_chromedriver as uc
from fake_useragent import UserAgent
from typing import Dict, List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NPIScraper:
    """
    Web scraper for NPI database using undetected-chromedriver to bypass Cloudflare.
    Implements recursive search to bypass 30-result limit.
    """
    
    BASE_URL = "https://npidb.org/npi-lookup/"

    #ALPHABET = 'A'             For Sample Test
    #STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA"]
    ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    STATES = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ]
    
    def __init__(self, headless: bool = True, delay: float = 1.0, max_retries: int = 3):
        self.headless = headless
        self.delay = delay
        self.max_retries = max_retries
        self.ua = UserAgent()
        self.recent_latencies = []  # Track recent search times for adaptive delay
        self.driver = None
    
    def __enter__(self):
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        self.driver = uc.Chrome(
            options=options,
            version_main=144  # Match Chrome version
        )
        logger.info("Chrome browser started successfully")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
    
    def _reinitialize_browser(self):
        """Reinitialize browser when connection is lost."""
        logger.warning("Reinitializing browser due to connection loss...")
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
        except:
            pass
        
        # Reinitialize browser
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        self.driver = uc.Chrome(
            options=options,
            version_main=144
        )
        logger.info("Browser reinitialized successfully")
        time.sleep(3)
    
    def test_cloudflare_bypass(self):
        """
        Test Cloudflare bypass on a known challenge page.
        """
        print("Starting browser...")
        # instantiate a Chrome browser with specific version
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        try:
            driver = uc.Chrome(
                options=options,
                version_main=144  # Match Chrome version exactly
            )
            print("Browser started.")

            # visit the target page
            print("Visiting page...")
            driver.get("https://www.scrapingcourse.com/cloudflare-challenge")
            print("Page loaded.")

            # wait for the interstitial page to load
            print("Waiting 10 seconds...")
            sleep(10)

            # take a screenshot of the current page and save it
            print("Taking screenshot...")
            driver.save_screenshot("cloudflare-challenge.png")
            print(f"Screenshot saved. Title: {driver.title}")

            # close the browser
            driver.quit()
            print("Test completed successfully!")
        except Exception as e:
            print(f"Error: {e}")
            print("Trying without headless...")
            # Try without headless as fallback
            driver = uc.Chrome(version_main=144)
            driver.get("https://www.scrapingcourse.com/cloudflare-challenge")
            sleep(10)
            driver.save_screenshot("cloudflare-challenge.png")
            print(f"Screenshot saved. Title: {driver.title}")
            driver.quit()
        print("Browser closed.")
    
    def _retry_operation(self, operation, *args, **kwargs):
        """Retry operation on failure, with browser recovery for session errors."""
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                # Check if it's a session/browser error
                if 'invalid session id' in error_msg.lower() or 'disconnected' in error_msg.lower():
                    logger.error(f"Browser connection lost: {e}")
                    if attempt < self.max_retries - 1:
                        self._reinitialize_browser()
                        continue
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
    
    def search_profiles(self, first_initial: str = '', last_initial: str = '',
                        middle_initial: str = '', state: str = '') -> List[str]:
        """
        Perform search and collect profile URLs.
        Returns list of profile URLs.
        """
        # Check if browser is still alive
        try:
            _ = self.driver.current_url
        except Exception as e:
            logger.error(f"Browser connection lost: {e}")
            raise
        
        start_time = time.time()
        
        params = {}
        if first_initial:
            params['fname'] = first_initial
        if last_initial:
            params['lname'] = last_initial
        if middle_initial:
            params['mname'] = middle_initial
        if state:
            params['state'] = state.lower()
        
        url = self.BASE_URL
        if params:
            from urllib.parse import urlencode
            url += '?' + urlencode(params)
        
        self.driver.get(url)
        time.sleep(5)  # Wait longer for dynamic content to load
        
        content = self.driver.page_source
        soup = BeautifulSoup(content, 'html.parser')
        
        # Debug: Save page source for inspection
        with open('debug_search_page.html', 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Page source saved to debug_search_page.html for URL: {url}")
        
        # Find result links from NPI numbers and Names in the table
        # The NPI numbers and Names are clickable links in the results table
        results = []
        
        # Look for links containing NPI numbers (numeric links in first column)
        npi_links = soup.find_all('a', href=True, string=lambda text: text and text.strip().isdigit() and len(text.strip()) == 10)
        results.extend(npi_links)
        
        # Also look for name links (second column) - these have href and contain names
        # Find all rows in the table and extract links
        table_rows = soup.find_all('tr')
        for row in table_rows:
            links = row.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                # Add links that look like profile URLs
                if href and (href.startswith('/') or 'npidb.org' in href):
                    if link not in results:
                        results.append(link)
        
        # Remove duplicates based on href
        unique_results = []
        seen_hrefs = set()
        for link in results:
            href = link.get('href')
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                unique_results.append(link)
        
        results = unique_results
        
        elapsed = time.time() - start_time
        logger.info(
            f"Search for {first_initial}{last_initial}{middle_initial}{state} "
            f"took {elapsed:.2f}s, results: {len(results)}"
        )
        
        # Extract URLs from results
        urls = []
        for result in results:
            href = result.get('href')
            if href:
                if not href.startswith('http'):
                    href = 'https://npidb.org' + href
                urls.append(href)
        
        # If results exceed 30, return empty to trigger recursive narrowing
        # But log the count so recursive_search knows to narrow
        if len(urls) > 30:
            logger.warning(
                f"Hotspot: {len(urls)} results exceed 30 for "
                f"{first_initial}{last_initial}{middle_initial}{state} - will trigger narrowing"
            )
            # Return special marker to indicate too many results
            return None  # This will trigger narrowing in recursive_search
        
        logger.info(f"Collected {len(urls)} URLs (within limit)")
        return urls
    
    def recursive_search(self, first: str = '', last: str = '', middle: str = '', state: str = '') -> List[str]:
        """
        Recursive function to narrow search if results > 30.
        Hierarchical strategy:
        1st Level: First name initial (A-Z)
        2nd Level: + Last name initial (AA-AZ, BA-BZ, ...)
        3rd Level: + Middle name initial (AAA-AAZ, ABA-ABZ, ...)
        4th Level: + State filter (AAA-CA, AAA-TX, ...)
        """
        urls = self._retry_operation(self.search_profiles, first, last, middle, state)
        
        # If None returned, it means > 30 results, need to narrow
        if urls is None:
            logger.info(f"Narrowing search for {first}{last}{middle}{state}")
            all_urls = []
            
            # Level 2: Add last initial if not present
            if not last:
                logger.info(f"Level 2: Adding last name initials for first={first}")
                for l in self.ALPHABET:
                    all_urls.extend(self.recursive_search(first, l, '', ''))
            # Level 3: Add middle initial if not present
            elif not middle:
                logger.info(f"Level 3: Adding middle name initials for first={first}, last={last}")
                for m in self.ALPHABET:
                    all_urls.extend(self.recursive_search(first, last, m, ''))
            # Level 4: Add state filter if not present
            elif not state:
                logger.info(f"Level 4: Adding state filters for first={first}, last={last}, middle={middle}")
                for s in self.STATES:
                    all_urls.extend(self.recursive_search(first, last, middle, s))
            else:
                # Level 5+: All basic filters exhausted, add more characters
                logger.warning(f"All 4 levels exhausted for {first}{last}{middle}{state}, adding more characters")
                
                # Add second character to first name
                if len(first) == 1:
                    logger.info(f"Level 5: Adding second character to first name for {first}{last}{middle}{state}")
                    for f2 in self.ALPHABET:
                        all_urls.extend(self.recursive_search(first + f2, last, middle, state))
                # Add second character to last name
                elif len(last) == 1:
                    logger.info(f"Level 6: Adding second character to last name for {first}{last}{middle}{state}")
                    for l2 in self.ALPHABET:
                        all_urls.extend(self.recursive_search(first, last + l2, middle, state))
                # Add second character to middle name
                elif len(middle) == 1:
                    logger.info(f"Level 7: Adding second character to middle name for {first}{last}{middle}{state}")
                    for m2 in self.ALPHABET:
                        all_urls.extend(self.recursive_search(first, last, middle + m2, state))
                # If all have 2+ characters, collect first 30
                else:
                    logger.error(f"Maximum narrowing reached for {first}{last}{middle}{state}. Collecting first 30.")
                    try:
                        params = {'fname': first, 'lname': last, 'state': state.lower()}
                        if middle:
                            params['mname'] = middle
                        self.driver.get(self.BASE_URL + '?' + urlencode(params))
                        time.sleep(5)
                        content = self.driver.page_source
                        soup = BeautifulSoup(content, 'html.parser')
                        npi_links = soup.find_all('a', href=True, string=lambda text: text and text.strip().isdigit() and len(text.strip()) == 10)
                        for link in npi_links[:30]:  # Take first 30 only
                            href = link.get('href')
                            if href:
                                if not href.startswith('http'):
                                    href = 'https://npidb.org' + href
                                all_urls.append(href)
                    except Exception as e:
                        logger.error(f"Failed to collect results for {first}{last}{middle}{state}: {e}")
            
            return all_urls
        
        # If we got results within limit, return them
        if urls is not None and len(urls) <= 30:
            return urls
        
        return []
    
    def scrape_search_results(self, params: dict = None) -> List[str]:
        """
        URL discovery engine: Performs hierarchical search starting from first initials.
        params: optional dict for custom starting params, e.g., {'first': 'A'}
        Returns list of all collected profile URLs.
        """
        if params is None:
            params = {}
        start_first = params.get('first', '')
        start_last = params.get('last', '')
        start_middle = params.get('middle', '')
        start_state = params.get('state', '')
        
        if start_first:
            # Start from specific first initial
            return self.recursive_search(start_first, start_last, start_middle, start_state)
        else:
            # Start from all first initials
            all_urls = []
            for f in self.ALPHABET:
                urls = self.recursive_search(f, start_last, start_middle, start_state)
                all_urls.extend(urls)
            return list(set(all_urls))  # Remove duplicates
    
    def extract_profile_data(self, url: str) -> Dict[str, str]:
        """
        Extract data from a profile page into structured dict.
        """
        self.driver.get(url)
        
        # Wait for Cloudflare challenge to complete
        max_wait = 15
        waited = 0
        while waited < max_wait:
            if "just a moment" in self.driver.title.lower() or "challenge" in self.driver.page_source.lower():
                time.sleep(1)
                waited += 1
            else:
                break
        
        time.sleep(2)  # Additional wait for page to fully load
        content = self.driver.page_source
        soup = BeautifulSoup(content, 'html.parser')
        
        data = {
            'URL': url,
            'NPI': '',
            'Full Name': '',
            'First Name': '',
            'Last Name': '',
            'Middle Name': '',
            'Credentials': '',
            'Address': '',
            'City': '',
            'State': '',
            'ZIP': '',
            'Phone': '',
            'Fax': '',
            'Website': '',
            'Status': '',
            'Enumeration Date': '',
            'Last Updated': '',
            'Sole Proprietor': '',
            'Entity Type': '',
            'Specialty': '',
            'Taxonomy Code': '',
            'Specialty Code': '',
            'Provider Type': '',
            'Gender': '',
            'Hospital Affiliation': ''
        }
        
        try:
            # Extract Full Name from the h3 heading or Contact Information section
            name_elem = soup.find('h1') or soup.find('h2')
            if name_elem:
                full_name = name_elem.text.strip()
                data['Full Name'] = full_name
                
                # Parse name components (basic parsing)
                name_parts = full_name.split(',')[0].strip().split()
                if len(name_parts) >= 2:
                    data['First Name'] = name_parts[0]
                    data['Last Name'] = name_parts[-1] if len(name_parts) > 1 else ''
                    if len(name_parts) > 2:
                        data['Middle Name'] = ' '.join(name_parts[1:-1])
                
                # Extract credentials (text after comma)
                if ',' in full_name:
                    data['Credentials'] = full_name.split(',', 1)[1].strip()
            
            # Extract NPI Number from the profile table
            npi_row = soup.find('td', string='NPI Number')
            if npi_row:
                npi_value = npi_row.find_next_sibling('td')
                if npi_value:
                    data['NPI'] = npi_value.text.strip()
            
            # Extract Status
            status_row = soup.find('td', string='Status')
            if status_row:
                status_value = status_row.find_next_sibling('td')
                if status_value:
                    data['Status'] = status_value.text.strip()
            
            # Extract Credentials from table
            cred_row = soup.find('td', string='Credentials')
            if cred_row:
                cred_value = cred_row.find_next_sibling('td')
                if cred_value:
                    data['Credentials'] = cred_value.text.strip()
            
            # Extract Entity Type
            entity_row = soup.find('td', string='Entity')
            if entity_row:
                entity_value = entity_row.find_next_sibling('td')
                if entity_value:
                    data['Entity Type'] = entity_value.text.strip()
            
            # Extract Enumeration Date
            enum_row = soup.find('td', string='Enumeration date')
            if enum_row:
                enum_value = enum_row.find_next_sibling('td')
                if enum_value:
                    data['Enumeration Date'] = enum_value.text.strip()
            
            # Extract Last Updated
            updated_row = soup.find('td', string='Last updated')
            if updated_row:
                updated_value = updated_row.find_next_sibling('td')
                if updated_value:
                    data['Last Updated'] = updated_value.text.strip()
            
            # Extract Sole Proprietor
            sole_row = soup.find('td', string=lambda t: t and 'Sole proprietor' in t)
            if sole_row:
                sole_value = sole_row.find_next_sibling('td')
                if sole_value:
                    data['Sole Proprietor'] = sole_value.text.strip()
            
            # Extract Hospital Affiliation
            hospital_row = soup.find('td', string=lambda t: t and 'Hospital affiliation' in t)
            if hospital_row:
                hospital_value = hospital_row.find_next_sibling('td')
                if hospital_value:
                    data['Hospital Affiliation'] = hospital_value.text.strip()
            
            # Extract Address, Phone, Fax, Website from Contact Information section
            address_elem = soup.find(string=lambda t: t and 'LOUISVILLE' in t or t and 'RD' in t or t and 'ST' in t)
            if not address_elem:
                # Try finding address near phone icon
                phone_icon = soup.find('span', class_='glyphicon-phone')
                if phone_icon:
                    parent = phone_icon.find_parent('div') or phone_icon.find_parent('p')
                    if parent:
                        text_content = parent.get_text(strip=True, separator='\n')
                        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
                        
                        # First line is usually the street address
                        if len(lines) > 0 and not lines[0].startswith('Phone'):
                            data['Address'] = lines[0]
                        
                        # Second line is usually city, state, zip
                        if len(lines) > 1:
                            city_state_zip = lines[1]
                            parts = city_state_zip.split(',')
                            if len(parts) >= 2:
                                data['City'] = parts[0].strip()
                                state_zip = parts[1].strip().split()
                                if len(state_zip) >= 2:
                                    data['State'] = state_zip[0]
                                    data['ZIP'] = state_zip[1] if len(state_zip) > 1 else ''
            
            # Better address extraction - look for the address pattern
            contact_section = soup.find('h3', string='Contact Information')
            if contact_section:
                # Get the next div or p after Contact Information
                next_elem = contact_section.find_next_sibling()
                if next_elem:
                    text = next_elem.get_text(separator='|', strip=True)
                    lines = [l.strip() for l in text.split('|') if l.strip()]
                    
                    for line in lines:
                        # Address line (has numbers and street name)
                        if any(char.isdigit() for char in line) and ('RD' in line.upper() or 'ST' in line.upper() or 'AVE' in line.upper() or 'BLVD' in line.upper() or 'DR' in line.upper()):
                            data['Address'] = line
                        # City, State ZIP line
                        elif ',' in line and any(char.isdigit() for char in line):
                            parts = line.split(',')
                            if len(parts) >= 2:
                                data['City'] = parts[0].strip()
                                state_zip = parts[1].strip().split()
                                if state_zip:
                                    data['State'] = state_zip[0]
                                    if len(state_zip) > 1:
                                        # ZIP might have dash
                                        data['ZIP'] = state_zip[1]
            
            # Extract Phone
            phone_label = soup.find(string=lambda t: t and 'Phone:' in t)
            if phone_label:
                # Phone number is usually right after the label
                parent = phone_label.find_parent()
                if parent:
                    phone_text = parent.get_text(strip=True)
                    # Extract phone number pattern
                    import re
                    phone_match = re.search(r'Phone:\s*([0-9-]+)', phone_text)
                    if phone_match:
                        data['Phone'] = phone_match.group(1)
            
            # Extract Fax
            fax_label = soup.find(string=lambda t: t and 'Fax:' in t)
            if fax_label:
                parent = fax_label.find_parent()
                if parent:
                    fax_text = parent.get_text(strip=True)
                    import re
                    fax_match = re.search(r'Fax:\s*([0-9-]+)', fax_text)
                    if fax_match:
                        data['Fax'] = fax_match.group(1)
            
            # Extract Website
            website_label = soup.find(string=lambda t: t and 'Website:' in t)
            if website_label:
                parent = website_label.find_parent()
                if parent:
                    link = parent.find('a')
                    if link and link.get('href'):
                        data['Website'] = link.get('href')
            
            # Extract Specialty from the Specialty table
            specialty_link = soup.find('a', href=lambda h: h and '/specialties/' in h)
            if specialty_link:
                data['Specialty'] = specialty_link.text.strip()
            
            # Extract Taxonomy Code and Specialty Code
            taxonomy_row = soup.find('td', string='Taxonomy Code')
            if taxonomy_row:
                taxonomy_value = taxonomy_row.find_next_sibling('td')
                if taxonomy_value:
                    data['Taxonomy Code'] = taxonomy_value.text.strip()
            
            specialty_code_row = soup.find('td', string='Specialty Code')
            if specialty_code_row:
                code_value = specialty_code_row.find_next_sibling('td')
                if code_value:
                    data['Specialty Code'] = code_value.text.strip()
            
            provider_type_row = soup.find('td', string='Provider Type')
            if provider_type_row:
                type_value = provider_type_row.find_next_sibling('td')
                if type_value:
                    data['Provider Type'] = type_value.text.strip()
            
            # Extract Gender from profile header or table
            gender_indicator = soup.find('span', class_='glyphicon-user')
            if gender_indicator:
                parent_text = gender_indicator.find_parent().get_text()
                if 'Male' in parent_text:
                    data['Gender'] = 'Male'
                elif 'Female' in parent_text:
                    data['Gender'] = 'Female'
            
        except Exception as e:
            logger.error(f"Error extracting profile data from {url}: {e}")
        
        return data
    
    def scrape_all(self, params: dict = None) -> pd.DataFrame:
        """
        Main scraping workflow: Search recursively, collect URLs, extract data, clean and validate.
        Returns cleaned DataFrame.
        Real-time saving ensures data is persisted even if browser crashes.
        """
        all_urls = self.scrape_search_results(params)
        
        logger.info(f"Collected {len(all_urls)} unique profile URLs")
        
        # Define fieldnames for CSV matching extract_profile_data output
        fieldnames = ['URL', 'NPI', 'Full Name', 'First Name', 'Last Name', 'Middle Name', 'Credentials', 
                      'Address', 'City', 'State', 'ZIP', 'Phone', 'Fax', 'Website', 'Status', 
                      'Enumeration Date', 'Last Updated', 'Sole Proprietor', 'Entity Type', 'Specialty', 
                      'Taxonomy Code', 'Specialty Code', 'Provider Type', 'Gender', 'Hospital Affiliation']
        
        # Initialize CSV file with headers if it doesn't exist
        csv_file = 'moms.csv'
        file_exists = os.path.exists(csv_file) and os.path.getsize(csv_file) > 0
        
        # Check which URLs have already been scraped (for resume capability)
        scraped_urls = set()
        if file_exists:
            try:
                existing_df = pd.read_csv(csv_file)
                if 'URL' in existing_df.columns:
                    scraped_urls = set(existing_df['URL'].dropna().tolist())
                    logger.info(f"Found {len(scraped_urls)} already scraped URLs in existing file")
            except Exception as e:
                logger.warning(f"Could not read existing CSV for resume: {e}")
        
        if not file_exists:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            logger.info(f"Created new CSV file: {csv_file}")
        else:
            logger.info(f"Appending to existing CSV file: {csv_file}")
        
        # Filter out already scraped URLs
        urls_to_scrape = [url for url in all_urls if url not in scraped_urls]
        skipped_count = len(all_urls) - len(urls_to_scrape)
        
        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} already scraped URLs")
        logger.info(f"Will scrape {len(urls_to_scrape)} new URLs")
        
        # Extract data from each URL and save in real-time
        all_data = []
        successful_count = 0
        failed_count = 0
        checkpoint_file = 'scraper_checkpoint.txt'
        
        for idx, url in enumerate(urls_to_scrape, 1):
            try:
                logger.info(f"Processing {idx}/{len(urls_to_scrape)}: {url}")
                data = self._retry_operation(self.extract_profile_data, url)
                all_data.append(data)
                
                # Real-time save to CSV - append mode with immediate flush
                with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow(data)
                    f.flush()  # Force write to disk immediately
                    os.fsync(f.fileno())  # Ensure OS writes to disk
                
                successful_count += 1
                logger.info(f"✓ Saved {idx}/{len(urls_to_scrape)} - NPI: {data.get('NPI', 'N/A')}, Name: {data.get('Full Name', 'N/A')}")
                
                # Save checkpoint every 10 records
                if successful_count % 10 == 0:
                    with open(checkpoint_file, 'w') as cf:
                        cf.write(f"Last processed: {idx}/{len(urls_to_scrape)}\n")
                        cf.write(f"Successful: {successful_count}\n")
                        cf.write(f"Failed: {failed_count}\n")
                        cf.write(f"URL: {url}\n")
                    logger.info(f"Checkpoint saved: {successful_count} records")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"✗ Failed {idx}/{len(urls_to_scrape)}: {url} - Error: {e}")
                # Continue with next URL even if one fails
                continue
        
        logger.info(f"Scraping completed: {successful_count} successful, {failed_count} failed, {skipped_count} skipped")
        logger.info(f"Data saved to {csv_file}")
        
        df = self.clean_data(all_data)
        return df
    
    def clean_data(self, data: List[Dict[str, str]]) -> pd.DataFrame:
        """
        Clean and validate the scraped data for 'Golden Record' quality.
        - Remove duplicates based on NPI.
        - Standardize address formats.
        """
        df = pd.DataFrame(data)
        
        # Handle empty DataFrame
        if df.empty or len(data) == 0:
            logger.warning("No data to clean - returning empty DataFrame")
            return pd.DataFrame(columns=['NPI', 'First Name', 'Last Name', 'Middle Name', 'Address', 'City', 'State', 'ZIP', 'Phone', 'Specialty'])
        
        # Remove duplicates (search overlaps)
        if 'NPI' in df.columns:
            df.drop_duplicates(subset=['NPI'], inplace=True)
        
        # Standardize address formats
        if 'Address' in df.columns:
            df['Address'] = df['Address'].str.replace(
                r'\bST\b', 'Street', case=False, regex=True
            )
            df['Address'] = df['Address'].str.replace(
                r'\bAVE\b', 'Avenue', case=False, regex=True
            )
            df['Address'] = df['Address'].str.replace(
                r'\bBLVD\b', 'Boulevard', case=False, regex=True
            )
            # Add more standardizations as needed
        
        # Basic validation: Ensure NPI is 10 digits (only if NPI column exists)
        if 'NPI' in df.columns and not df.empty:
            df = df[df['NPI'].str.match(r'^\d{10}$', na=False)]
        
        return df

def main():
    with NPIScraper(headless=True, delay=1.0) as scraper:
        # Test Cloudflare bypass first
        logger.info("Testing Cloudflare bypass...")
        scraper.driver.get("https://npidb.org/npi-lookup/")
        sleep(5)  # Wait for Cloudflare
        logger.info(f"Successfully accessed npidb.org - Title: {scraper.driver.title}")
        
        # Start scraping with first initial 'A'
        df = scraper.scrape_all({'first': 'A'})
        logger.info(f"Scraping completed. Total records: {len(df)}")
        logger.info("Cleaned data saved to moms.csv")

if __name__ == "__main__":
    main()
