import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import json

from config_loader import get_fetch_config, get_paths_config, load_config
from artifacts import AGENT_FETCH, get_run_id, write_manifest

# NCBI E-utilities Base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def build_search_query(journals, days_back=30, topic_keywords=None, humans_only=True):
    """
    Builds an NCBI search query: journals + date range + optional topic keywords.
    Restricts to human studies only (no animal models): adds "humans"[MeSH Terms] when humans_only=True.
    """
    journal_query = " OR ".join([f'"{j}"[Journal]' for j in journals])
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
    base = f"({journal_query}) AND {date_query} AND open access[filter]"
    if humans_only:
        base = f"{base} AND (\"humans\"[MeSH Terms])"
    if topic_keywords:
        terms = " OR ".join([f'"{t}"[Title/Abstract]' for t in topic_keywords if t and t.strip()])
        if terms:
            base = f"({base}) AND ({terms})"
    return base

def search_pmc(query, max_results=100):
    """
    Searches PubMed Central and returns a list of PMCID.
    Retries up to 3 times on NCBI 429 rate-limit responses (65 s wait).
    """
    print(f"Searching PMC with query: {query}")
    params = {
        "db": "pmc",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "date"  # Prioritize latest
    }
    max_retries = 3
    for attempt in range(max_retries):
        response = requests.get(ESEARCH_URL, params=params)
        if response.status_code == 429:
            if attempt < max_retries - 1:
                print(f"NCBI rate limit (429). Retrying in 65 seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(65)
                continue
        response.raise_for_status()
        data = response.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        print(f"Found {len(id_list)} articles.")
        return id_list
    return []

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
    cfg = get_fetch_config()
    paths = get_paths_config()
    days_back = cfg["days_back"]
    max_results = cfg["max_results"]
    journals = cfg["journals"]
    topic_keywords = cfg.get("topic_keywords") or []
    humans_only = cfg.get("humans_only", True)
    delay_sec = cfg.get("request_delay_sec", 1)
    raw_dir = paths["raw_papers"]

    query = build_search_query(journals, days_back=days_back, topic_keywords=topic_keywords, humans_only=humans_only)
    pmcids = search_pmc(query, max_results=max_results)
    # Optional second query for aging/biology: merge PMCIDs (dedupe, preserve order)
    aging_keywords = cfg.get("aging_keywords") or []
    if aging_keywords:
        query_aging = build_search_query(journals, days_back=days_back, topic_keywords=aging_keywords, humans_only=humans_only)
        pmcids_aging = search_pmc(query_aging, max_results=max_results)
        seen = set(pmcids)
        for pid in pmcids_aging:
            if pid not in seen:
                seen.add(pid)
                pmcids.append(pid)
        if pmcids_aging:
            print(f"Merged {len(pmcids_aging)} from aging query; total {len(pmcids)} unique.")

    skip_existing = cfg.get("skip_existing", True)
    if skip_existing and os.path.isdir(raw_dir):
        existing = set()
        for f in os.listdir(raw_dir):
            if f.startswith("PMC") and f.endswith(".json"):
                try:
                    existing.add(f.replace("PMC", "").replace(".json", ""))
                except Exception:
                    pass
        to_fetch = [p for p in pmcids if p not in existing]
        if existing and to_fetch:
            print(f"Skipping {len(existing)} already downloaded; fetching {len(to_fetch)} new.")
        elif existing and not to_fetch:
            print("All found articles already downloaded. Nothing to fetch.")
            run_id = get_run_id()
            write_manifest(AGENT_FETCH, run_id, {"pmcids_fetched": [], "file_paths": [], "raw_papers_dir": raw_dir, "config_fetch": cfg})
            return
        pmcids = to_fetch

    run_id = get_run_id()
    articles = []
    os.makedirs(raw_dir, exist_ok=True)
    file_paths = []

    for pd in pmcids:
        print(f"Fetching PMC{pd}...")
        article_data = fetch_article_data(pd)
        if article_data:
            articles.append(article_data)
            out_path = os.path.join(raw_dir, f"PMC{pd}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(article_data, f, indent=4)
            file_paths.append(f"PMC{pd}.json")
        time.sleep(delay_sec)

    pmcids_fetched = [a.get("pmcid", "") for a in articles]
    write_manifest(AGENT_FETCH, run_id, {
        "pmcids_fetched": pmcids_fetched,
        "file_paths": file_paths,
        "raw_papers_dir": raw_dir,
        "config_fetch": cfg,
    })
    print(f"Successfully downloaded and saved {len(articles)} articles.")

if __name__ == "__main__":
    main()
