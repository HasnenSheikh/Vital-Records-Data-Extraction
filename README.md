# Vital Records Data Extraction - Comprehensive Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [Problem Statement](#problem-statement)
3. [Search Strategy](#search-strategy)
4. [Technology Stack](#technology-stack)
5. [Architecture & Code Overview](#architecture--code-overview)
6. [Running Instructions](#running-instructions)
7. [Data Output](#data-output)
8. [Notes & Limitations](#notes--limitations)
9. [Troubleshooting](#troubleshooting)

---

## Introduction

The **Vital Records Data Extraction** is a sophisticated web scraping solution designed to extract comprehensive healthcare provider information from the National Provider Identifier (NPI) database at https://npidb.org. This tool automates the collection of 24 distinct fields for each healthcare provider, including contact information, credentials, specialties, and taxonomy codes.

### Key Features
- **Cloudflare Bypass**: Uses undetected-chromedriver to bypass anti-bot protection
- **Hierarchical Search Strategy**: Implements intelligent recursive narrowing to overcome the 30-result limit
- **Real-time Data Persistence**: Saves records to CSV immediately using os.fsync() to prevent data loss
- **Resume Capability**: Automatically skips already-scraped URLs when restarted
- **Error Recovery**: Handles browser crashes and connection failures with automatic recovery
- **Comprehensive Extraction**: Captures 24 distinct fields per provider profile

---

## Problem Statement

### Challenge 1: Cloudflare Protection
The NPI database website (npidb.org) implements Cloudflare's anti-bot protection, which blocks traditional web scrapers. Standard tools like Selenium with regular ChromeDriver trigger bot detection mechanisms, resulting in access denial.

### Challenge 2: 30-Result Limit
The search functionality on npidb.org limits results to 30 profiles per query. A broad search (e.g., all providers with first name starting with "A") returns thousands of matches, but only displays 30 results. This makes it impossible to collect all profiles using simple queries.

### Challenge 3: Dynamic Content & Complex Structure
Profile pages contain dynamically loaded content with inconsistent HTML structures. Fields may be present or absent, and their location varies between profiles. Extract logic must handle multiple HTML patterns for each field.

### Challenge 4: Data Persistence
Long-running scraping sessions (hours or days) are vulnerable to crashes, network failures, or system interruptions. Without proper persistence mechanisms, crashes result in complete data loss.

---

## Search Strategy

### Hierarchical Recursive Narrowing Algorithm

The scraper implements an 8-level hierarchical strategy to systematically narrow searches when results exceed 30:

```
Level 1: Start with first initial (A-Z)
         ↓ (if >30 results)
Level 2: Add last name initial (A + A through A + Z)
         ↓ (if >30 results)
Level 3: Add middle name initial (A + B + A through A + B + Z)
         ↓ (if >30 results)
Level 4: Add state filter (A + B + C + AL through A + B + C + WY)
         ↓ (if >30 results)
Level 5: Add second character to first name (AA + B + C + CA, AB + B + C + CA, etc.)
         ↓ (if >30 results)
Level 6: Add second character to last name (A + BA + C + CA, A + BB + C + CA, etc.)
         ↓ (if >30 results)
Level 7: Add second character to middle name (A + B + CA + CA, A + B + CB + CA, etc.)
         ↓ (if >30 results)
Level 8: Maximum narrowing reached - collect first 30 results and log warning
```

### Example Search Flow

**Scenario**: Searching for providers with first name starting with "A"

1. **Initial Query**: `?fname=A`
   - Result: >30 profiles found
   - Action: Trigger Level 2

2. **Level 2 Query**: `?fname=A&lname=S`
   - Result: Still >30 profiles
   - Action: Trigger Level 3

3. **Level 3 Query**: `?fname=A&lname=S&mname=M`
   - Result: Still >30 profiles
   - Action: Trigger Level 4

4. **Level 4 Query**: `?fname=A&lname=S&mname=M&state=ca`
   - Result: 18 profiles found (≤30)
   - Action: Collect all 18 profile URLs
   - Continue with next state...

### Code Implementation

```python
def recursive_search(self, first='', last='', middle='', state='') -> List[str]:
    """Recursive function to narrow search if results > 30."""
    urls = self.search_profiles(first, last, middle, state)
    
    if urls is None:  # None indicates >30 results
        all_urls = []
        
        # Level 2: Add last initial
        if not last:
            for l in self.ALPHABET:
                all_urls.extend(self.recursive_search(first, l, '', ''))
        
        # Level 3: Add middle initial
        elif not middle:
            for m in self.ALPHABET:
                all_urls.extend(self.recursive_search(first, last, m, ''))
        
        # Level 4: Add state filter
        elif not state:
            for s in self.STATES:
                all_urls.extend(self.recursive_search(first, last, middle, s))
        
        # Levels 5-7: Add second characters
        else:
            if len(first) == 1:
                for f2 in self.ALPHABET:
                    all_urls.extend(self.recursive_search(first + f2, last, middle, state))
            # ... similar for last and middle
        
        return list(set(all_urls))
    
    return urls
```

---

## Technology Stack

### Core Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.8+ | Core programming language |
| **undetected-chromedriver** | 3.5.5 | Bypass Cloudflare protection |
| **Selenium** | Latest | Browser automation |
| **BeautifulSoup4** | Latest | HTML parsing |
| **Pandas** | Latest | Data manipulation & cleaning |
| **fake-useragent** | Latest | Dynamic user agent generation |

### Why These Technologies?

#### undetected-chromedriver
Standard Selenium ChromeDriver is easily detected by Cloudflare. `undetected-chromedriver` is a patched version that:
- Removes webdriver detection fingerprints
- Mimics human browser behavior
- Automatically handles Chrome version matching (version_main=144)

```python
import undetected_chromedriver as uc

options = uc.ChromeOptions()
driver = uc.Chrome(options=options, version_main=144)
```

#### BeautifulSoup4
Chosen for robust HTML parsing capabilities:
- Handles malformed HTML gracefully
- Provides multiple search methods (find, find_all, select)
- Lambda functions for flexible string matching

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_content, 'html.parser')
npi_row = soup.find('td', string='NPI Number')
```

#### Pandas
Used for data cleaning and validation:
- Filter invalid NPI numbers (must be 10 digits)
- Remove duplicates efficiently
- Export to CSV with proper formatting

---

## Architecture & Code Overview

### Class Structure

```python
class NPIScraper:
    """Main scraper class with context manager support."""
    
    BASE_URL = "https://npidb.org/npi-lookup/"
    ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    STATES = ["AL", "AK", ..., "WY"]  # 50 US states
    
    def __init__(self, headless=True, delay=1.0, max_retries=3):
        """Initialize scraper with configuration."""
        
    def __enter__(self):
        """Context manager entry - initialize browser."""
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup browser."""
```

### Core Methods

#### 1. Browser Management

```python
def _reinitialize_browser(self):
    """Reinitialize browser when connection is lost."""
    logger.warning("Reinitializing browser due to connection loss...")
    if self.driver:
        try:
            self.driver.quit()
        except:
            pass
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    self.driver = uc.Chrome(options=options, version_main=144)
    time.sleep(3)
```

#### 2. Search Execution

```python
def search_profiles(self, first_initial='', last_initial='', 
                   middle_initial='', state='') -> List[str]:
    """Perform search and collect profile URLs."""
    
    # Build URL with query parameters
    params = {}
    if first_initial:
        params['fname'] = first_initial
    if last_initial:
        params['lname'] = last_initial
    if middle_initial:
        params['mname'] = middle_initial
    if state:
        params['state'] = state.lower()
    
    url = self.BASE_URL + '?' + urlencode(params)
    self.driver.get(url)
    time.sleep(5)  # Wait for dynamic content
    
    # Parse results
    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
    
    # Extract profile links
    results = []
    npi_links = soup.find_all('a', href=True, 
                              string=lambda t: t and t.strip().isdigit() 
                                               and len(t.strip()) == 10)
    
    # Return None if >30 results to trigger narrowing
    if len(results) > 30:
        return None
    
    return [result['href'] for result in results]
```

#### 3. Profile Data Extraction (24 Fields)

```python
def extract_profile_data(self, url: str) -> Dict[str, str]:
    """Extract 24 fields from a profile page."""
    
    self.driver.get(url)
    
    # Wait for Cloudflare challenge completion
    max_wait = 15
    waited = 0
    while waited < max_wait:
        if "just a moment" in self.driver.title.lower():
            time.sleep(1)
            waited += 1
        else:
            break
    
    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
    
    # Initialize data dictionary
    data = {'URL': url}
    
    try:
        # Extract Full Name from page title
        page_title = self.driver.title
        if ' - NPI ' in page_title:
            data['Full Name'] = page_title.split(' - NPI ')[0].strip()
        
        # Extract NPI Number
        npi_row = soup.find('td', string='NPI Number')
        if npi_row:
            npi_value = npi_row.find_next_sibling('td')
            if npi_value:
                data['NPI'] = npi_value.text.strip()
        
        # Extract Status
        status_row = soup.find('td', string='Status')
        if status_row:
            data['Status'] = status_row.find_next_sibling('td').text.strip()
        
        # ... Extract remaining 21 fields ...
        # (Credentials, Entity Type, Enumeration Date, Address, 
        #  City, State, ZIP, Phone, Fax, Website, Email, Gender,
        #  Specialty, Primary Taxonomy, Taxonomy Code, etc.)
        
    except Exception as e:
        logger.error(f'Error extracting from {url}: {e}')
    
    return data
```

#### 4. Real-time CSV Saving

```python
def scrape(self, params=None) -> pd.DataFrame:
    """Main scraping workflow with real-time CSV saving."""
    
    # Collect all profile URLs first
    all_urls = self.scrape_search_results(params)
    logger.info(f'Collected {len(all_urls)} unique profile URLs')
    
    # Setup CSV with 24 field headers
    fieldnames = ['URL', 'Full Name', 'NPI', 'Status', 'Credentials',
                  'Entity Type', 'Enumeration Date', 'Last Updated',
                  'Address', 'City', 'State', 'ZIP', 'Phone', 'Fax',
                  'Website', 'Email', 'Gender', 'Specialty',
                  'Primary Taxonomy', 'Taxonomy Code', 'Specialty Code',
                  'Provider Type', 'Sole Proprietor', 'Hospital Affiliation']
    
    # Load existing URLs to avoid duplicates (resume capability)
    scraped_urls = set()
    if os.path.exists('moms.csv'):
        with open('moms.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            scraped_urls = {row['URL'] for row in reader if 'URL' in row}
    
    # Open CSV in append mode
    with open('moms.csv', 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header if file is new
        if csvfile.tell() == 0:
            writer.writeheader()
        
        for i, url in enumerate(all_urls, 1):
            if url in scraped_urls:
                logger.info(f'Skipping already scraped URL: {url}')
                continue
            
            # Extract data
            profile_data = self.extract_profile_data(url)
            
            # Write immediately to CSV
            writer.writerow(profile_data)
            csvfile.flush()
            os.fsync(csvfile.fileno())  # Force write to disk
            
            logger.info(f'[{i}/{len(all_urls)}] NPI: {profile_data.get("NPI", "N/A")}, '
                       f'Name: {profile_data.get("Full Name", "N/A")}')
            
            time.sleep(self.delay)  # Rate limiting
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SCRAPING WORKFLOW                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Initialize Browser (undetected-chromedriver)            │
│     - Bypass Cloudflare                                     │
│     - Set Chrome options                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. URL Collection Phase (recursive_search)                 │
│     - Start with first initial A-Z                          │
│     - Apply hierarchical narrowing (8 levels)               │
│     - Collect all profile URLs (deduplicated)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Load Existing Data (Resume Capability)                  │
│     - Read moms.csv if exists                               │
│     - Extract already-scraped URLs                          │
│     - Create skip set                                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Profile Extraction Loop                                 │
│     FOR EACH URL:                                           │
│       - Skip if already scraped                             │
│       - Navigate to profile page                            │
│       - Wait for Cloudflare (max 15s)                       │
│       - Parse HTML with BeautifulSoup                       │
│       - Extract 24 fields                                   │
│       - Write to CSV immediately                            │
│       - Flush & fsync to disk                               │
│       - Log progress                                        │
│       - Sleep (rate limiting)                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Data Cleaning & Validation                              │
│     - Load DataFrame from CSV                               │
│     - Filter invalid NPI numbers (must be 10 digits)        │
│     - Remove duplicates                                     │
│     - Save cleaned data                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Running Instructions

### Prerequisites

1. **Python 3.8 or higher**
   ```bash
   python --version  # Should show 3.8+
   ```

2. **Google Chrome browser** (version 144 or compatible)
   ```bash
   google-chrome --version
   ```

### Step-by-Step Installation

#### Step 1: Clone or Download Project
```bash
cd /path/to/your/workspace
# If using git:
git clone <repository-url>
cd "Vital Records Extraction Engine - Playwright"
```

#### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/Mac:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**requirements.txt contents:**
```
undetected-chromedriver==3.5.5
selenium
beautifulsoup4
pandas
fake-useragent
```

#### Step 4: Verify Installation
```bash
python -c "import undetected_chromedriver as uc; print('Success!')"
```

### Running the Scraper

#### Basic Execution (Full Scrape)
```bash
python scraper.py
```
This will:
- Test Cloudflare bypass
- Scrape all profiles starting with first initial 'A'
- Save results to `moms.csv`

#### Custom Starting Point
Edit the `main()` function in scraper.py:

```python
def main():
    with NPIScraper(headless=True, delay=1.0) as scraper:
        # Start from specific first initial
        df = scraper.scrape_all({'first': 'M'})
        
        # Or start from specific name combination
        # df = scraper.scrape_all({'first': 'A', 'last': 'S'})
        
        logger.info(f"Total records: {len(df)}")
```

#### Configuration Options

```python
NPIScraper(
    headless=True,      # Run browser in background (True) or visible (False)
    delay=1.0,          # Delay between requests in seconds (adjust for rate limiting)
    max_retries=3       # Number of retry attempts for failed operations
)
```

### Monitoring Progress

The scraper provides real-time logging:

```
2026-02-08 10:15:23 - INFO - Chrome browser started successfully
2026-02-08 10:15:25 - INFO - Testing Cloudflare bypass...
2026-02-08 10:15:31 - INFO - Successfully accessed npidb.org
2026-02-08 10:15:35 - INFO - Search for A took 3.24s, results: 31
2026-02-08 10:15:35 - WARNING - Search returned 31 results (>30), returning None
2026-02-08 10:15:35 - INFO - Narrowing search for A
2026-02-08 10:15:35 - INFO - Level 2: Adding last name initials for first=A
2026-02-08 10:15:42 - INFO - Search for AA took 2.87s, results: 18
2026-02-08 10:16:15 - INFO - Collected 357 unique profile URLs
2026-02-08 10:16:17 - INFO - [1/357] NPI: 1234567890, Name: John Smith
2026-02-08 10:16:25 - INFO - [2/357] NPI: 1234567891, Name: Jane Doe
...
```

### Resume After Interruption

If the scraper crashes or is interrupted:

1. Simply run it again: `python scraper.py`
2. The scraper automatically:
   - Loads existing `moms.csv`
   - Extracts already-scraped URLs
   - Skips those URLs
   - Continues from where it left off

You'll see logs like:
```
2026-02-08 11:30:15 - INFO - Skipping already scraped URL: https://npidb.org/npi/1234567890
```

### Handling Cloudflare Challenges

If Cloudflare challenges appear frequently:

1. **Increase wait time** in `extract_profile_data`:
   ```python
   max_wait = 30  # Increase from 15 to 30 seconds
   ```

2. **Add random delays**:
   ```python
   import random
   time.sleep(random.uniform(2, 5))  # Random delay between 2-5 seconds
   ```

3. **Use headless=False** for debugging:
   ```python
   with NPIScraper(headless=False, delay=2.0) as scraper:
   ```

---

## Data Output

### CSV Structure (moms.csv)

The output CSV contains 24 columns:

| Column # | Field Name | Description | Example |
|----------|------------|-------------|---------|
| 1 | URL | Profile page URL | https://npidb.org/npi/1234567890 |
| 2 | Full Name | Provider's full name | Dr. John A. Smith |
| 3 | NPI | 10-digit NPI number | 1234567890 |
| 4 | Status | Active/Inactive | Active |
| 5 | Credentials | Medical credentials | MD, FACP |
| 6 | Entity Type | Individual/Organization | Individual |
| 7 | Enumeration Date | Date of NPI registration | 01/15/2010 |
| 8 | Last Updated | Last profile update | 12/05/2025 |
| 9 | Address | Street address | 123 Medical Plaza Rd |
| 10 | City | City name | Louisville |
| 11 | State | State code | KY |
| 12 | ZIP | ZIP code | 40202 |
| 13 | Phone | Phone number | 502-555-1234 |
| 14 | Fax | Fax number | 502-555-1235 |
| 15 | Website | Website URL | www.example.com |
| 16 | Email | Email address | contact@example.com |
| 17 | Gender | Male/Female | Male |
| 18 | Specialty | Medical specialty | Internal Medicine |
| 19 | Primary Taxonomy | Primary taxonomy description | Physician |
| 20 | Taxonomy Code | Taxonomy code | 207R00000X |
| 21 | Specialty Code | Specialty classification code | 13 |
| 22 | Provider Type | Type of provider | Allopathic & Osteopathic |
| 23 | Sole Proprietor | Yes/No | No |
| 24 | Hospital Affiliation | Hospital name | University Hospital |

### Sample Output

```csv
URL,Full Name,NPI,Status,Credentials,Entity Type,Enumeration Date,Last Updated,Address,City,State,ZIP,Phone,Fax,Website,Email,Gender,Specialty,Primary Taxonomy,Taxonomy Code,Specialty Code,Provider Type,Sole Proprietor,Hospital Affiliation
https://npidb.org/npi/1234567890,Dr. John A. Smith,1234567890,Active,MD FACP,Individual,01/15/2010,12/05/2025,123 Medical Plaza Rd,Louisville,KY,40202,502-555-1234,502-555-1235,www.example.com,contact@example.com,Male,Internal Medicine,Physician,207R00000X,13,Allopathic & Osteopathic,No,University Hospital
```

### Data Quality

After scraping completes, the data is automatically cleaned:

- **NPI Validation**: Only records with valid 10-digit NPI numbers are retained
- **Duplicate Removal**: Duplicate records based on NPI are removed
- **Empty Field Handling**: Missing fields are left empty (not "N/A" or "None")

---

## Notes & Limitations

### Known Limitations

1. **30-Result Cap per Query**
   - Even with 8-level narrowing, some name combinations may exceed 30 results
   - In such cases, only the first 30 results are collected
   - Logs will show: `Maximum narrowing reached for {search_key}. Collecting first 30.`

2. **Cloudflare Challenge Variability**
   - Cloudflare may increase scrutiny after ~300-500 requests
   - Solution: Increase delay between requests or pause and resume later
   - Consider using residential proxies for large-scale scraping

3. **Field Availability**
   - Not all profiles contain all 24 fields
   - Some fields may be empty in the output
   - Website and Email are particularly sparse (~20% availability)

4. **Performance**
   - Average extraction rate: 3-5 profiles per minute
   - Full database scrape (estimated 2M+ profiles): ~7-11 days
   - URL collection phase: ~2-6 hours (for all first initials)

5. **Browser Version Compatibility**
   - Requires Chrome version 144 or compatible
   - `undetected-chromedriver` auto-downloads matching ChromeDriver
   - May need to update `version_main` parameter if Chrome updates

### Best Practices

#### 1. Rate Limiting
```python
# Conservative approach (recommended)
scraper = NPIScraper(delay=2.0)  # 2 seconds between requests

# Aggressive approach (may trigger Cloudflare)
scraper = NPIScraper(delay=0.5)  # 0.5 seconds between requests
```

#### 2. Headless vs Headed Mode
```python
# Production: headless mode (faster, no GUI)
scraper = NPIScraper(headless=True)

# Debugging: headed mode (see browser actions)
scraper = NPIScraper(headless=False)
```

#### 3. Error Handling
The scraper includes automatic error recovery:
- Browser crashes → Automatic reinitialization
- Network errors → Retry up to 3 times
- Invalid pages → Log error and continue

#### 4. Incremental Scraping
For large-scale scraping, use incremental approach:

```python
# Day 1: Scrape A-E
for letter in 'ABCDE':
    df = scraper.scrape_all({'first': letter})

# Day 2: Scrape F-J
for letter in 'FGHIJ':
    df = scraper.scrape_all({'first': letter})
```

### Ethical Considerations

1. **Respect robots.txt**: Check website's robots.txt before scraping
2. **Rate Limiting**: Implement delays to avoid overloading the server
3. **Data Privacy**: Handle personal information (NPI data is public record)
4. **Terms of Service**: Review npidb.org ToS before large-scale scraping
5. **Data Usage**: Use scraped data responsibly and legally

### Legal Disclaimer

This scraper is provided for educational and research purposes. Users are responsible for:
- Complying with applicable laws and regulations
- Respecting website Terms of Service
- Ensuring data usage complies with privacy laws (HIPAA, GDPR, etc.)
- Implementing appropriate rate limiting

---

## Troubleshooting

### Issue 1: "Error 1006" or "Just a moment..." in Full Name

**Symptom**: CSV shows "Error 1006" instead of actual names

**Cause**: Cloudflare challenge not completing before data extraction

**Solution**:
```python
# Increase wait time in extract_profile_data
max_wait = 30  # Change from 15 to 30 seconds
```

### Issue 2: Browser Connection Lost

**Symptom**: Logs show "Browser connection lost" or "invalid session id"

**Cause**: Chrome browser crashed or lost connection

**Solution**: 
- Automatic recovery is built-in (see `_reinitialize_browser`)
- If persistent, increase system resources (RAM)
- Close other applications to free memory

### Issue 3: No Results Found

**Symptom**: `Collected 0 unique profile URLs`

**Cause**: Search parameters too restrictive or HTML structure changed

**Solution**:
1. Test with broad search: `{'first': 'A'}`
2. Check HTML structure manually:
   ```python
   # Add debug output
   with open('debug_search_page.html', 'w') as f:
       f.write(self.driver.page_source)
   ```
3. Update selectors if npidb.org changed HTML structure

### Issue 4: ChromeDriver Version Mismatch

**Symptom**: "ChromeDriver only supports Chrome version X"

**Cause**: Chrome browser updated but ChromeDriver version not updated

**Solution**:
```python
# Update version_main in scraper.py
self.driver = uc.Chrome(options=options, version_main=145)  # Update to match Chrome version
```

Or check Chrome version:
```bash
google-chrome --version
# Update version_main to match major version
```

### Issue 5: Slow Performance

**Symptom**: <1 profile per minute extraction rate

**Cause**: Network latency, Cloudflare challenges, or system resources

**Solutions**:
1. Check network connection stability
2. Reduce delay if Cloudflare is not triggering: `delay=0.8`
3. Close unnecessary applications
4. Use wired connection instead of WiFi
5. Consider running on a server with better connectivity

### Issue 6: CSV Corruption After Crash

**Symptom**: moms.csv cannot be opened or has malformed data

**Cause**: Write operation interrupted during crash

**Solution**:
1. The scraper uses `os.fsync()` to minimize this risk
2. If corruption occurs, remove last incomplete line manually
3. Run scraper again - it will skip already-scraped URLs

---

## Advanced Configuration

### Custom Field Extraction

To add or modify extracted fields, edit `extract_profile_data()`:

```python
# Add custom field
custom_row = soup.find('td', string='Your Custom Field')
if custom_row:
    custom_value = custom_row.find_next_sibling('td')
    if custom_value:
        data['Custom Field'] = custom_value.text.strip()

# Update fieldnames list in scrape() method
fieldnames = ['URL', 'Full Name', ..., 'Custom Field']
```

### Proxy Configuration

For IP rotation or bypassing regional blocks:

```python
options = uc.ChromeOptions()
options.add_argument('--proxy-server=http://your-proxy:port')
self.driver = uc.Chrome(options=options, version_main=144)
```

### Parallel Scraping

To speed up extraction using multiple browsers:

```python
from concurrent.futures import ThreadPoolExecutor

def scrape_letter(letter):
    with NPIScraper(headless=True) as scraper:
        return scraper.scrape_all({'first': letter})

with ThreadPoolExecutor(max_workers=3) as executor:
    results = executor.map(scrape_letter, 'ABC')
```

---

## Conclusion

This Vital Records Data Extraction demonstrates advanced web scraping techniques including:
- Cloudflare bypass using undetected-chromedriver
- Hierarchical recursive search algorithm to overcome pagination limits
- Real-time data persistence with crash recovery
- Comprehensive error handling and automatic retry mechanisms
- Clean, maintainable code following best practices

For questions, issues, or contributions, please refer to the project repository or contact the maintainer.

**Version**: 1.0.0  
**Last Updated**: February 8, 2026  
**Author**: Code Sorcerer Projects  
**License**: MIT
