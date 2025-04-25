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
