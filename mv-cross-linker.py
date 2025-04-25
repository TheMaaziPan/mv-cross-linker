import streamlit as st
import pandas as pd
import numpy as np
import re
from urllib.parse import urlparse
import csv
import random
import os
import io
import traceback
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import concurrent.futures
import time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string

# Download NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

# Set page configuration
st.set_page_config(
    page_title="MV Octopus Cross-linker",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
    }
    .sidebar .sidebar-content {
        background-color: #f5f5f5;
    }
    .stProgress > div > div {
        background-color: #4CAF50;
    }
    .stDownloadButton button {
        background-color: #4CAF50;
        color: white;
    }
    h1, h2, h3 {
        color: #2C3E50;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def extract_url_components(url):
    """Extract components from a URL"""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path.strip('/')
        path_segments = path.split('/')
        
        return {
            'domain': domain,
            'path': path,
            'segments': path_segments,
            'depth': len(path_segments),
            'full_url': url
        }
    except:
        return {
            'domain': '',
            'path': '',
            'segments': [],
            'depth': 0,
            'full_url': url
        }

def categorize_page(url_components, patterns):
    """Categorize a page based on its URL pattern"""
    path = url_components['path']
    
    # Check each pattern to see if it matches
    for category, pattern in patterns.items():
        if isinstance(pattern, str) and re.search(pattern, path):
            return category
    
    # Default category
    return 'other'

def fetch_page_title(url, timeout=5):
    """Fetch the page title from a URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                return title_tag.text.strip()
            h1_tag = soup.find('h1')
            if h1_tag:
                return h1_tag.text.strip()
        return None
    except Exception as e:
        return None

def generate_varied_anchor_text(url, category, title=None, content_type=None):
    """Generate varied anchor text based on URL, category, and additional info"""
    components = extract_url_components(url)
    segments = components['segments']
    
    # If we have a title, use it as a base
    if title:
        # Clean up the title
        clean_title = re.sub(r'\s*\|\s*.*$', '', title)  # Remove site name after pipe
        clean_title = re.sub(r'\s*-\s*.*$', '', clean_title)  # Remove site name after dash
        
        # Limit title length
        if len(clean_title) > 50:
            clean_title = clean_title[:47] + "..."
            
        if category == 'pdp':
            variations = [
                clean_title,
                f"View {clean_title}",
                f"Explore {clean_title}"
            ]
        elif category == 'city_plp':
            variations = [
                clean_title,
                f"Browse {clean_title}",
                f"Explore {clean_title}"
            ]
        elif category == 'state_plp':
            variations = [
                clean_title,
                f"Discover {clean_title}",
                f"Browse {clean_title}"
            ]
        elif category == 'category_plp':
            variations = [
                clean_title,
                f"Shop {clean_title}",
                f"View all {clean_title}"
            ]
        else:
            variations = [clean_title]
            
        return random.choice(variations)
    
    # Fall back to URL-based anchor text generation
    if category == 'pdp':
        # For property detail pages
        if len(segments) >= 3:
            property_id = segments[2]
            # Extract address from property ID (e.g., "123456-main-st" -> "main st")
            address_parts = property_id.split('-')
            if len(address_parts) > 1:
                address = ' '.join(address_parts[1:])
                return address.title()
        return "Property Details"
    
    elif category == 'city_plp':
        # For city listing pages
        if len(segments) >= 2:
            city = segments[1].replace('-', ' ').title()
            return f"{city} Listings"
        return "City Listings"
    
    elif category == 'state_plp':
        # For state listing pages
        if len(segments) >= 1:
            state = segments[0].upper()
            return f"{state} Listings"
        return "State Listings"
    
    elif category == 'category_plp':
        # For category listing pages
        if len(segments) >= 1:
            category_name = segments[0].replace('-', ' ').title()
            return f"{category_name} Listings"
        return "Category Listings"
    
    # Default
    return "View Listings"

def get_appropriate_placements(source_category, target_category):
    """Determine appropriate placements based on page categories"""
    if source_category == 'pdp':
        if target_category == 'city_plp' or target_category == 'state_plp':
            return ['breadcrumb', 'footer_navigation']
        elif target_category == 'category_plp':
            return ['sidebar', 'related_categories']
        else:
            return ['related_properties', 'similar_properties']
    
    elif source_category in ['city_plp', 'state_plp', 'category_plp']:
        if target_category == 'pdp':
            return ['featured_properties', 'property_grid']
        else:
            return ['related_categories', 'subcategory_links']
    
    return ['content_body', 'sidebar']

def calculate_content_similarity(source_content, target_content):
    """Calculate similarity between source and target content using TF-IDF and cosine similarity"""
    if not source_content or not target_content:
        return 0.0
    
    # Preprocess text
    def preprocess(text):
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))
        # Tokenize
        tokens = word_tokenize(text)
        # Remove stopwords
        stop_words = set(stopwords.words('english'))
        tokens = [word for word in tokens if word not in stop_words]
        return ' '.join(tokens)
    
    try:
        source_processed = preprocess(source_content)
        target_processed = preprocess(target_content)
        
        # Calculate TF-IDF
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([source_processed, target_processed])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return similarity
    except Exception as e:
        return 0.0

def parse_xml_sitemap(url):
    """Parse XML sitemap and extract URLs and other metadata"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None, f"Failed to fetch sitemap. Status code: {response.status_code}"
        
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Handle different sitemap formats
        if 'text/xml' in content_type or 'application/xml' in content_type:
            # Regular XML sitemap
            root = ET.fromstring(response.content)
            
            # Determine namespace
            namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
            if root.tag.startswith('{'):
                namespace = root.tag.split('}')[0] + '}'
            
            # Extract URLs
            urls = []
            for url_elem in root.findall(f'.//{namespace}url'):
                loc_elem = url_elem.find(f'{namespace}loc')
                if loc_elem is not None and loc_elem.text:
                    lastmod_elem = url_elem.find(f'{namespace}lastmod')
                    lastmod = lastmod_elem.text if lastmod_elem is not None else None
                    
                    priority_elem = url_elem.find(f'{namespace}priority')
                    priority = priority_elem.text if priority_elem is not None else None
                    
                    changefreq_elem = url_elem.find(f'{namespace}changefreq')
                    changefreq = changefreq_elem.text if changefreq_elem is not None else None
                    
                    urls.append({
                        'Address': loc_elem.text.strip(),
                        'Last Modified': lastmod,
                        'Priority': priority,
                        'Change Frequency': changefreq,
                        'Status Code': 200  # Assume valid URLs in sitemap
                    })
            
            return urls, None
        elif 'text/plain' in content_type:
            # Simple text sitemap
            urls = []
            for line in response.text.splitlines():
                line = line.strip()
                if line and line.startswith(('http://', 'https://')):
                    urls.append({
                        'Address': line,
                        'Status Code': 200  # Assume valid URLs in sitemap
                    })
            return urls, None
        else:
            return None, f"Unsupported sitemap format: {content_type}"
    
    except ET.ParseError as e:
        return None, f"XML parsing error: {str(e)}"
    except Exception as e:
        return None, f"Error parsing sitemap: {str(e)}"

def fetch_page_metadata(url_data, max_workers=5, sample_size=None):
    """Fetch page titles and content types for a sample of URLs"""
    urls = url_data['Address'].tolist()
    
    # Take a sample if specified
    if sample_size and sample_size < len(urls):
        sampled_urls = random.sample(urls, sample_size)
    else:
        sampled_urls = urls
    
    results = {}
    processed = 0
    total = len(sampled_urls)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def fetch_url_data(url):
        title = fetch_page_title(url)
        return url, title
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch_url_data, url): url for url in sampled_urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                url, title = future.result()
                results[url] = {'title': title}
            except Exception as e:
                results[url] = {'title': None}
            
            processed += 1
            progress = processed / total
            progress_bar.progress(progress)
            status_text.text(f"Processed {processed}/{total} URLs")
    
    # Update the original DataFrame with the fetched metadata
    titles = []
    for url in url_data['Address']:
        if url in results:
            titles.append(results[url]['title'])
        else:
            titles.append(None)
    
    url_data['Title'] = titles
    
    return url_data

def generate_cross_links(df, url_patterns, max_links=1000, use_content_similarity=False, fetch_titles=False):
    """Generate cross-linking recommendations with enhanced features"""
    # Ensure 'Address' column exists
    if 'Address' not in df.columns:
        raise ValueError("DataFrame must contain an 'Address' column with URLs")
    
    # Filter for 200 status code pages if the column exists
    if 'Status Code' in df.columns:
        df = df[df['Status Code'] == 200]
        st.info(f"Processing {len(df)} pages with 200 status code")
    else:
        st.info(f"Processing {len(df)} pages (no status code filtering)")
    
    # Fetch page titles if requested and not already present
    if fetch_titles and 'Title' not in df.columns:
        with st.spinner("Fetching page titles (sample)..."):
            df = fetch_page_metadata(df, sample_size=min(50, len(df)))
    
    # Categorize all pages
    categorized_pages = {
        'pdp': [],
        'city_plp': [],
        'state_plp': [],
        'category_plp': [],
        'other': []  # Added 'other' category to capture uncategorized pages
    }
    
    with st.spinner("Categorizing pages..."):
        for idx, row in df.iterrows():
            url = row['Address']
            components = extract_url_components(url)
            category = categorize_page(components, url_patterns)
            
            page_info = {
                'url': url,
                'components': components
            }
            
            # Add title if available
            if 'Title' in df.columns:
                page_info['title'] = row['Title']
            
            # Add content type if available
            if 'Content Type' in df.columns:
                page_info['content_type'] = row['Content Type']
            
            categorized_pages[category].append(page_info)
    
    # Print category counts
    st.write("Pages by category:")
    for category, pages in categorized_pages.items():
        st.write(f"- {category}: {len(pages)} pages")
    
    # Define linking rules
    linking_rules = [
        # PDP to PLP links
        {'source': 'pdp', 'target': 'city_plp', 'max_targets': 1, 'priority': 'high', 'placement': 'breadcrumb'},
        {'source': 'pdp', 'target': 'state_plp', 'max_targets': 1, 'priority': 'medium', 'placement': 'breadcrumb'},
        {'source': 'pdp', 'target': 'category_plp', 'max_targets': 2, 'priority': 'medium', 'placement': 'sidebar'},
        {'source': 'pdp', 'target': 'pdp', 'max_targets': 3, 'priority': 'medium', 'placement': 'related_properties'},
        
        # PLP to PDP links
        {'source': 'city_plp', 'target': 'pdp', 'max_targets': 5, 'priority': 'high', 'placement': 'featured_section'},
        {'source': 'state_plp', 'target': 'city_plp', 'max_targets': 10, 'priority': 'high', 'placement': 'main_content'},
        {'source': 'category_plp', 'target': 'pdp', 'max_targets': 5, 'priority': 'medium', 'placement': 'featured_section'},
        
        # Added more comprehensive rules
        {'source': 'category_plp', 'target': 'category_plp', 'max_targets': 5, 'priority': 'medium', 'placement': 'related_categories'},
        {'source': 'city_plp', 'target': 'city_plp', 'max_targets': 3, 'priority': 'low', 'placement': 'nearby_cities'},
        {'source': 'other', 'target': 'pdp', 'max_targets': 2, 'priority': 'low', 'placement': 'content_body'},
        {'source': 'other', 'target': 'category_plp', 'max_targets': 2, 'priority': 'low', 'placement': 'sidebar'}
    ]
    
    # Generate cross-links
    all_links = []
    link_count = 0
    
    with st.spinner("Generating cross-links..."):
        for rule in linking_rules:
            source_category = rule['source']
            target_category = rule['target']
            max_targets = rule['max_targets']
            priority = rule['priority']
            placement = rule['placement']
            link_type = f"{source_category}_to_{target_category}"
            
            # Skip if we don't have pages in either category
            if not categorized_pages[source_category] or not categorized_pages[target_category]:
                continue
            
            st.write(f"Generating {link_type} links...")
            progress_bar = st.progress(0)
            
            # For each source page, find appropriate target pages
            for i, source_page in enumerate(categorized_pages[source_category]):
                # Update progress
                if len(categorized_pages[source_category]) > 0:
                    progress_bar.progress(min(1.0, (i+1) / len(categorized_pages[source_category])))
                
                source_url = source_page['url']
                source_components = source_page['components']
                
                # Find relevant target pages
                relevant_targets = []
                
                # Enhanced matching strategy
                if source_category == 'pdp' and target_category == 'city_plp':
                    # Find the parent city page
                    for target_page in categorized_pages[target_category]:
                        target_components = target_page['components']
                        if (len(source_components['segments']) >= 2 and 
                            len(target_components['segments']) >= 2 and
                            source_components['segments'][0] == target_components['segments'][0] and
                            source_components['segments'][1] == target_components['segments'][1]):
                            relevant_targets.append(target_page)
                
                elif source_category == 'pdp' and target_category == 'state_plp':
                    # Find the parent state page
                    for target_page in categorized_pages[target_category]:
                        target_components = target_page['components']
                        if (len(source_components['segments']) >= 1 and 
                            len(target_components['segments']) >= 1 and
                            source_components['segments'][0] == target_components['segments'][0]):
                            relevant_targets.append(target_page)
                
                elif source_category == 'city_plp' and target_category == 'pdp':
                    # Find property pages in this city
                    for target_page in categorized_pages[target_category]:
                        target_components = target_page['components']
                        if (len(source_components['segments']) >= 2 and 
                            len(target_components['segments']) >= 2 and
                            source_components['segments'][0] == target_components['segments'][0] and
                            source_components['segments'][1] == target_components['segments'][1]):
                            relevant_targets.append(target_page)
                
                elif source_category == 'pdp' and target_category == 'pdp':
                    # Find similar property pages (same city, different property)
                    for target_page in categorized_pages[target_category]:
                        target_components = target_page['components']
                        if (len(source_components['segments']) >= 2 and 
                            len(target_components['segments']) >= 2 and
                            source_components['segments'][0] == target_components['segments'][0] and
                            source_components['segments'][1] == target_components['segments'][1] and
                            source_url != target_page['url']):  # Exclude self
                            relevant_targets.append(target_page)
                
                elif source_category == 'state_plp' and target_category == 'city_plp':
                    # Find city pages in this state
                    for target_page in categorized_pages[target_category]:
                        target_components = target_page['components']
                        if (len(source_components['segments']) >= 1 and 
                            len(target_components['segments']) >= 2 and
                            source_components['segments'][0] == target_components['segments'][0]):
                            relevant_targets.append(target_page)
                
                elif source_category == 'category_plp' and target_category == 'category_plp':
                    # Find related category pages (sharing common parent category)
                    for target_page in categorized_pages[target_category]:
                        target_components = target_page['components']
                        # Avoid self-links
                        if source_url != target_page['url']:
                            # Check if they share a common parent category
                            if len(source_components['segments']) >= 1 and len(target_components['segments']) >= 1:
                                if source_components['segments'][0] == target_components['segments'][0]:
                                    relevant_targets.append(target_page)
                
                else:
                    # For other combinations, use a sample of target pages
                    temp_targets = [p for p in categorized_pages[target_category] if p['url'] != source_url]
                    relevant_targets = random.sample(
                        temp_targets, 
                        min(max_targets, len(temp_targets))
                    ) if temp_targets else []
                
                # Limit number of targets
                if len(relevant_targets) > max_targets:
                    relevant_targets = relevant_targets[:max_targets]
                
                # Generate links
                for position, target_page in enumerate(relevant_targets, 1):
                    target_url = target_page['url']
                    
                    # Generate anchor text using the title if available
                    title = target_page.get('title')
                    content_type = target_page.get('content_type')
                    
                    anchor_text = generate_varied_anchor_text(
                        target_url, 
                        target_category,
                        title,
                        content_type
                    )
                    
                    # Calculate relevance score (if enabled)
                    relevance_score = 0.5  # Default medium relevance
                    
                    # Create link
                    link = {
                        'source_page': source_url,
                        'target_page': target_url,
                        'link_type': link_type,
                        'anchor_text': anchor_text,
                        'placement': placement,
                        'priority': priority,
                        'position': position if placement == 'featured_section' else '',
                        'relevance_score': relevance_score
                    }
                    
                    all_links.append(link)
                    link_count += 1
                    
                    if link_count >= max_links:
                        break
                
                if link_count >= max_links:
                    break
    
    return all_links

def test_patterns(test_url, url_patterns):
    """Test a URL against the patterns and show which category it matches"""
    components = extract_url_components(test_url)
    category = categorize_page(components, url_patterns)
    return category

def main():
    try:
        # Set up session state for page navigation
        if 'page' not in st.session_state:
            st.session_state.page = 'main'
        
        st.title("🔗 MV Octopus Cross-linker")
        
        st.markdown("""
        This app generates cross-linking recommendations for your website based on sitemap data.
        Upload a CSV sitemap export, provide an XML sitemap URL, or enter URLs manually to create a comprehensive cross-linking plan.
        """)
        
        with st.sidebar:
            st.header("Configuration")
            
            st.subheader("Step 1: Choose Data Source")
            data_source = st.radio(
                "Select data source",
                ["Upload CSV", "XML Sitemap URL", "Manual URL Entry"]
            )
            
            if data_source == "Upload CSV":
                uploaded_file = st.file_uploader("Upload your sitemap CSV", type=["csv"])
            elif data_source == "XML Sitemap URL":
                sitemap_url = st.text_input("Enter XML sitemap URL", placeholder="https://example.com/sitemap.xml")
                fetch_titles = st.checkbox("Fetch page titles (may slow down processing)", value=False)
            else:  # Manual URL Entry
                url_input = st.text_area("Enter URLs (one per line)", height=150, 
                                        placeholder="https://example.com/page1\nhttps://example.com/page2")
            
            st.subheader("Step 2: URL Pattern Configuration")
            
            # Website type template selection
            site_type = st.selectbox(
                "Select your website type",
                ["Custom", "E-commerce", "Real Estate", "Blog/Content", "Local Business"]
            )
            
            # Default patterns based on website type
            if site_type == "Real Estate":
                default_pdp_pattern = r'[a-z]{2}/[a-z-]+/\d+'  # e.g., ca/los-angeles/123456-address
                default_city_pattern = r'[a-z]{2}/[a-z-]+'  # e.g., ca/los-angeles
                default_state_pattern = r'^[a-z]{2}$'  # e.g., ca
                default_category_pattern = r'(coworking|metro-area)/'  # e.g., coworking/
            elif site_type == "E-commerce":
                default_pdp_pattern = r'product/[a-z0-9-]+'  # e.g., product/blue-t-shirt
                default_city_pattern = r'shop/[a-z-]+'  # e.g., shop/mens-clothing
                default_state_pattern = r'^shop$'  # e.g., shop
                default_category_pattern = r'category/[a-z-]+'  # e.g., category/shirts
            elif site_type == "Blog/Content":
                default_pdp_pattern = r'blog/\d{4}/\d{2}/[a-z0-9-]+'  # e.g., blog/2023/01/article-title
                default_city_pattern = r'blog/\d{4}/\d{2}'  # e.g., blog/2023/01
                default_state_pattern = r'^blog$'  # e.g., blog
                default_category_pattern = r'category/[a-z-]+'  # e.g., category/marketing
            elif site_type == "Local Business":
                default_pdp_pattern = r'services/[a-z0-9-]+'  # e.g., services/roof-repair
                default_city_pattern = r'locations/[a-z-]+'  # e.g., locations/new-york
                default_state_pattern = r'^locations$'  # e.g., locations
                default_category_pattern = r'services$'  # e.g., services
            else:  # Custom
                default_pdp_pattern = r'products?/[a-z0-9-]+'
                default_city_pattern = r'categor(y|ies)/[a-z-]+'
                default_state_pattern = r'^(home|main|index)$'
                default_category_pattern = r'collections?/[a-z-]+'
            
            # Allow customization of patterns
            pdp_pattern = st.text_input("Product/Detail Page Pattern (regex)", default_pdp_pattern)
            city_plp_pattern = st.text_input("City/Primary Listing Page Pattern (regex)", default_city_pattern)
            state_plp_pattern = st.text_input("State/Root Listing Page Pattern (regex)", default_state_pattern)
            category_plp_pattern = st.text_input("Category Listing Page Pattern (regex)", default_category_pattern)
            
            # Advanced options
            with st.expander("Advanced Options"):
                max_links = st.number_input("Maximum number of links to generate", min_value=10, max_value=10000, value=500)
                use_content_similarity = st.checkbox("Enable content similarity analysis (experimental)", value=False)
                balance_links = st.checkbox("Balance bidirectional links", value=True)
                
                # If XML sitemap is selected and fetch titles is enable
# If XML sitemap is selected and fetch titles is enabled
                if data_source == "XML Sitemap URL" and fetch_titles:
                    max_title_fetches = st.slider("Maximum pages to fetch titles for", 10, 200, 50)
        
        # Main content area
        df = None
        
        # Create tabs for workflow stages
        tab1, tab2, tab3 = st.tabs(["1️⃣ Data Preparation", "2️⃣ Link Generation", "3️⃣ Analysis & Export"])
        
        with tab1:
            # Process data source
            if data_source == "Upload CSV" and uploaded_file is not None:
                # Read CSV data
                try:
                    # Try to parse CSV
                    df = pd.read_csv(uploaded_file)
                    
                    # Show data preview
                    st.subheader("Data Preview")
                    st.dataframe(df.head())
                    
                    # Validate required columns
                    required_column = 'Address'
                    if required_column not in df.columns:
                        st.error(f"CSV is missing required column: {required_column}")
                        st.stop()
                except Exception as e:
                    st.error(f"Error processing CSV file: {e}")
                    st.code(traceback.format_exc())
                    st.stop()
                    
            elif data_source == "XML Sitemap URL" and sitemap_url:
                try:
                    with st.spinner("Fetching XML sitemap..."):
                        urls, error = parse_xml_sitemap(sitemap_url)
                        
                        if error:
                            st.error(error)
                            st.stop()
                        
                        if not urls:
                            st.warning("No URLs found in the sitemap.")
                            st.stop()
                        
                        # Convert to DataFrame
                        df = pd.DataFrame(urls)
                        
                        # Fetch page titles if requested
                        if fetch_titles:
                            with st.spinner(f"Fetching page titles (max {max_title_fetches})..."):
                                df = fetch_page_metadata(df, sample_size=max_title_fetches)
                        
                        # Show data preview
                        st.subheader("Sitemap Data Preview")
                        st.dataframe(df.head())
                        
                        st.info(f"Found {len(df)} URLs in the sitemap.")
                except Exception as e:
                    st.error(f"Error processing XML sitemap: {e}")
                    st.code(traceback.format_exc())
                    st.stop()
                    
            elif data_source == "Manual URL Entry" and url_input:
                try:
                    # Process manually entered URLs
                    urls = [url.strip() for url in url_input.strip().split('\n') if url.strip().startswith(('http://', 'https://'))]
                    
                    if not urls:
                        st.warning("No valid URLs found. Please enter URLs starting with http:// or https://")
                        st.stop()
                    
                    # Convert to DataFrame
                    df = pd.DataFrame({
                        'Address': urls,
                        'Status Code': 200  # Assume valid URLs
                    })
                    
                    # Show data preview
                    st.subheader("URL Data Preview")
                    st.dataframe(df.head())
                    
                    st.info(f"Processing {len(df)} manually entered URLs.")
                except Exception as e:
                    st.error(f"Error processing manual URLs: {e}")
                    st.code(traceback.format_exc())
                    st.stop()
                
        # Create URL patterns dictionary
        url_patterns = {
            'pdp': pdp_pattern,
            'city_plp': city_plp_pattern,
            'state_plp': state_plp_pattern,
            'category_plp': category_plp_pattern
        }
        
        # Continue only if we have data
        if df is not None:
            with tab2:
                st.subheader("Generate Cross-linking Plan")
                
                if st.button("Generate Cross-linking Plan"):
                    try:
                        # Generate links
                        links = generate_cross_links(
                            df, 
                            url_patterns, 
                            max_links=max_links, 
                            use_content_similarity=use_content_similarity,
                            fetch_titles=(data_source != "XML Sitemap URL" or not fetch_titles)
                        )
                        
                        if not links:
                            st.warning("No links were generated. Check your URL patterns and make sure they match your data.")
                            st.stop()
                        
                        # Convert links to DataFrame
                        links_df = pd.DataFrame(links)
                        
                        # Apply link balancing if enabled
                        if balance_links:
                            with st.spinner("Balancing bidirectional links..."):
                                # Identify pages with too many outgoing links
                                outgoing_counts = links_df['source_page'].value_counts()
                                incoming_counts = links_df['target_page'].value_counts()
                                
                                # Find pages with imbalanced links (many outgoing, few incoming)
                                imbalanced_pages = []
                                for page, outgoing in outgoing_counts.items():
                                    incoming = incoming_counts.get(page, 0)
                                    if outgoing > incoming * 3 and outgoing > 5:  # Arbitrary threshold
                                        imbalanced_pages.append(page)
                                
                                if imbalanced_pages:
                                    st.info(f"Found {len(imbalanced_pages)} pages with imbalanced links. Adjusting link distribution...")
                                    
                                    # Reduce outgoing links from imbalanced pages
                                    for page in imbalanced_pages:
                                        # Keep high priority links, reduce lower priority ones
                                        page_links = links_df[links_df['source_page'] == page]
                                        low_priority_links = page_links[page_links['priority'] == 'low']
                                        
                                        if len(low_priority_links) > 0:
                                            # Remove some low priority links
                                            links_to_remove = low_priority_links.sample(min(len(low_priority_links), int(outgoing_counts[page] * 0.3)))
                                            links_df = links_df.drop(links_to_remove.index)
                        
                        # Store links in session state for access in the next tab
                        st.session_state['links_df'] = links_df
                        
                        # Display results
                        st.success(f"Successfully generated {len(links_df)} cross-linking recommendations")
                        
                        # Show sample of links
                        st.dataframe(links_df.head(10))
                        
                        # Prompt to continue to analysis tab
                        st.info("Continue to the 'Analysis & Export' tab to explore the results and download your cross-linking plan.")
                        
                    except Exception as e:
                        st.error(f"Error generating cross-links: {e}")
                        st.code(traceback.format_exc())
            
            with tab3:
                st.subheader("Analysis & Export")
                
                # Check if links have been generated
                if 'links_df' in st.session_state:
                    links_df = st.session_state['links_df']
                    
                    # Summary statistics
                    st.write("### Summary Statistics")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Total Links:** {len(links_df)}")
                        
                        # Source pages count
                        source_pages_count = links_df['source_page'].nunique()
                        st.write(f"**Unique Source Pages:** {source_pages_count}")
                        
                        # Target pages count
                        target_pages_count = links_df['target_page'].nunique()
                        st.write(f"**Unique Target Pages:** {target_pages_count}")
                    
                    with col2:
                        # Most linked-to pages
                        top_targets = links_df['target_page'].value_counts().head(5)
                        st.write("**Top Target Pages:**")
                        for page, count in top_targets.items():
                            st.write(f"- {os.path.basename(page)}: {count} links")
                    
                    # Link types breakdown
                    if 'link_type' in links_df.columns:
                        st.write("### Links by Type")
                        link_types = links_df['link_type'].value_counts()
                        st.bar_chart(link_types)
                    
                    # Priority breakdown
                    if 'priority' in links_df.columns:
                        st.write("### Links by Priority")
                        priority_counts = links_df['priority'].value_counts()
                        st.bar_chart(priority_counts)
                    
                    # Placement breakdown
                    if 'placement' in links_df.columns:
                        st.write("### Links by Placement")
                        placement_counts = links_df['placement'].value_counts()
                        st.bar_chart(placement_counts)
                    
                    # Export options
                    st.write("### Export Options")
                    
                    # Format selection
                    export_format = st.radio(
                        "Select export format",
                        ["CSV", "Excel", "HTML Report"]
                    )
                    
                    if export_format == "CSV":
                        csv = links_df.to_csv(index=False)
                        st.download_button(
                            "Download Complete Cross-linking Plan (CSV)",
                            csv,
                            "cross_linking_plan.csv",
                            "text/csv",
                            key='download-csv'
                        )
                    elif export_format == "Excel":
                        # Create Excel file in memory
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            links_df.to_excel(writer, sheet_name='Cross-linking Plan', index=False)
                            
                            # Get workbook and worksheet objects
                            workbook = writer.book
                            worksheet = writer.sheets['Cross-linking Plan']
                            
                            # Add formats
                            header_format = workbook.add_format({
                                'bold': True,
                                'bg_color': '#4CAF50',
                                'color': 'white',
                                'border': 1
                            })
                            
                            # Format headers
                            for col_num, value in enumerate(links_df.columns.values):
                                worksheet.write(0, col_num, value, header_format)
                                
                            # Auto-adjust column widths
                            for i, col in enumerate(links_df.columns):
                                max_len = max(links_df[col].astype(str).apply(len).max(), len(col)) + 2
                                worksheet.set_column(i, i, min(max_len, 50))
                        
                        excel_data = output.getvalue()
                        st.download_button(
                            "Download Complete Cross-linking Plan (Excel)",
                            excel_data,
                            "cross_linking_plan.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key='download-excel'
                        )
                    else:  # HTML Report
                        # Create HTML report
                        html_buffer = io.StringIO()
                        html_buffer.write(f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <title>Cross-linking Plan</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                                h1, h2 {{ color: #2C3E50; }}
                                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                                th {{ background-color: #4CAF50; color: white; text-align: left; padding: 8px; }}
                                td {{ border: 1px solid #ddd; padding: 8px; }}
                                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                                .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                                .footer {{ margin-top: 30px; font-size: 12px; color: #777; }}
                            </style>
                        </head>
                        <body>
                            <h1>Cross-linking Plan</h1>
                            <div class="summary">
                                <h2>Summary</h2>
                                <p>Total Links: {len(links_df)}</p>
                                <p>Unique Source Pages: {links_df['source_page'].nunique()}</p>
                                <p>Unique Target Pages: {links_df['target_page'].nunique()}</p>
                                <p>Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                            </div>
                            
                            <h2>Cross-linking Plan</h2>
                            <table>
                                <tr>
                        """)
                        
                        # Add table headers
                        for col in links_df.columns:
                            html_buffer.write(f"<th>{col}</th>")
                        html_buffer.write("</tr>")
                        
                        # Add table rows (limit to 1000 rows for browser performance)
                        for _, row in links_df.head(1000).iterrows():
                            html_buffer.write("<tr>")
                            for col in links_df.columns:
                                html_buffer.write(f"<td>{row[col]}</td>")
                            html_buffer.write("</tr>")
                        
                        # Close table and add footer
                        html_buffer.write("""
                            </table>
                            
                            <div class="footer">
                                <p>Generated by MV Cross-linking Generator</p>
                            </div>
                        </body>
                        </html>
                        """)
                        
                        html_report = html_buffer.getvalue()
                        st.download_button(
                            "Download HTML Report",
                            html_report,
                            "cross_linking_report.html",
                            "text/html",
                            key='download-html'
                        )
# Implementation guide
                    with st.expander("Implementation Guide"):
                        st.markdown("""
                        ### How to Implement This Cross-linking Plan
                        
                        1. **Prioritize by importance**:
                           - Start with 'high' priority links
                           - Focus on critical page types first (e.g., PDP to category links)
                        
                        2. **Respect placement recommendations**:
                           - Place links in the suggested locations for best user experience
                           - For 'breadcrumb' placements, ensure they follow a logical hierarchy
                        
                        3. **Use the provided anchor text**:
                           - The suggested anchor text is optimized for context and relevance
                           - You can slightly modify anchor text for better readability
                        
                        4. **Implement gradually**:
                           - For large sites, implement 20-50 links per week
                           - Monitor traffic and ranking changes
                        
                        5. **Track implementation**:
                           - Add a column to this export to track implementation status
                           - Re-run analysis periodically to identify new opportunities
                        """)
                        
                    # Additional insights
                    with st.expander("Additional Insights"):
                        st.markdown("### Link Distribution Analysis")
                        
                        # Calculate link distribution metrics
                        out_degree = links_df['source_page'].value_counts()
                        in_degree = links_df['target_page'].value_counts()
                        
                        # Pages with most outgoing links
                        st.write("#### Pages with Most Outgoing Links")
                        st.dataframe(out_degree.head(10).reset_index().rename(
                            columns={'index': 'Page', 'source_page': 'Outgoing Links'}))
                        
                        # Pages with most incoming links
                        st.write("#### Pages with Most Incoming Links")
                        st.dataframe(in_degree.head(10).reset_index().rename(
                            columns={'index': 'Page', 'target_page': 'Incoming Links'}))
                        
                        # Pages with no incoming links
                        pages_with_no_incoming = set(links_df['source_page'].unique()) - set(links_df['target_page'].unique())
                        if pages_with_no_incoming:
                            st.write(f"#### {len(pages_with_no_incoming)} Pages with No Incoming Links (sample):")
                            st.write(", ".join(list(pages_with_no_incoming)[:5]))
                        
                        # Pages with no outgoing links
                        pages_with_no_outgoing = set(links_df['target_page'].unique()) - set(links_df['source_page'].unique())
                        if pages_with_no_outgoing:
                            st.write(f"#### {len(pages_with_no_outgoing)} Pages with No Outgoing Links (sample):")
                            st.write(", ".join(list(pages_with_no_outgoing)[:5]))
                
                else:
                    st.info("Please generate a cross-linking plan first in the 'Link Generation' tab.")
            
            # Add a URL Pattern Tester tool
            with st.expander("URL Pattern Tester"):
                st.write("Test your URL patterns against example URLs to verify categorization")
                test_url = st.text_input("Enter a URL to test", placeholder="https://example.com/products/test-product")
                
                if test_url:
                    category = test_patterns(test_url, url_patterns)
                    components = extract_url_components(test_url)
                    
                    st.write(f"**Categorized as:** {category}")
                    st.write("**URL Components:**")
                    st.json(components)
                    
                    if category == 'other':
                        st.warning("This URL didn't match any of your defined patterns.")
        else:
            # No data uploaded yet
            st.info("Please upload or provide URL data in the 'Data Preparation' tab to get started.")
            
            # Example/placeholder content
            with st.expander("Example Data Format"):
                st.subheader("CSV Format Example")
                example_data = pd.DataFrame({
                    'Address': [
                        'https://example.com/products/blue-shirt',
                        'https://example.com/products/red-pants',
                        'https://example.com/category/shirts',
                        'https://example.com/category/pants',
                        'https://example.com/shop'
                    ],
                    'Status Code': [200, 200, 200, 200, 200],
                    'Content Type': ['text/html', 'text/html', 'text/html', 'text/html', 'text/html'],
                    'Title': ['Blue Shirt | Example Store', 'Red Pants | Example Store', 
                             'Shirts Category | Example Store', 'Pants Category | Example Store', 
                             'Shop | Example Store']
                })
                st.dataframe(example_data)
                
                st.markdown("""
                ## Data Requirements
                
                At minimum, your data should include:
                
                - **Address**: Full URL of each page
                
                Additional helpful columns:
                - **Status Code**: HTTP status (to filter out non-200 pages)
                - **Content Type**: To identify different page types
                - **Title**: For better anchor text generation
                - **Indexability**: To focus on indexable pages
                
                ## XML Sitemap Format
                
                The app can process standard XML sitemaps in this format:
                
                ```xml
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url>
                    <loc>https://example.com/page1</loc>
                    <lastmod>2023-01-01</lastmod>
                    <changefreq>monthly</changefreq>
                    <priority>0.8</priority>
                  </url>
                  <url>
                    <loc>https://example.com/page2</loc>
                    <lastmod>2023-01-15</lastmod>
                    <changefreq>weekly</changefreq>
                    <priority>0.9</priority>
                  </url>
                </urlset>
                ```
                """)
    
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
