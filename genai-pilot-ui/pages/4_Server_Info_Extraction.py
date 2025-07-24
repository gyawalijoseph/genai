import streamlit as st
import requests
import json
import os
from datetime import datetime

from utils.vectorSearchUtil import vector_search
from constants.server_info import SERVER_SYSTEM_PROMPT, LOCAL_BACKEND_URL, LLM_API_ENDPOINT, HEADERS

# Initialize session state for 404 logs
if '404_logs' not in st.session_state:
    st.session_state['404_logs'] = []

def log_404_error(system_prompt, user_prompt, codebase, file_source, url, timestamp):
    """
    Log 404 error with all relevant context
    """
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

def safechain_llm_call(data, system_prompt, user_prompt, extraction_mode="server_info"):
    """
    Centralized LLM API call with 404 tracking for firewall blocking
    Enhanced for dynamic extraction scenarios
    """
    extracted_data = []
    
    for result in data['results']:
        codebase = result['page_content']
        
        # Apply text cleaning based on extraction mode
        if extraction_mode in ["server_info", "database_info"]:
            codebase = codebase.replace("@aexp", "@aexps")
            codebase = codebase.replace("@", "")
            codebase = codebase.replace("aimid", "")

        st.subheader(f"📄 {result['metadata']['source']}")
        _, extension = os.path.splitext(result['metadata']['source'])
        
        with st.expander(f"View source code ({len(codebase)} characters)", expanded=False):
            st.code(codebase, language=extension[1:] if extension else "text")
        
        if len(codebase) < 4:
            st.error("⚠️ Codebase content is too short to process.")
            continue

        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
        
        payload = json.dumps({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "codebase": codebase
        })

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with st.spinner(f"Processing {result['metadata']['source']}..."):
            try:
                response = requests.request("POST", url, headers=HEADERS, data=payload, timeout=30)
                
                # Track 404 errors specifically for firewall blocking
                if response.status_code == 404:
                    st.error(f"❌ 404 Error: Request blocked by firewall")
                    log_404_error(system_prompt, user_prompt, codebase, 
                                 result['metadata']['source'], url, timestamp)
                    
                    # Display immediate 404 info in UI
                    with st.expander("🚨 404 Error Details", expanded=True):
                        st.error("**Firewall blocked this request**")
                        st.write(f"**File:** {result['metadata']['source']}")
                        st.write(f"**URL:** {url}")
                        st.write(f"**Timestamp:** {timestamp}")
                        st.text_area("System Prompt:", system_prompt, height=100, disabled=True)
                        st.text_area("User Prompt:", user_prompt, height=100, disabled=True)
                    continue
                    
                elif response.status_code != 200:
                    st.error(f"❌ HTTP {response.status_code} Error: {response.text}")
                    continue
                    
                response_json = response.json()
                status_code = response_json.get('status_code', response.status_code)
                
                if status_code == 400:
                    st.error(f"❌ LLM API Error: {response_json.get('message', 'Unknown error')}")
                    continue
                else:
                    st.success(f"✅ Successfully processed")
                    output = response_json.get('output', '')
                    
                    # Handle different extraction modes
                    if extraction_mode == "server_info":
                        try:
                            parsed_output = json.loads(output)
                            if 'host_ports' in parsed_output:
                                extracted_data.extend(parsed_output['host_ports'])
                                st.json(parsed_output['host_ports'])
                            else:
                                extracted_data.append({"raw_output": output, "file": result['metadata']['source']})
                                st.json({"raw_output": output})
                        except json.JSONDecodeError:
                            extracted_data.append({"raw_output": output, "file": result['metadata']['source']})
                            st.text_area("Raw LLM Output:", output, height=150)
                    else:
                        # Generic extraction mode
                        try:
                            parsed_output = json.loads(output)
                            extracted_data.append({
                                "file": result['metadata']['source'],
                                "extracted_data": parsed_output
                            })
                            st.json(parsed_output)
                        except json.JSONDecodeError:
                            extracted_data.append({
                                "file": result['metadata']['source'],
                                "raw_output": output
                            })
                            st.text_area("Raw LLM Output:", output, height=150)
                        
            except requests.exceptions.ConnectionError:
                st.error(f"❌ Connection Error: Could not reach LLM API at {url}")
            except requests.exceptions.Timeout:
                st.error(f"❌ Timeout Error: Request timed out after 30 seconds")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {str(e)}")

    return extracted_data

def perform_extraction(codebase, vector_results_count, search_query, system_prompt, user_prompt, extraction_mode, search_external_files):
    """
    Generic extraction function for various scenarios
    """
    st.markdown("---")
    st.subheader(f"🔍 Extraction Results - {extraction_mode.replace('_', ' ').title()}")
    
    # Determine search target
    search_target = codebase + "-external-files" if search_external_files else codebase
    
    # Vector search
    with st.spinner(f"Searching for content in {search_target}..."):
        data = vector_search(search_target, search_query, vector_results_count)
    
    if not data or 'results' not in data or len(data['results']) == 0:
        st.warning(f"No content found for query: '{search_query}'")
        return {}
    
    st.info(f"📄 Found {len(data['results'])} relevant files to process")
    
    # Extract information using safechain LLM call
    extracted_data = safechain_llm_call(data, system_prompt, user_prompt, extraction_mode)
    
    # Display results
    if extracted_data:
        st.success(f"✅ Extraction completed - {len(extracted_data)} items extracted")
        
        st.subheader("📊 Extraction Summary")
        summary = {
            "extraction_mode": extraction_mode,
            "total_items": len(extracted_data),
            "extracted_data": extracted_data
        }
        st.json(summary)
        
        return summary
    else:
        st.warning("No data could be extracted with the current prompts.")
        return {}

def display_404_logs():
    """
    Display comprehensive 404 error logs
    """
    if len(st.session_state['404_logs']) == 0:
        st.info("🎉 No 404 errors logged yet!")
        return
    
    st.error(f"🚨 {len(st.session_state['404_logs'])} 404 Errors Logged")
    
    # Download logs as JSON
    logs_json = json.dumps(st.session_state['404_logs'], indent=2)
    st.download_button(
        label="📥 Download 404 Logs as JSON",
        data=logs_json,
        file_name=f"404_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )
    
    # Display logs in expandable sections
    for i, log in enumerate(reversed(st.session_state['404_logs'])):
        with st.expander(f"🚨 404 Error #{len(st.session_state['404_logs']) - i} - {log['timestamp']} - {log['file_source']}", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**📄 File Source:**")
                st.code(log['file_source'])
                
                st.write("**🔗 URL Attempted:**")
                st.code(log['url_attempted'])
                
                st.write("**⏰ Timestamp:**")
                st.code(log['timestamp'])
                
                st.write("**📏 Codebase Length:**")
                st.code(f"{log['full_codebase_length']} characters")
            
            with col2:
                st.write("**🤖 System Prompt:**")
                st.text_area("", log['system_prompt'], height=100, disabled=True, key=f"sys_{i}")
                
                st.write("**👤 User Prompt:**")
                st.text_area("", log['user_prompt'], height=100, disabled=True, key=f"user_{i}")
            
            st.write("**📝 Codebase Snippet (first 500 chars):**")
            st.code(log['codebase_snippet'], language="text")
    
    # Clear logs button
    if st.button("🗑️ Clear All 404 Logs", type="secondary"):
        st.session_state['404_logs'] = []
        st.success("All 404 logs cleared!")
        st.rerun()

def main():
    st.set_page_config(
        page_title="Dynamic Code Extraction Tool",
        page_icon="🔧",
        layout="wide"
    )
    
    st.title("🔧 Dynamic Code Extraction Tool")
    st.markdown("**Advanced extraction with customizable prompts and comprehensive error tracking**")
    
    # Sidebar for 404 logs
    with st.sidebar:
        st.header("🚨 404 Error Tracking")
        if len(st.session_state['404_logs']) > 0:
            st.metric("Total 404 Errors", len(st.session_state['404_logs']))
        display_404_logs()
    
    # Main interface with tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Extraction", "⚙️ Advanced Settings", "📊 Presets"])
    
    with tab1:
        # Core extraction form
        with st.form("dynamic_extraction_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                codebase = st.text_input(
                    "🗂️ Codebase Name:", 
                    placeholder="my-project",
                    help="Name of the codebase to search"
                )
                
                search_query = st.text_input(
                    "🔍 Search Query:",
                    value="server host",
                    help="What to search for in the vector database"
                )
                
                extraction_mode = st.selectbox(
                    "🎯 Extraction Mode:",
                    ["server_info", "database_info", "api_endpoints", "config_files", "custom"],
                    help="Type of extraction to perform"
                )
            
            with col2:
                vector_results_count = st.number_input(
                    '📊 Results Count:', 
                    value=10,
                    min_value=1,
                    max_value=50,
                    help="Number of files to process"
                )
                
                search_external_files = st.checkbox(
                    "🔗 Search External Files",
                    value=True,
                    help="Include external files in search (adds '-external-files' suffix)"
                )
                
                timeout_seconds = st.number_input(
                    "⏱️ Request Timeout (seconds):",
                    value=30,
                    min_value=5,
                    max_value=120
                )
            
            st.markdown("### 🤖 Prompt Configuration")
            
            # Dynamic prompt selection based on extraction mode
            if extraction_mode == "server_info":
                default_system = SERVER_SYSTEM_PROMPT
                default_user = "Extract server host and port information. Return as JSON with 'host_ports' array."
            elif extraction_mode == "database_info":
                default_system = "You are an expert at analyzing code for database configurations and connections."
                default_user = "Extract database connection details, table names, and SQL queries. Return as structured JSON."
            elif extraction_mode == "api_endpoints":
                default_system = "You are an expert at analyzing code for API endpoints and routes."
                default_user = "Extract API endpoints, HTTP methods, and route handlers. Return as JSON array."
            elif extraction_mode == "config_files":
                default_system = "You are an expert at analyzing configuration files and environment variables."
                default_user = "Extract configuration keys, values, and environment variables. Return as JSON object."
            else:  # custom
                default_system = "You are a helpful code analysis assistant."
                default_user = "Analyze this code and extract relevant information."
            
            system_prompt = st.text_area(
                "🤖 System Prompt:",
                value=default_system,
                height=120,
                help="Instructions for the AI about its role and context"
            )
            
            user_prompt = st.text_area(
                "👤 User Prompt:", 
                value=default_user,
                height=100,
                help="Specific extraction instructions"
            )
            
            submit_button = st.form_submit_button(
                f'🚀 Start {extraction_mode.replace("_", " ").title()} Extraction', 
                use_container_width=True
            )

        # Process form submission
        if submit_button:
            if not codebase:
                st.error("❌ Please enter a codebase name")
            elif not search_query:
                st.error("❌ Please enter a search query")
            elif not system_prompt.strip() or not user_prompt.strip():
                st.error("❌ Both system and user prompts are required")
            else:
                try:
                    with st.spinner("🔄 Processing extraction..."):
                        result = perform_extraction(
                            codebase=codebase,
                            vector_results_count=vector_results_count,
                            search_query=search_query,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            extraction_mode=extraction_mode,
                            search_external_files=search_external_files
                        )
                    
                    if result:
                        st.balloons()
                        # Download results
                        results_json = json.dumps(result, indent=2)
                        st.download_button(
                            label="📥 Download Results as JSON",
                            data=results_json,
                            file_name=f"{extraction_mode}_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                except Exception as e:
                    st.error(f"❌ Extraction failed: {str(e)}")
    
    with tab2:
        st.header("⚙️ Advanced Configuration")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔧 API Settings")
            st.code(f"Backend URL: {LOCAL_BACKEND_URL}")
            st.code(f"LLM Endpoint: {LLM_API_ENDPOINT}")
            
            st.subheader("📊 Session Stats")
            st.metric("Total Extractions", len(st.session_state.get('extraction_history', [])))
            st.metric("404 Errors", len(st.session_state['404_logs']))
        
        with col2:
            st.subheader("🗑️ Clear Data")
            if st.button("Clear 404 Logs", type="secondary"):
                st.session_state['404_logs'] = []
                st.success("404 logs cleared!")
            
            if st.button("Clear All Session Data", type="secondary"):
                for key in list(st.session_state.keys()):
                    if key != 'extraction_history':
                        del st.session_state[key]
                st.success("Session data cleared!")
    
    with tab3:
        st.header("📊 Extraction Presets")
        st.markdown("Quick configurations for common extraction tasks:")
        
        presets = {
            "🖥️ Server Information": {
                "search_query": "server host port configuration",
                "system_prompt": SERVER_SYSTEM_PROMPT,
                "user_prompt": "Extract server host and port information. Return as JSON with 'host_ports' array.",
                "extraction_mode": "server_info"
            },
            "🗄️ Database Connections": {
                "search_query": "database connection sql query",
                "system_prompt": "You are an expert at analyzing database-related code.",
                "user_prompt": "Extract database connections, table schemas, and SQL queries. Return as structured JSON.",
                "extraction_mode": "database_info"
            },
            "🌐 API Endpoints": {
                "search_query": "api endpoint route handler",
                "system_prompt": "You are an expert at analyzing API and web service code.",
                "user_prompt": "Extract API endpoints, HTTP methods, request/response formats. Return as JSON array.",
                "extraction_mode": "api_endpoints"
            },
            "⚙️ Configuration Files": {
                "search_query": "config environment variable setting",
                "system_prompt": "You are an expert at analyzing configuration and environment files.",
                "user_prompt": "Extract configuration keys, values, environment variables, and settings. Return as JSON.",
                "extraction_mode": "config_files"
            }
        }
        
        for preset_name, preset_config in presets.items():
            with st.expander(preset_name):
                st.write(f"**Search Query:** `{preset_config['search_query']}`")
                st.write(f"**Extraction Mode:** `{preset_config['extraction_mode']}`")
                st.text_area("System Prompt:", preset_config['system_prompt'], height=80, disabled=True)
                st.text_area("User Prompt:", preset_config['user_prompt'], height=60, disabled=True)

if __name__ == "__main__":
    main()