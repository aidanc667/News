# Political News Bias Analyzer

This Streamlit application analyzes and compares political news coverage between liberal (CNN) and conservative (Fox News) sources. It identifies the top 5 trending political topics and provides a detailed comparison of how each side covers these stories.

## Setup

1. Clone this repository
2. Create a `.env` file in the root directory with your API keys:
   ```
   NEWS_API_KEY=your_news_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

To run the application, use the following command:
```bash
streamlit run app.py
```

## Features

- Real-time analysis of political news from CNN and Fox News
- Top 5 trending political topics identified automatically
- Side-by-side comparison of liberal and conservative coverage
- Detailed bias analysis for each topic
- Article summaries and direct links to source material

## Requirements

- Python 3.7+
- NewsAPI key
- Google Gemini API key
- Internet connection

## Note

The application requires valid API keys for both NewsAPI and Google Gemini. Make sure to keep your API keys secure and never commit them to version control. 