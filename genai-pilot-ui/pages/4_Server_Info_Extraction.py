import streamlit as st
import requests
import json
import os
from datetime import datetime

# Constants (embedded to keep single file)
SERVER_SYSTEM_PROMPT = "You are an expert at analyzing code for server configurations, host information, and network settings."
LOCAL_BACKEND_URL = "http://localhost:8000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}

# Initialize session state for error tracking
if '404_logs' not in st.session_state:
    st.session_state['404_logs'] = []
if 'error_logs' not in st.session_state:
    st.session_state['error_logs'] = []

def vector_search_simulation(codebase, query, count):
    """
    Simulate vector search (replace with actual implementation)
    This is a placeholder for the actual vector_search function
    """
    # This would normally call your vector search utility
    # For now, return sample structure
    return {
        'results': [
            {
                'page_content': f"Sample server config code for {query}",
                'metadata': {'source': f"{codebase}/config/server.js"}
            }
        ]
    }

def log_404_error(system_prompt, user_prompt, codebase, file_source, url, timestamp):
    """Log 404 error with all relevant context"""
    log_entry = {
        "timestamp": timestamp,
        "file_source": file_source,
        "url_attempted": url,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "codebase_snippet": codebase[:500] + "..." if len(codebase) > 500 else codebase,
        "full_codebase_length": len(codebase)
    }
    st.session_state['404_logs'].append(log_entry)

def log_error(error_type, status_code, response_text, system_prompt, user_prompt, codebase, file_source, url, timestamp, additional_info=None):
    """Log any non-200 response with full debugging metadata"""
    log_entry = {
        "timestamp": timestamp,
        "error_type": error_type,
        "status_code": status_code,
        "response_text": response_text[:1000] + "..." if len(str(response_text)) > 1000 else str(response_text),
        "file_source": file_source,
        "url_attempted": url,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "codebase_snippet": codebase[:500] + "..." if len(codebase) > 500 else codebase,
        "full_codebase_length": len(codebase),
        "payload_size": len(json.dumps({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "codebase": codebase
        })),
        "additional_info": additional_info or {}
    }
    st.session_state['error_logs'].append(log_entry)

def safechain_server_extraction(data, system_prompt, user_prompt, vector_query):
    """
    Server-focused LLM extraction with detailed flow display
    """
    st.subheader("🔍 Vector Search Results")
    st.info(f"**Vector Search Query Used:** `{vector_query}`")
    st.info(f"**Files Found:** {len(data['results'])}")
    
    server_information = []
    
    for i, result in enumerate(data['results'], 1):
        st.markdown(f"### 📄 Processing File {i}/{len(data['results'])}: `{result['metadata']['source']}`")
        
        codebase = result['page_content']
        
        # Apply text cleaning for server extraction
        original_length = len(codebase)
        codebase = codebase.replace("@aexp", "@aexps")
        codebase = codebase.replace("@", "")
        codebase = codebase.replace("aimid", "")
        
        st.write(f"**📊 Content Length:** {original_length} → {len(codebase)} characters (after cleaning)")
        
        # Display codebase content
        with st.expander(f"📖 View Source Code - {result['metadata']['source']}", expanded=False):
            _, extension = os.path.splitext(result['metadata']['source'])
            st.code(codebase, language=extension[1:] if extension else "text")
        
        if len(codebase) < 4:
            st.error("⚠️ Codebase content is too short to process.")
            continue

        # Show LLM request details
        st.write("**🤖 LLM Request Configuration:**")
        col1, col2 = st.columns(2)
        with col1:
            st.text_area("System Prompt:", system_prompt, height=100, disabled=True, key=f"sys_{i}")
        with col2:
            st.text_area("User Prompt:", user_prompt, height=100, disabled=True, key=f"user_{i}")

        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
        st.write(f"**🌐 API Endpoint:** `{url}`")
        
        payload = json.dumps({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "codebase": codebase
        })

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with st.spinner(f"🔄 Sending request to LLM for {result['metadata']['source']}..."):
            try:
                response = requests.request("POST", url, headers=HEADERS, data=payload, timeout=300)
                
                # Track 404 errors specifically for firewall blocking
                if response.status_code == 404:
                    st.error("❌ **404 Error: Request blocked by firewall**")
                    log_404_error(system_prompt, user_prompt, codebase, 
                                 result['metadata']['source'], url, timestamp)
                    log_error("404_firewall_block", 404, response.text, system_prompt, user_prompt,
                             codebase, result['metadata']['source'], url, timestamp)
                    
                    # Display immediate 404 info in UI
                    with st.expander("🚨 404 Error Details", expanded=True):
                        st.error("**Firewall blocked this request**")
                        st.write(f"**File:** {result['metadata']['source']}")
                        st.write(f"**URL:** {url}")
                        st.write(f"**Timestamp:** {timestamp}")
                        st.json({
                            "system_prompt": system_prompt,
                            "user_prompt": user_prompt,
                            "codebase_length": len(codebase),
                            "response_text": response.text
                        })
                    # Continue to next file instead of stopping
                    continue
                    
                elif response.status_code != 200:
                    st.error(f"❌ **HTTP {response.status_code} Error:** {response.text}")
                    log_error(f"http_{response.status_code}", response.status_code, response.text,
                             system_prompt, user_prompt, codebase, result['metadata']['source'], 
                             url, timestamp, {"headers": dict(response.headers)})
                    
                    # Show detailed error info but continue processing
                    with st.expander(f"🔍 HTTP {response.status_code} Error Details", expanded=False):
                        st.json({
                            "status_code": response.status_code,
                            "response_text": response.text,
                            "response_headers": dict(response.headers),
                            "file": result['metadata']['source'],
                            "timestamp": timestamp
                        })
                    continue
                    
                # Handle successful HTTP response
                try:
                    response_json = response.json()
                except json.JSONDecodeError as e:
                    st.error(f"❌ **Invalid JSON Response:** Could not parse response")
                    log_error("invalid_json_response", 200, response.text, system_prompt, user_prompt,
                             codebase, result['metadata']['source'], url, timestamp, 
                             {"json_error": str(e)})
                    with st.expander("🔍 Invalid JSON Response Details", expanded=False):
                        st.text_area("Raw Response:", response.text, height=150)
                    continue
                
                status_code = response_json.get('status_code', response.status_code)
                
                if status_code == 400:
                    st.error(f"❌ **LLM API Error:** {response_json.get('message', 'Unknown error')}")
                    log_error("llm_api_400", 400, response_json.get('message', 'Unknown error'),
                             system_prompt, user_prompt, codebase, result['metadata']['source'],
                             url, timestamp, {"full_response": response_json})
                    
                    with st.expander("🔍 LLM API Error Details", expanded=False):
                        st.json(response_json)
                    continue
                else:
                    st.success(f"✅ **Successfully processed:** {result['metadata']['source']}")
                    output = response_json.get('output', '')
                    
                    # Display raw LLM output first
                    with st.expander("🔍 Raw LLM Response", expanded=False):
                        st.text_area("Raw Output:", output, height=150, key=f"raw_{i}")
                    
                    # Try to parse server information
                    try:
                        parsed_output = json.loads(output)
                        if 'host_ports' in parsed_output and parsed_output['host_ports']:
                            st.success(f"🎯 **Found {len(parsed_output['host_ports'])} server entries**")
                            st.json(parsed_output['host_ports'])
                            server_information.extend(parsed_output['host_ports'])
                        else:
                            st.warning("⚠️ No server host/port information found in structured format")
                            st.json(parsed_output)
                            server_information.append({
                                "file": result['metadata']['source'],
                                "raw_output": output
                            })
                    except json.JSONDecodeError:
                        st.warning("⚠️ LLM response is not valid JSON")
                        st.text_area("Raw Output:", output, height=150, key=f"raw_fallback_{i}")
                        server_information.append({
                            "file": result['metadata']['source'],
                            "raw_output": output
                        })
                        
            except requests.exceptions.ConnectionError as e:
                st.error(f"❌ **Connection Error:** Could not reach LLM API at {url}")
                log_error("connection_error", None, str(e), system_prompt, user_prompt,
                         codebase, result['metadata']['source'], url, timestamp)
                # Continue to next file
                continue
                
            except requests.exceptions.Timeout as e:
                st.warning(f"⏰ **Timeout Warning:** Request timed out after 300 seconds - continuing with next file")
                log_error("timeout", None, f"Request timed out after 300 seconds: {str(e)}", 
                         system_prompt, user_prompt, codebase, result['metadata']['source'], 
                         url, timestamp)
                # Continue to next file instead of stopping
                continue
                
            except Exception as e:
                st.error(f"❌ **Unexpected Error:** {str(e)} - continuing with next file")
                log_error("unexpected_error", None, str(e), system_prompt, user_prompt,
                         codebase, result['metadata']['source'], url, timestamp)
                # Continue to next file
                continue

        st.markdown("---")

    return server_information

def display_error_logs():
    """Display comprehensive error logs with debugging metadata"""
    total_404s = len(st.session_state['404_logs'])
    total_errors = len(st.session_state['error_logs'])
    
    if total_404s == 0 and total_errors == 0:
        st.info("🎉 No errors logged yet!")
        return
    
    # Summary metrics
    if total_404s > 0:
        st.error(f"🚨 {total_404s} 404 Errors")
    if total_errors > 0:
        st.warning(f"⚠️ {total_errors} Other Errors")
    
    # Download all logs as JSON
    all_logs = {
        "404_errors": st.session_state['404_logs'],
        "other_errors": st.session_state['error_logs'],
        "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    logs_json = json.dumps(all_logs, indent=2)
    st.download_button(
        label="📥 Download All Error Logs",
        data=logs_json,
        file_name=f"error_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )
    
    # Display 404 logs
    if total_404s > 0:
        st.subheader("🚨 404 Firewall Blocks")
        for i, log in enumerate(reversed(st.session_state['404_logs'])):
            with st.expander(f"404 #{total_404s - i} - {log['timestamp']} - {log['file_source']}", expanded=(i == 0)):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**📄 File Source:**")
                    st.code(log['file_source'])
                    
                    st.write("**🔗 URL Attempted:**")
                    st.code(log['url_attempted'])
                    
                    st.write("**⏰ Timestamp:**")
                    st.code(log['timestamp'])
                
                with col2:
                    st.write("**📏 Codebase Length:**")
                    st.code(f"{log['full_codebase_length']} characters")
                    
                    st.write("**🤖 System Prompt (truncated):**")
                    st.code(log['system_prompt'][:100] + "..." if len(log['system_prompt']) > 100 else log['system_prompt'])
                
                st.write("**📝 Codebase Snippet:**")
                st.code(log['codebase_snippet'], language="text")
    
    # Display other error logs
    if total_errors > 0:
        st.subheader("⚠️ All Other Errors")
        for i, log in enumerate(reversed(st.session_state['error_logs'])):
            error_color = "🚨" if log['status_code'] and log['status_code'] >= 500 else "⚠️"
            with st.expander(f"{error_color} {log['error_type']} #{total_errors - i} - {log['timestamp']} - {log['file_source']}", expanded=(i == 0)):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**🏷️ Error Type:**")
                    st.code(log['error_type'])
                    
                    st.write("**📄 File Source:**")
                    st.code(log['file_source'])
                    
                    st.write("**🔗 URL:**")
                    st.code(log['url_attempted'])
                    
                    st.write("**⏰ Timestamp:**")
                    st.code(log['timestamp'])
                
                with col2:
                    if log['status_code']:
                        st.write("**📊 Status Code:**")
                        st.code(log['status_code'])
                    
                    st.write("**📏 Payload Size:**")
                    st.code(f"{log['payload_size']} bytes")
                    
                    st.write("**📏 Codebase Length:**")
                    st.code(f"{log['full_codebase_length']} characters")
                
                st.write("**🔍 Response Text:**")
                st.code(log['response_text'])
                
                if log['additional_info']:
                    st.write("**🔧 Additional Debug Info:**")
                    st.json(log['additional_info'])
                
                with st.expander("Full Context", expanded=False):
                    st.write("**🤖 System Prompt:**")
                    st.text_area("", log['system_prompt'], height=100, disabled=True, key=f"sys_err_{i}")
                    
                    st.write("**👤 User Prompt:**")
                    st.text_area("", log['user_prompt'], height=100, disabled=True, key=f"user_err_{i}")
                    
                    st.write("**📝 Codebase Snippet:**")
                    st.code(log['codebase_snippet'], language="text")
    
    # Clear logs buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear 404 Logs", type="secondary"):
            st.session_state['404_logs'] = []
            st.success("404 logs cleared!")
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear All Error Logs", type="secondary"):
            st.session_state['404_logs'] = []
            st.session_state['error_logs'] = []
            st.success("All error logs cleared!")
            st.rerun()

def main():
    st.set_page_config(
        page_title="Server Information Extraction",
        page_icon="🖥️",
        layout="wide"
    )
    
    st.title("🖥️ Server Information Extraction")
    st.markdown("**Extract server host and port information with detailed processing flow**")
    
    # Sidebar for error tracking
    with st.sidebar:
        st.header("🚨 Error Tracking & Debug")
        total_404s = len(st.session_state['404_logs'])
        total_errors = len(st.session_state['error_logs'])
        
        if total_404s > 0 or total_errors > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("404 Errors", total_404s)
            with col2:
                st.metric("Other Errors", total_errors)
        
        display_error_logs()
    
    # Main extraction form
    with st.form("server_extraction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            codebase = st.text_input(
                "🗂️ Codebase Name:", 
                placeholder="my-project",
                help="Name of the codebase to search for server information"
            )
            
            vector_query = st.text_input(
                "🔍 Vector Search Query:",
                value="server host port configuration",
                help="Query used to find relevant files in vector database"
            )
        
        with col2:
            vector_results_count = st.number_input(
                '📊 Max Results Count:', 
                value=10,
                min_value=1,
                max_value=50,
                help="Maximum number of files to process from vector search"
            )
        
        st.markdown("### 🤖 LLM Prompt Configuration")
        
        system_prompt = st.text_area(
            "🤖 System Prompt:",
            value=SERVER_SYSTEM_PROMPT,
            height=100,
            help="Instructions for the AI about its role and context"
        )
        
        user_prompt = st.text_area(
            "👤 User Prompt:", 
            value="Extract server host and port information from this code snippet. Return as JSON with 'host_ports' array containing objects with 'host' and 'port' fields. If no server information is found, return empty array.",
            height=100,
            help="Specific extraction instructions for server information"
        )
        
        submit_button = st.form_submit_button(
            '🚀 Start Server Information Extraction', 
            use_container_width=True
        )

    # Process form submission
    if submit_button:
        if not codebase:
            st.error("❌ Please enter a codebase name")
        elif not vector_query.strip():
            st.error("❌ Please enter a vector search query")
        elif not system_prompt.strip() or not user_prompt.strip():
            st.error("❌ Both system and user prompts are required")
        else:
            try:
                st.markdown("---")
                st.header("🔄 Processing Flow")
                
                # Step 1: Vector Search
                st.subheader("📊 Step 1: Vector Database Search")
                search_target = codebase + "-external-files"  # Always search external files
                st.info(f"**Target Database:** `{search_target}`")
                st.info(f"**Search Query:** `{vector_query}`")
                st.info(f"**Max Results:** {vector_results_count}")
                
                with st.spinner("🔍 Searching vector database..."):
                    # Replace this with actual vector_search call
                    # data = vector_search(search_target, vector_query, vector_results_count)
                    data = vector_search_simulation(search_target, vector_query, vector_results_count)
                
                if not data or 'results' not in data or len(data['results']) == 0:
                    st.warning(f"❌ No content found for query: '{vector_query}' in database: '{search_target}'")
                    st.info("💡 Try adjusting your search query or check if the codebase embeddings exist")
                else:
                    # Step 2: LLM Processing
                    st.subheader("🤖 Step 2: LLM Processing & Server Extraction")
                    
                    server_information = safechain_server_extraction(
                        data, system_prompt, user_prompt, vector_query
                    )
                    
                    # Step 3: Final Results
                    st.header("🎯 Final Results")
                    if server_information:
                        st.success(f"✅ **Extraction completed successfully!** Found {len(server_information)} server entries")
                        
                        # Summary
                        summary = {
                            "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "codebase": search_target,
                            "vector_query": vector_query,
                            "total_files_processed": len(data['results']),
                            "total_servers_found": len(server_information),
                            "server_details": server_information
                        }
                        
                        st.json(summary)
                        
                        # Download results
                        results_json = json.dumps(summary, indent=2)
                        st.download_button(
                            label="📥 Download Server Info as JSON",
                            data=results_json,
                            file_name=f"server_extraction_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                        
                        st.balloons()
                    else:
                        st.warning("⚠️ No server information could be extracted from the codebase")
                        st.info("💡 Try adjusting your prompts or search query")
                        
            except Exception as e:
                st.error(f"❌ **Extraction failed:** {str(e)}")
                st.error("Please check if the codebase embeddings exist and the backend is running")

if __name__ == "__main__":
    main()