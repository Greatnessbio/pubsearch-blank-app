import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
import time

# User agents list (abbreviated for brevity)
user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36"
]

def make_header():
    return {'User-Agent': random.choice(user_agents)}

async def extract_by_article(url, semaphore):
    async with semaphore:
        async with aiohttp.ClientSession(headers=make_header()) as session:
            async with session.get(url) as response:
                data = await response.text()
                soup = BeautifulSoup(data, "lxml")
                
                title = soup.find('h1', {'class': 'heading-title'})
                title = title.text.strip() if title else 'N/A'
                
                abstract_div = soup.find('div', {'id': 'abstract'})
                abstract = 'N/A'
                if abstract_div:
                    abstract_content = abstract_div.find('div', {'class': 'abstract-content selected'})
                    if abstract_content:
                        abstract = ' '.join([p.text.strip() for p in abstract_content.find_all('p')])
                
                authors = []
                authors_div = soup.find('div', {'class': 'authors-list'})
                if authors_div:
                    for author in authors_div.find_all('span', {'class': 'authors-list-item'}):
                        name = author.find('a', {'class': 'full-name'})
                        if name:
                            authors.append(name.text.strip())
                
                date_elem = soup.find('span', {'class': 'cit'}) or soup.find('time', {'class': 'citation-year'})
                date = date_elem.text.strip() if date_elem else 'N/A'
                
                journal_elem = soup.find('button', {'id': 'full-view-journal-trigger'}) or soup.find('span', {'class': 'journal-title'})
                journal = journal_elem.text.strip() if journal_elem else 'N/A'
                
                return {
                    'url': url,
                    'title': title,
                    'authors': ', '.join(authors),
                    'abstract': abstract,
                    'date': date,
                    'journal': journal
                }

async def get_pmids(page, keyword, session):
    url = f'https://pubmed.ncbi.nlm.nih.gov/?term={keyword}&page={page}'
    async with session.get(url) as response:
        data = await response.text()
        soup = BeautifulSoup(data, "lxml")
        pmids = soup.find('meta', {'name': 'log_displayeduids'})
        if pmids:
            return [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in pmids['content'].split(',')]
        return []

async def scrape_pubmed(keywords, start_year, end_year, max_pages):
    semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
    all_urls = []
    async with aiohttp.ClientSession(headers=make_header()) as session:
        for keyword in keywords:
            for page in range(1, max_pages + 1):
                urls = await get_pmids(page, f"{keyword} AND ({start_year}:{end_year}[dp])", session)
                all_urls.extend(urls)
                if len(urls) < 10:  # Less than 10 results on a page means it's the last page
                    break
        
        tasks = [extract_by_article(url, semaphore) for url in all_urls]
        results = await asyncio.gather(*tasks)
    
    return pd.DataFrame(results)

def main():
    st.title("PubMed Article Scraper")

    # User inputs
    keywords = st.text_area("Enter keywords (one per line):", "artificial intelligence\nmachine learning")
    start_year = st.number_input("Start year:", min_value=1900, max_value=2023, value=2019)
    end_year = st.number_input("End year:", min_value=1900, max_value=2023, value=2023)
    max_pages = st.number_input("Maximum pages to scrape per keyword:", min_value=1, max_value=100, value=10)

    if st.button("Scrape Articles"):
        keywords_list = [k.strip() for k in keywords.split('\n') if k.strip()]
        
        start_time = time.time()
        with st.spinner("Scraping articles... This may take a while."):
            df = asyncio.run(scrape_pubmed(keywords_list, start_year, end_year, max_pages))
        end_time = time.time()
        
        st.success(f"Scraped {len(df)} articles in {end_time - start_time:.2f} seconds!")
        
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
