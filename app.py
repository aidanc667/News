import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
import requests
import os
from collections import defaultdict
import time
from bs4 import BeautifulSoup

# Configuration
st.set_page_config(layout="wide", page_title="News Bias AI")

# Debug: Print environment variables (without exposing actual keys)
st.write("Checking environment variables...")
st.write("GEMINI_API_KEY exists:", "GEMINI_API_KEY" in os.environ)
st.write("NEWS_API_KEY exists:", "NEWS_API_KEY" in os.environ)

# Initialize APIs
try:
    # Try getting API keys from environment variables first
    gemini_key = os.environ.get("GEMINI_API_KEY")
    news_key = os.environ.get("NEWS_API_KEY")
    
    if not gemini_key or not news_key:
        # Fall back to secrets if environment variables aren't set
        gemini_key = st.secrets["GEMINI_API_KEY"]
        news_key = st.secrets["NEWS_API_KEY"]
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    NEWS_API_KEY = news_key
    NEWS_API_URL = "https://newsapi.org/v2/everything"
except Exception as e:
    st.error(f"Error initializing APIs: {str(e)}")
    st.stop()

# News sources mapping with domains
NEWS_SOURCES = {
    "CNN": "cnn.com",
    "Fox News": "foxnews.com",
    "Politico": "politico.com",
    "NBC News": "nbcnews.com"
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

@st.cache_data(ttl=3600)
def get_recent_articles(source):
    """Get recent articles from a specific news source"""
    today = datetime.now()
    one_day_ago = today - timedelta(days=1)
    
    # Validate source
    if source not in NEWS_SOURCES:
        st.error(f"Invalid news source: {source}")
        return []
    
    source_domain = NEWS_SOURCES[source]
    
    # First try with domain
    params = {
        'domains': source_domain,
        'language': 'en',
        'apiKey': NEWS_API_KEY,
        'pageSize': 10,  # Increased to get more articles
        'sortBy': 'publishedAt'
    }
    
    try:
        # Debug: Print the API request details (without the actual API key)
        debug_params = params.copy()
        debug_params['apiKey'] = '***'  # Hide the actual API key
        st.write("Making API request with parameters:", debug_params)
        
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        
        # Debug: Print response status and headers
        st.write("Response status code:", response.status_code)
        st.write("Response headers:", dict(response.headers))
        
        # Try to get the response text for debugging
        response_text = response.text
        st.write("Response text preview:", response_text[:200] if response_text else "No response text")
        
        articles_data = response.json()
        
        # If no articles found, try with a broader search
        if not articles_data.get('articles'):
            st.write("No articles found with domain search, trying broader search...")
            params = {
                'q': f'site:{source_domain}',
                'language': 'en',
                'apiKey': NEWS_API_KEY,
                'pageSize': 10,
                'sortBy': 'publishedAt'
            }
            response = requests.get(NEWS_API_URL, params=params, timeout=10)
            articles_data = response.json()
        
        if response.status_code != 200:
            error_msg = f"NewsAPI Error: {articles_data.get('message', 'Unknown error')}"
            if 'code' in articles_data:
                error_msg += f"\nError Code: {articles_data['code']}"
            st.error(error_msg)
            return []
            
        if not articles_data.get('articles'):
            error_msg = f"No articles found from {source}"
            if 'status' in articles_data:
                error_msg += f"\nAPI Status: {articles_data['status']}"
            if 'message' in articles_data:
                error_msg += f"\nAPI Message: {articles_data['message']}"
            st.error(error_msg)
            return []
            
        # Filter articles to only include political content
        political_articles = []
        political_keywords = ['politics', 'government', 'congress', 'senate', 'white house', 'biden', 'trump', 'election', 'democrat', 'republican', 'campaign', 'vote', 'legislation', 'policy']
        
        # Try to get 5 political articles
        for article in articles_data['articles']:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            if any(keyword in title or keyword in description for keyword in political_keywords):
                political_articles.append(article)
                if len(political_articles) >= 5:
                    break
        
        # If we don't have 5 political articles, add non-political articles to reach 5
        if len(political_articles) < 5:
            for article in articles_data['articles']:
                if article not in political_articles:
                    political_articles.append(article)
                    if len(political_articles) >= 5:
                        break
        
        if not political_articles:
            st.error(f"No articles found from {source}")
            return []
            
        return political_articles[:5]  # Ensure we return exactly 5 articles
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while fetching articles: {str(e)}")
        return []
    except ValueError as e:
        st.error(f"Error parsing API response: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Unexpected error fetching articles: {str(e)}")
        return []

def fetch_full_article(url):
    """Fetch the full article content from the URL"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Get the main content
            article_content = []
            for paragraph in soup.find_all('p'):
                text = paragraph.get_text().strip()
                if text and len(text) > 50:  # Only include substantial paragraphs
                    article_content.append(text)
            
            return ' '.join(article_content)
    except Exception as e:
        st.warning(f"Could not fetch full article: {str(e)}")
    return None

def generate_article_summary(article_content):
    """Generate a concise summary of the article using Gemini"""
    prompt = f"""
    Summarize this article in 4-5 bullet points:
    1. Main topic
    2. Key facts
    3. Main arguments
    4. Key quotes
    5. Impact
    
    Article content:
    {article_content[:8000]}
    
    Keep each point under 10 words. Be direct and clear.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Could not generate summary due to an error."

def analyze_bias(article_content, source):
    """Analyze the political bias in the article"""
    prompt = f"""
    Analyze bias in this {source} article. For each aspect, provide specific examples:
    1. Word choice (loaded terms)
    2. Fact selection (inclusions/exclusions)
    3. Tone (how presented)
    4. Sources (who's quoted)
    5. Conclusions (what's implied)
    
    Article content:
    {article_content[:8000]}
    
    Keep each point under 8 words. Include specific examples.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Could not analyze bias due to an error."

def generate_devils_advocate(article_content, source):
    """Generate a devil's advocate analysis of the article"""
    prompt = f"""
    Critically analyze this {source} article:
    1. Missing context
    2. Opposing views
    3. Questionable assumptions
    4. Alternative interpretations
    5. Unanswered questions
    
    Article content:
    {article_content[:8000]}
    
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
    with st.spinner(f"Loading trending articles from {selected_source}..."):
        articles = get_recent_articles(selected_source)
        
        if not articles:
            st.error(f"Could not fetch trending articles from {selected_source}. Please try again later.")
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
                        bias_analysis = analyze_bias(article_content, selected_source)
                        st.markdown(bias_analysis)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Devil's Advocate
                    with col3:
                        st.markdown('<div class="article-box devil-box">', unsafe_allow_html=True)
                        st.markdown("### Devil's Advocate")
                        devils_advocate = generate_devils_advocate(article_content, selected_source)
                        st.markdown(devils_advocate)
                        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown(f"""
<div style="margin-top: 50px; text-align: center; color: #7f8c8d; font-size: 0.9rem;">
    <hr style="border: 0; height: 1px; background: #ddd; margin: 20px 0;">
    <p>Analysis generated on {datetime.now().strftime("%m/%d/%Y %I:%M %p")}</p>
</div>
""", unsafe_allow_html=True)