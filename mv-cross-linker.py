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

# Set page configuration
st.set_page_config(
    page_title="Cross-linking Generator",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def generate_anchor_text(url, category):
    """Generate appropriate anchor text based on URL and category"""
    components = extract_url_components(url)
    segments = components['segments']
    
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

def generate_cross_links(df, url_patterns, max_links=1000):
    """Generate cross-linking recommendations"""
    # Ensure 'Address' column exists
    if 'Address' not in df.columns:
        raise ValueError("DataFrame must contain an 'Address' column with URLs")
    
    # Filter for 200 status code pages if the column exists
    if 'Status Code' in df.columns:
        df = df[df['Status Code'] == 200]
        st.info(f"Processing {len(df)} pages with 200 status code")
    else:
        st.info(f"Processing {len(df)} pages (no status code filtering)")
    
    # Categorize all pages
    categorized_pages = {
        'pdp': [],
        'city_plp': [],
        'state_plp': [],
        'category_plp': []
    }
    
    with st.spinner("Categorizing pages..."):
        for idx, row in df.iterrows():
            url = row['Address']
            components = extract_url_components(url)
            category = categorize_page(components, url_patterns)
            
            if category in categorized_pages:
                categorized_pages[category].append({
                    'url': url,
                    'components': components
                })
    
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
        {'source': 'category_plp', 'target': 'pdp', 'max_targets': 5, 'priority': 'medium', 'placement': 'featured_section'}
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
                
                # Simple matching strategy - can be enhanced
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
                
                else:
                    # For other combinations, just use a sample of target pages
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
                    
                    # Generate anchor text
                    anchor_text = generate_anchor_text(target_url, target_category)
                    
                    # Create link
                    link = {
                        'source_page': source_url,
                        'target_page': target_url,
                        'link_type': link_type,
                        'anchor_text': anchor_text,
                        'placement': placement,
                        'priority': priority,
                        'position': position if placement == 'featured_section' else ''
                    }
                    
                    all_links.append(link)
                    link_count += 1
                    
                    if link_count >= max_links:
                        break
                
                if link_count >= max_links:
                    break
    
    return all_links

def main():
    try:
        st.title("🔗 Website Cross-linking Generator")
        
        st.markdown("""
        This app generates cross-linking recommendations for your website based on a sitemap export CSV.
        Upload your sitemap data, configure patterns for different page types, and generate a comprehensive cross-linking plan.
        """)
        
        with st.sidebar:
            st.header("Configuration")
            
            st.subheader("Step 1: Upload Sitemap CSV")
            uploaded_file = st.file_uploader("Upload your sitemap CSV", type=["csv"])
            
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
        
        # Main content area
        if uploaded_file is not None:
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
                
                # Create URL patterns dictionary
                url_patterns = {
                    'pdp': pdp_pattern,
                    'city_plp': city_plp_pattern,
                    'state_plp': state_plp_pattern,
                    'category_plp': category_plp_pattern
                }
                
                # Generate cross-linking plan
                if st.button("Generate Cross-linking Plan"):
                    try:
                        # Generate links
                        links = generate_cross_links(df, url_patterns, max_links)
                        
                        if not links:
                            st.warning("No links were generated. Check your URL patterns and make sure they match your data.")
                            st.stop()
                        
                        # Convert links to DataFrame
                        links_df = pd.DataFrame(links)
                        
                        # Display results
                        st.subheader("Cross-linking Plan")
                        st.write(f"Generated {len(links)} cross-linking recommendations")
                        
                        # Show sample of links
                        st.dataframe(links_df.head(20))
                        
                        # Provide download link
                        csv = links_df.to_csv(index=False)
                        st.download_button(
                            "Download Complete Cross-linking Plan (CSV)",
                            csv,
                            "cross_linking_plan.csv",
                            "text/csv",
                            key='download-csv'
                        )
                        
                        # Summary statistics
                        st.subheader("Summary Statistics")
                        
                        # Link types breakdown
                        if 'link_type' in links_df.columns:
                            link_types = links_df['link_type'].value_counts()
                            st.write("Links by Type:")
                            st.bar_chart(link_types)
                        
                        # Priority breakdown
                        if 'priority' in links_df.columns:
                            priority_counts = links_df['priority'].value_counts()
                            st.write("Links by Priority:")
                            st.bar_chart(priority_counts)
                        
                        # Placement breakdown
                        if 'placement' in links_df.columns:
                            placement_counts = links_df['placement'].value_counts()
                            st.write("Links by Placement:")
                            st.bar_chart(placement_counts)
                        
                    except Exception as e:
                        st.error(f"Error generating cross-links: {e}")
                        st.code(traceback.format_exc())
                
            except Exception as e:
                st.error(f"Error processing CSV file: {e}")
                st.code(traceback.format_exc())
        else:
            # Example/placeholder content
            st.info("Please upload a sitemap CSV file to generate a cross-linking plan.")
            
            st.subheader("Example CSV Format")
            example_data = pd.DataFrame({
                'Address': [
                    'https://example.com/products/blue-shirt',
                    'https://example.com/products/red-pants',
                    'https://example.com/category/shirts',
                    'https://example.com/category/pants',
                    'https://example.com/shop'
                ],
                'Status Code': [200, 200, 200, 200, 200],
                'Content Type': ['text/html', 'text/html', 'text/html', 'text/html', 'text/html']
            })
            st.dataframe(example_data)
            
            st.markdown("""
            ## What to Include in Your Sitemap CSV
            
            At minimum, your CSV should include:
            
            - **Address**: Full URL of each page
            - **Status Code**: HTTP status (to filter out non-200 pages)
            
            Additional helpful columns:
            - **Content Type**: To identify different page types
            - **Title**: For better anchor text generation
            - **Indexability**: To focus on indexable pages
            """)
    
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
