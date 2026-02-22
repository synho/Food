import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import json

# Target High-Impact Open Access Medical Journals
# We cross-reference with PubMed's journal list
HIGH_IMPACT_JOURNALS = [
    "Nat Med",             # Nature Medicine
    "Lancet",              # The Lancet
    "N Engl J Med",        # New England Journal of Medicine
    "JAMA",                # Journal of the American Medical Association
    "BMJ",                 # British Medical Journal
    "Cell",                # Cell
    "Science",             # Science
    "Nature",              # Nature
    "Ann Intern Med",      # Annals of Internal Medicine
    "Am J Clin Nutr"       # American Journal of Clinical Nutrition
]

# NCBI E-utilities Base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def build_search_query(journals, days_back=30):
    """
    Builds an NCBI search query for specific journals within a date range.
    """
    journal_query = " OR ".join([f'"{j}"[Journal]' for j in journals])
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
    
    # Ensure they have Full Text in PMC (Open Access)
    final_query = f"({journal_query}) AND {date_query} AND open access[filter]"
    return final_query

def search_pmc(query, max_results=100):
    """
    Searches PubMed Central and returns a list of PMCID.
    """
    print(f"Searching PMC with query: {query}")
    params = {
        "db": "pmc",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "date" # Prioritize latest
    }
    
    response = requests.get(ESEARCH_URL, params=params)
    response.raise_for_status()
    data = response.json()
    
    id_list = data.get("esearchresult", {}).get("idlist", [])
    print(f"Found {len(id_list)} articles.")
    return id_list

def fetch_article_data(pmcid):
    """
    Fetches the full XML data for a given PMCID and extracts relevant sections.
    """
    params = {
        "db": "pmc",
        "id": pmcid,
        "retmode": "xml"
    }
    
    try:
        response = requests.get(EFETCH_URL, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PMC{pmcid}: {e}")
        return None
        
    root = ET.fromstring(response.content)
    
    # Extract Title
    title_elem = root.find(".//article-title")
    title = title_elem.text if title_elem is not None else "No Title"
    
    # Extract Abstract
    abstract_elem = root.find(".//abstract")
    abstract = ""
    if abstract_elem is not None:
        abstract = "".join(abstract_elem.itertext()).strip()
        
    # Extract Journal Name
    journal_elem = root.find(".//journal-title")
    journal = journal_elem.text if journal_elem is not None else "Unknown Journal"
    
    # Extract Publication Date (Year, Month, Day)
    pub_date_elem = root.find(".//pub-date[@date-type='pub']") or root.find(".//pub-date")
    pub_date = "Unknown"
    if pub_date_elem is not None:
        year = pub_date_elem.findtext("year", default="")
        month = pub_date_elem.findtext("month", default="01")
        day = pub_date_elem.findtext("day", default="01")
        if year:
            pub_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
    # Extract Body/Text (for deeper LLM analysis later)
    body_elem = root.find(".//body")
    body_text = ""
    if body_elem is not None:
         body_text = "".join(body_elem.itertext()).strip()
         
    return {
        "pmcid": f"PMC{pmcid}",
        "title": title,
        "journal": journal,
        "date": pub_date,
        "abstract": abstract,
        "full_text_preview": body_text[:1000] + "..." if len(body_text) > 1000 else body_text # Just a preview to save memory for now
    }

def main():
    # Only searching back 30 days initially to test "latest first"
    query = build_search_query(HIGH_IMPACT_JOURNALS, days_back=30)
    
    # Limit to 5 for initial testing
    pmcids = search_pmc(query, max_results=5)
    
    articles = []
    
    os.makedirs("data/raw_papers", exist_ok=True)
    
    for pd in pmcids:
        print(f"Fetching PMC{pd}...")
        article_data = fetch_article_data(pd)
        if article_data:
            articles.append(article_data)
            
            # Save raw JSON locally
            with open(f"data/raw_papers/PMC{pd}.json", "w", encoding="utf-8") as f:
                json.dump(article_data, f, indent=4)
                
        # Be polite to NCBI servers (max 3 req/sec without API key)
        time.sleep(1)
        
    print(f"Successfully downloaded and saved {len(articles)} articles.")

if __name__ == "__main__":
    main()
