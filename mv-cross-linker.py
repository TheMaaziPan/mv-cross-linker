import pandas as pd
import csv
import re
from urllib.parse import urlparse
import random
import os
import sys
import argparse

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
    segments = url_components['segments']
    depth = url_components['depth']
    
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
    
    # Default
    return "View Listings"

def generate_csv_export(sitemap_df, output_csv_path, url_patterns, max_links=1000):
    """
    Generate a cross-linking CSV based on sitemap data
    
    Args:
        sitemap_df: DataFrame containing sitemap data
        output_csv_path: Path to save the cross-linking CSV
        url_patterns: Dictionary of URL patterns for categorizing pages
        max_links: Maximum number of links to generate
    """
    # Ensure 'Address' column exists
    if 'Address' not in sitemap_df.columns:
        raise ValueError("DataFrame must contain an 'Address' column with URLs")
    
    # Filter for 200 status code pages if the column exists
    if 'Status Code' in sitemap_df.columns:
        sitemap_df = sitemap_df[sitemap_df['Status Code'] == 200]
    
    print(f"Processing {len(sitemap_df)} pages with 200 status code")
    
    # Categorize all pages
    categorized_pages = {
        'pdp': [],
        'city_plp': [],
        'state_plp': [],
        'category_plp': []
    }
    
    for idx, row in sitemap_df.iterrows():
        url = row['Address']
        components = extract_url_components(url)
        category = categorize_page(components, url_patterns)
        
        if category in categorized_pages:
            categorized_pages[category].append({
                'url': url,
                'components': components
            })
    
    # Print category counts
    for category, pages in categorized_pages.items():
        print(f"Found {len(pages)} {category} pages")
    
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
    
    for rule in linking_rules:
        source_category = rule['source']
        target_category = rule['target']
        max_targets = rule['max_targets']
        priority = rule['priority']
        placement = rule['placement']
        link_type = f"{source_category}_to_{target_category}"
        
        # Skip if we don't have pages in either category
        if not categorized_pages[source_category] or not categorized_pages[target_category]:
            print(f"Skipping {link_type} - missing pages in one of the categories")
            continue
        
        print(f"Generating {link_type} links...")
        
        # For each source page, find appropriate target pages
        for source_page in categorized_pages[source_category]:
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
            
            else:
                # For other combinations, just use a sample of target pages
                relevant_targets = random.sample(
                    categorized_pages[target_category], 
                    min(max_targets, len(categorized_pages[target_category]))
                )
            
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
    
    # Write to CSV
    print(f"Writing {len(all_links)} links to {output_csv_path}")
    with open(output_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['source_page', 'target_page', 'link_type', 'anchor_text', 'placement', 'priority', 'position']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for link in all_links:
            writer.writerow(link)
    
    return len(all_links)

# Example of directly loading CSV content as string (for uploads in web app)
def process_csv_content(csv_content, output_path, url_patterns, max_links=1000):
    """Process CSV content directly from a string"""
    import io
    
    # Use pandas to read the CSV content from a string
    df = pd.read_csv(io.StringIO(csv_content))
    
    # Generate the cross-linking CSV
    return generate_csv_export(df, output_path, url_patterns, max_links)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Generate cross-linking CSV from sitemap data')
    parser.add_argument('--input', '-i', help='Input sitemap CSV file path', default='sitemaps_all.csv')
    parser.add_argument('--output', '-o', help='Output cross-linking CSV file path', default='cross_linking_plan.csv')
    parser.add_argument('--max-links', '-m', type=int, help='Maximum number of links to generate', default=1000)
    parser.add_argument('--site-type', '-t', help='Site type (real_estate, ecommerce, blog)', default='real_estate')
    args = parser.parse_args()
    
    # Make sure input file exists
    if not os.path.isfile(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Files in directory: {os.listdir('.')}")
        sys.exit(1)
    
    # Define URL patterns based on site type
    if args.site_type == 'real_estate':
        url_patterns = {
            'pdp': r'[a-z]{2}/[a-z-]+/\d+',  # e.g., ca/los-angeles/123456-address
            'city_plp': r'[a-z]{2}/[a-z-]+$',  # e.g., ca/los-angeles
            'state_plp': r'^[a-z]{2}$',  # e.g., ca
            'category_plp': r'(coworking|metro-area)/'  # e.g., coworking/
        }
    elif args.site_type == 'ecommerce':
        url_patterns = {
            'pdp': r'product/[a-z0-9-]+',  # e.g., product/blue-t-shirt
            'city_plp': r'category/[a-z-]+$',  # e.g., category/t-shirts
            'state_plp': r'^shop$',  # e.g., shop
            'category_plp': r'collections?/'  # e.g., collection/
        }
    elif args.site_type == 'blog':
        url_patterns = {
            'pdp': r'blog/\d{4}/\d{2}/[a-z0-9-]+',  # e.g., blog/2023/01/post-title
            'city_plp': r'blog/\d{4}/\d{2}$',  # e.g., blog/2023/01
            'state_plp': r'^blog$',  # e.g., blog
            'category_plp': r'category/'  # e.g., category/marketing
        }
    else:
        url_patterns = {
            'pdp': r'/[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+',  # Most specific page level
            'city_plp': r'/[a-z0-9-]+/[a-z0-9-]+$',  # Second level pages
            'state_plp': r'^/[a-z0-9-]+$',  # Top level pages
            'category_plp': r'/categories?/'  # Category pages
        }
    
    # Read sitemap CSV
    print(f"Reading sitemap from {args.input}")
    df = pd.read_csv(args.input)
    
    # Generate cross-linking CSV
    num_links = generate_csv_export(
        df,
        args.output,
        url_patterns,
        max_links=args.max_links
    )
    
    print(f"Successfully generated {num_links} cross-linking recommendations")
    print(f"Output saved to {args.output}")
