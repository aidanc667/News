import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
import requests
import os
from collections import defaultdict
import time
from bs4 import BeautifulSoup

# Configuration
st.set_page_config(layout="wide", page_title="News Bias Analyzer")

# Initialize Gemini
GEMINI_API_KEY = "AIzaSyAMXBR4JBXw0Y3d5sxfUwQgHJCI8VqddlM"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize NewsAPI
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "71c14398131a486d8135d30e80e45dd4")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# News sources mapping
NEWS_SOURCES = {
    "CNN": "cnn",
    "Fox News": "fox-news",
    "MSNBC": "msnbc"
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
    
    params = {
        'sources': source,
        'from': one_day_ago.strftime('%Y-%m-%dT%H:%M:%S'),
        'to': today.strftime('%Y-%m-%dT%H:%M:%S'),
        'sortBy': 'popularity',
        'language': 'en',
        'apiKey': NEWS_API_KEY,
        'pageSize': 5,
        'q': 'politics OR election OR congress OR senate OR president OR government OR policy OR legislation OR bill OR law'
    }
    
    try:
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        articles_data = response.json()
        
        if not articles_data.get('articles'):
            st.error(f"No trending articles found from {source} in the last 24 hours")
            return []
            
        return articles_data['articles']
    except Exception as e:
        st.error(f"Error fetching articles: {str(e)}")
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
    Provide a clear and concise summary of this article. Include:
    1. Main topic and context
    2. Key facts and figures
    3. Main arguments and positions
    4. Important quotes or statements
    5. Potential implications
    
    Article content:
    {article_content[:8000]}
    
    Return 4-5 bullet points, each 12-20 words long, focusing on the most important aspects.
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
    1. Word choice and framing (loaded terms, emotional language)
    2. Fact selection (what's included/excluded)
    3. Tone and perspective (how issues are presented)
    4. Sources used (who is quoted, who isn't)
    5. Conclusions drawn (what's suggested)
    
    Article content:
    {article_content[:8000]}
    
    Return 4-5 bullet points, each 10-15 words long, with specific examples from the text.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Could not analyze bias due to an error."

def generate_devils_advocate(article_content, source):
    """Generate a devil's advocate analysis of the article"""
    prompt = f"""
    Provide a critical analysis of this {source} article. Consider:
    1. Missing information or context (what's not being said)
    2. Opposing viewpoints (how others might see this)
    3. Questionable assumptions (what's being taken for granted)
    4. Alternative interpretations (other ways to understand the facts)
    5. Unanswered questions (what remains unclear)
    
    Article content:
    {article_content[:8000]}
    
    Return 4-5 bullet points, each 12-20 words long, focusing on specific gaps or alternative perspectives.
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
    <h1>News Bias Analyzer</h1>
    <p>Analyze Trending Articles with AI-Powered Insights</p>
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
        articles = get_recent_articles(NEWS_SOURCES[selected_source])
        
        if not articles:
            st.error(f"Could not fetch trending articles from {selected_source}. Please try again later.")
            st.stop()
        
        # Display each article with analysis
        for i, article in enumerate(articles):
            with st.expander(f"### {article['title']}", expanded=False):  # Changed to always be False
                # Article metadata
                st.markdown(f"""
                <div class="article-box">
                    <div class="article-title">{article['title']}</div>
                    <div>{article.get('description', 'No description available')}</div>
                    {f'<div class="article-link">Published: {datetime.strptime(article["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").strftime("%m-%d-%Y %I:%M %p")}</div>' if article.get("publishedAt") else ''}
                    {f'<div class="article-link"><a href="{article["url"]}" target="_blank">Read full article</a></div>' if article.get("url") else ''}
                </div>
                """, unsafe_allow_html=True)
                
                # Fetch full article content
                with st.spinner("Fetching and analyzing article content..."):
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