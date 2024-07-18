import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
import socket
import time
import warnings

warnings.filterwarnings('ignore')

# User agents list (unchanged from the original script)
user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    # ... (include all user agents from the original script)
]

def make_header():
    return {'User-Agent': random.choice(user_agents)}

async def extract_by_article(url, session, semaphore):
    async with semaphore, session.get(url) as response:
        data = await response.text()
        soup = BeautifulSoup(data, "lxml")
        
        # Extract article data (similar to the original script)
        abstract = soup.find('div', {'class': 'abstract-content selected'})
        abstract = ' '.join([p.text.strip() for p in abstract.find_all('p')]) if abstract else 'NO_ABSTRACT'
        
        affiliations = soup.find('ul', {'class': 'item-list'})
        affiliations = [li.get_text().strip() for li in affiliations.find_all('li')] if affiliations else 'NO_AFFILIATIONS'
        
        keywords = soup.find('div', {'class': 'abstract'})
        if keywords and keywords.find_all('strong', {'class': 'sub-title'})[-1].text.strip() == 'Keywords:':
            keywords = keywords.find_all('p')[-1].get_text().replace('Keywords:', '').strip()
        else:
            keywords = 'NO_KEYWORDS'
        
        title = soup.find('meta', {'name': 'citation_title'})
        title = title['content'].strip('[]') if title else 'NO_TITLE'
        
        authors = soup.find('div', {'class': 'authors-list'})
        authors = ', '.join([a.text for a in authors.find_all('a', {'class': 'full-name'})]) if authors else 'NO_AUTHOR'
        
        journal = soup.find('meta', {'name': 'citation_journal_title'})
        journal = journal['content'] if journal else 'NO_JOURNAL'
        
        date = soup.find('time', {'class': 'citation-year'})
        date = date.text if date else 'NO_DATE'

        return {
            'url': url,
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'affiliations': affiliations,
            'journal': journal,
            'keywords': keywords,
            'date': date
        }

async def get_pmids(page, keyword, session):
    page_url = f'https://pubmed.ncbi.nlm.nih.gov/?term={keyword}&page={page}'
    async with session.get(page_url) as response:
        data = await response.text()
        soup = BeautifulSoup(data, "lxml")
        pmids = soup.find('meta', {'name': 'log_displayeduids'})
        return [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in pmids['content'].split(',')] if pmids else []

async def scrape_pubmed(keywords, start_year, end_year, max_pages):
    conn = aiohttp.TCPConnector(family=socket.AF_INET)
    async with aiohttp.ClientSession(headers=make_header(), connector=conn) as session:
        semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        all_urls = []
        for keyword in keywords:
            for page in range(1, max_pages + 1):
                urls = await get_pmids(page, f"{keyword} AND ({start_year}:{end_year}[dp])", session)
                all_urls.extend(urls)
                if len(urls) < 10:  # Less than 10 results on a page means it's the last page
                    break
        
        tasks = [extract_by_article(url, session, semaphore) for url in all_urls]
        articles_data = await asyncio.gather(*tasks)
    
    return pd.DataFrame(articles_data)

def main():
    st.title("PubMed Article Scraper")

    # User inputs
    keywords = st.text_area("Enter keywords (one per line):", "artificial intelligence\nmachine learning")
    start_year = st.number_input("Start year:", min_value=1900, max_value=2023, value=2019)
    end_year = st.number_input("End year:", min_value=1900, max_value=2023, value=2023)
    max_pages = st.number_input("Maximum pages to scrape per keyword:", min_value=1, max_value=100, value=10)

    if st.button("Scrape Articles"):
        keywords_list = [k.strip() for k in keywords.split('\n') if k.strip()]
        
        with st.spinner("Scraping articles... This may take a while."):
            df = asyncio.run(scrape_pubmed(keywords_list, start_year, end_year, max_pages))
        
        st.success(f"Scraped {len(df)} articles!")
        
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download data as CSV",
            data=csv,
            file_name="pubmed_articles.csv",
            mime="text/csv",
        )

if __name__ == "__main__":
    main()
