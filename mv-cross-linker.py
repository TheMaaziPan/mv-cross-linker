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
