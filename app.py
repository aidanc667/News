import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
import requests
import os
from collections import defaultdict
import time
from bs4 import BeautifulSoup
import concurrent.futures
import asyncio
import aiohttp
from functools import lru_cache

# Configuration
st.set_page_config(layout="wide", page_title="News Bias AI")

# Initialize APIs
try:
    # Try to get API keys from environment variables first, then fall back to secrets.toml
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY") or st.secrets.get("NEWS_API_KEY")
    
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in environment variables or secrets.toml")
    if not NEWS_API_KEY:
        raise ValueError("NEWS_API_KEY not found in environment variables or secrets.toml")
        
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
except Exception as e:
    st.error(f"Error initializing APIs: {str(e)}")
    st.error("Please check your API keys in environment variables or secrets.toml")
    st.stop()

# News sources mapping with domains
NEWS_SOURCES = {
    "CNN (Liberal Bias)": "cnn.com",
    "Fox News (Conservative Bias)": "foxnews.com",
    "MSNBC (Liberal Bias)": "msnbc.com",
    "The Daily Wire (Conservative Bias)": "dailywire.com"
}

# Custom CSS
st.markdown("""
<style>
.header-banner {
    background: url('https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Flag_of_the_United_States.svg/1200px-Flag_of_the_United_States.svg.png');
    background-size: 100% 100%;
    background-position: center;
    padding: 40px 0;
    border-radius: 10px;
    margin-bottom: 30px;
    color: white;
    text-align: center;
    position: relative;
    min-height: 200px;  /* Ensure enough space for the flag */
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.header-banner::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);  /* Adjusted opacity for better text visibility */
    border-radius: 10px;
    z-index: 1;
}
.header-banner h1, .header-banner p, .header-banner .date {
    position: relative;
    z-index: 2;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);  /* Increased shadow for better contrast */
}
.header-banner .date {
    font-size: 1.2rem;
    margin-top: 10px;
    font-weight: 500;
}
.article-box {
    padding: 20px;
    border-radius: 8px;
    margin: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    background: white;
}
.summary-box {
    background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
    border: 2px solid #2196F3;
}
.bias-box {
    background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
    border: 2px solid #FF9800;
}
.devil-box {
    background: linear-gradient(135deg, #FCE4EC 0%, #F8BBD0 100%);
    border: 2px solid #E91E63;
}
.article-title {
    font-weight: 600;
    margin-bottom: 5px;
    font-size: 1.6rem;
    color: #000;
}
.article-link {
    font-size: 1.3rem;
    color: #333;
}
.stExpander {
    margin: 20px 0;
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 10px;
    background: white;
}
.stExpander > div {
    padding: 15px;
}
.stExpander > div > div {
    font-size: 2.2rem;
    font-weight: bold;
    color: #000;
}
.stExpander p, .stExpander div, .stExpander li {
    font-size: 1.5rem;
    line-height: 1.8;
    color: #000;
}
.loading-spinner {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100px;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_recent_articles(source):
    """Get recent articles from a specific news source using News API"""
    try:
        # Validate source
        if source not in NEWS_SOURCES:
            st.error(f"Invalid news source: {source}")
            return []
        
        source_domain = NEWS_SOURCES[source]
        
        # News API URL
        url = f"https://newsapi.org/v2/everything"
        params = {
            'domains': source_domain,
            'language': 'en',
            'sortBy': 'publishedAt',
            'apiKey': NEWS_API_KEY,
            'pageSize': 10,  # Get more articles to filter from
            'q': 'politics OR government OR election'  # Add search query to improve results
        }
        
        # Get the articles
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            error_message = response.json().get('message', 'Unknown error')
            st.error(f"Error from News API: {response.status_code} - {error_message}")
            if response.status_code == 403:
                st.error("This might be due to an invalid API key or the API key not being properly configured.")
            return []
            
        data = response.json()
        
        if data.get('status') != 'ok':
            st.error(f"Invalid response from News API: {data.get('message', 'Unknown error')}")
            return []
            
        articles = []
        political_keywords = ['politics', 'government', 'congress', 'senate', 'white house', 'biden', 'trump', 'election', 'democrat', 'republican', 'campaign', 'vote', 'legislation', 'policy']
        
        # Process articles
        for article in data.get('articles', []):
            try:
                title = article.get('title', '')
                description = article.get('description', '')
                url = article.get('url', '')
                
                # Skip articles without required fields
                if not all([title, url]):
                    continue
                
                # Check if article is political
                is_political = any(keyword in title.lower() or keyword in description.lower() for keyword in political_keywords)
                
                articles.append({
                    'title': title,
                    'url': url,
                    'description': description,
                    'is_political': is_political
                })
            except Exception:
                continue
        
        # Filter for political articles first
        political_articles = [article for article in articles if article['is_political']]
        
        # If we don't have enough political articles, add non-political ones
        if len(political_articles) < 5:
            non_political = [article for article in articles if not article['is_political']]
            political_articles.extend(non_political)
        
        if not political_articles:
            st.error(f"No articles found from {source}")
            return []
            
        return political_articles[:5]  # Ensure we return exactly 5 articles
        
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while fetching articles: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Unexpected error while fetching articles: {str(e)}")
        return []

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def fetch_full_article(url):
    """Fetch the full article content from the URL"""
    try:
        response = requests.get(url, timeout=5)  # Reduced timeout
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements more efficiently
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Get the main content more efficiently
            article_content = ' '.join(
                p.get_text().strip() for p in soup.find_all('p')
                if len(p.get_text().strip()) > 50
            )
            
            return article_content
    except Exception as e:
        st.warning(f"Could not fetch full article: {str(e)}")
    return None

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def generate_article_summary(article_content):
    """Generate a concise summary of the article using Gemini"""
    if not article_content:
        return "Could not generate summary due to missing content."
        
    prompt = f"""
    Summarize this article in 4-5 bullet points:
    1. Main topic
    2. Key facts
    3. Main arguments
    4. Key quotes
    5. Impact
    
    Article content:
    {article_content[:4000]}  # Reduced content length for faster processing
    
    Keep each point under 10 words. Be direct and clear.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Could not generate summary due to an error."

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def analyze_bias(article_content, source):
    """Analyze the political bias in the article"""
    if not article_content:
        return "Could not analyze bias due to missing content."
        
    prompt = f"""
    Analyze bias in this {source} article. For each aspect, provide specific examples:
    1. Word choice (loaded terms)
    2. Fact selection (inclusions/exclusions)
    3. Tone (how presented)
    4. Sources (who's quoted)
    5. Conclusions (what's implied)
    
    Article content:
    {article_content[:4000]}  # Reduced content length for faster processing
    
    Keep each point under 8 words. Include specific examples.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Could not analyze bias due to an error."

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def generate_devils_advocate(article_content, source):
    """Generate a devil's advocate analysis of the article"""
    if not article_content:
        return "Could not generate devil's advocate analysis due to missing content."
        
    prompt = f"""
    Critically analyze this {source} article:
    1. Missing context
    2. Opposing views
    3. Questionable assumptions
    4. Alternative interpretations
    5. Unanswered questions
    
    Article content:
    {article_content[:4000]}  # Reduced content length for faster processing
    
    Keep each point under 8 words. Focus on gaps and alternatives.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Could not generate devil's advocate analysis due to an error."

# Header
today = datetime.now().strftime("%A, %B %d, %Y")
st.markdown(f"""
<div class="header-banner">
    <h1>News Bias AI</h1>
    <p> In-depth Analysis on Trending Articles</p>
    <div class="date">{today}</div>
</div>
""", unsafe_allow_html=True)

# News source selection
selected_source = st.selectbox(
    "Select a News Source",
    list(NEWS_SOURCES.keys()),
    index=0
)

if selected_source:
    # Extract the base source name without the bias label for processing
    base_source = selected_source.split(" (")[0]
    with st.spinner(f"Loading trending articles from {base_source}..."):
        articles = get_recent_articles(selected_source)
        
        if not articles:
            st.error(f"Could not fetch trending articles from {base_source}. Please try again later.")
            st.stop()
        
        # Display each article with analysis
        for i, article in enumerate(articles):
            with st.expander(f"### {article['title']}", expanded=False):
                # Article metadata - simplified to just the link
                st.markdown(f"""
                <div class="article-box">
                    {f'<div class="article-link"><a href="{article["url"]}" target="_blank">Read full article</a></div>' if article.get("url") else ''}
                </div>
                """, unsafe_allow_html=True)
                
                # Fetch full article content
                with st.spinner("Analyzing article..."):
                    article_content = fetch_full_article(article['url'])
                    if not article_content:
                        article_content = f"{article['title']}\n{article.get('description', '')}"
                    
                    # Create columns for different analyses
                    col1, col2, col3 = st.columns(3)
                    
                    # Summary
                    with col1:
                        st.markdown('<div class="article-box summary-box">', unsafe_allow_html=True)
                        st.markdown("### Summary")
                        summary = generate_article_summary(article_content)
                        st.markdown(summary)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Bias Analysis
                    with col2:
                        st.markdown('<div class="article-box bias-box">', unsafe_allow_html=True)
                        st.markdown("### Bias Analysis")
                        bias_analysis = analyze_bias(article_content, base_source)
                        st.markdown(bias_analysis)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Devil's Advocate
                    with col3:
                        st.markdown('<div class="article-box devil-box">', unsafe_allow_html=True)
                        st.markdown("### Devil's Advocate")
                        devils_advocate = generate_devils_advocate(article_content, base_source)
                        st.markdown(devils_advocate)
                        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown(f"""
<div style="margin-top: 50px; text-align: center; color: #7f8c8d; font-size: 0.9rem;">
    <hr style="border: 0; height: 1px; background: #ddd; margin: 20px 0;">
    <p>Analysis generated on {datetime.now().strftime("%m/%d/%Y %I:%M %p")}</p>
</div>
""", unsafe_allow_html=True)