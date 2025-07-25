import streamlit as st
import requests
import json
import os
from datetime import datetime

# Constants
SERVER_SYSTEM_PROMPT = "You are an expert at analyzing code for server configurations, host information, and network settings."
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}

# Initialize session state for error tracking
if 'multi_404_logs' not in st.session_state:
    st.session_state['multi_404_logs'] = []
if 'multi_error_logs' not in st.session_state:
    st.session_state['multi_error_logs'] = []


def vector_search(codebase, similarity_search_query, vector_results_count):
    """Vector search implementation"""
    url = "http://localhost:5000/vector-search"
    payload = {
        "codebase": codebase,
        "query": similarity_search_query,
        "vector_results_count": vector_results_count
    }

    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=60)

        if response.status_code != 200:
            # Log vector search error for ANY non-200 status code
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if response.status_code == 404:
                log_404_error("Vector search system", f"Query: {similarity_search_query}", 
                             f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
            
            log_error(f"vector_search_{response.status_code}", response.status_code, response.text, 
                     "Vector search system", f"Query: {similarity_search_query}", 
                     f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
            return {"results": []}

        data = response.json()

        # Validate the response structure
        if not isinstance(data, dict) or 'results' not in data:
            return {"results": []}

        if not data['results']:
            return {"results": []}

        return data

    except requests.exceptions.ConnectionError as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_connection_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except requests.exceptions.Timeout as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_timeout_error", None, f"Timeout after 60 seconds: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except json.JSONDecodeError as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_json_parse_error", None, f"JSON decode error: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_general_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}


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
    st.session_state['multi_404_logs'].append(log_entry)


def log_error(error_type, status_code, response_text, system_prompt, user_prompt, codebase, file_source, url, timestamp,
              additional_info=None):
    """Log any non-200 response with complete debugging metadata - fully dynamic"""
    
    log_entry = {
        "timestamp": timestamp,
        "error_type": error_type,
        "status_code": status_code,
        "response_text": str(response_text),
        "response_text_truncated": response_text[:1000] + "..." if len(str(response_text)) > 1000 else str(response_text),
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
        "additional_info": additional_info or {},
        "error_severity": "HIGH" if status_code and status_code >= 500 else "MEDIUM" if status_code and status_code >= 400 else "LOW"
    }
    st.session_state['multi_error_logs'].append(log_entry)


def process_single_codebase(codebase, system_prompt, vector_query, vector_results_count):
    """Process a single codebase and return server information"""
    search_target = codebase + "-external-files"
    
    # Step 1: Vector Search
    data = vector_search(search_target, vector_query, vector_results_count)
    
    if not data or 'results' not in data or len(data['results']) == 0:
        return []
    
    # Step 2: LLM Processing & Server Extraction
    host_ports_array = []
    
    for i, result in enumerate(data['results'], 1):
        try:
            codebase_content = result['page_content']
            file_source = result['metadata']['source']
            
            # Apply text cleaning
            codebase_content = codebase_content.replace("@aexp", "@aexps")
            codebase_content = codebase_content.replace("@", "")
            codebase_content = codebase_content.replace("aimid", "")
            
            if len(codebase_content) < 4:
                continue
            
            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Step 1: Check if server information exists
            detection_prompt = "Given the provided code snippet, identify if there are server informations present showing host, port and database information? If none, reply back with 'no'. Else extract the server information. Place in a json with keys 'host', 'port', 'database name'. Reply with only the JSON. Make sure it's a valid JSON."
            
            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase_content
            }
            
            try:
                response = requests.post(url, json=payload, headers=HEADERS, timeout=300)
                
                # Handle ALL non-200 HTTP errors dynamically
                if response.status_code != 200:
                    # Log 404 errors in both places for backwards compatibility
                    if response.status_code == 404:
                        log_404_error(system_prompt, detection_prompt, codebase_content, file_source, url, timestamp)
                    
                    # Log ANY non-200 error dynamically
                    log_error(f"llm_api_{response.status_code}", response.status_code, response.text,
                              system_prompt, detection_prompt, codebase_content, file_source, url, timestamp)
                    continue
                
                # Parse response
                try:
                    response_json = response.json()
                except json.JSONDecodeError as e:
                    log_error("invalid_json_response", 200, response.text, system_prompt, detection_prompt,
                              codebase_content, file_source, url, timestamp, {"json_error": str(e)})
                    continue
                
                status_code = response_json.get('status_code', response.status_code)
                
                # Handle internal status codes (like 400 from LLM API) dynamically
                if status_code != 200:
                    # Log internal LLM API errors for ANY non-200 status code
                    if status_code == 404:
                        log_404_error(system_prompt, detection_prompt, codebase_content, file_source, url, timestamp)
                    
                    log_error(f"llm_internal_{status_code}", status_code, response_json.get('output', 'Unknown error'),
                              system_prompt, detection_prompt, codebase_content, file_source, url, timestamp)
                    continue
                
                # Process successful response
                output = response_json.get('output', '')
                
                # Check if no server information found
                if 'no' in output.lower() or 'No' in output:
                    continue
                
                # Try to parse the JSON extraction
                try:
                    json_document = json.loads(output)
                except json.JSONDecodeError:
                    continue
                
                # Step 2: Validate the extracted server information
                validation_prompt = "Is this valid database server information? If yes, reply with 'yes'. If no, reply with 'no'."
                
                validation_payload = {
                    "system_prompt": system_prompt,
                    "user_prompt": validation_prompt,
                    "codebase": json.dumps(json_document)
                }
                
                try:
                    validation_response = requests.post(url, json=validation_payload, headers=HEADERS, timeout=300)
                    
                    if validation_response.status_code != 200:
                        # Log validation error for ANY non-200 status code
                        if validation_response.status_code == 404:
                            log_404_error(system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                        
                        log_error(f"validation_api_{validation_response.status_code}", validation_response.status_code, 
                                 validation_response.text, system_prompt, validation_prompt, 
                                 json.dumps(json_document), file_source, url, timestamp)
                        
                        # Accept the data even if validation fails
                        host_ports_array.append(json_document)
                        continue
                    
                    try:
                        validation_json = validation_response.json()
                        validation_output = validation_json.get('output', '')
                        
                        internal_status = validation_json.get('status_code', 200)
                        if internal_status != 200:
                            # Log internal validation errors for ANY non-200 status code
                            if internal_status == 404:
                                log_404_error(system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                            
                            log_error(f"validation_internal_{internal_status}", internal_status, validation_output,
                                     system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                            
                            host_ports_array.append(json_document)
                        elif 'yes' in validation_output.lower():
                            host_ports_array.append(json_document)
                        else:
                            host_ports_array.append(json_document)
                    
                    except json.JSONDecodeError:
                        host_ports_array.append(json_document)
                
                except Exception as validation_error:
                    host_ports_array.append(json_document)
            
            except requests.exceptions.ConnectionError as e:
                log_error("connection_error", None, str(e), system_prompt, detection_prompt,
                          codebase_content, file_source, url, timestamp)
                continue
            
            except requests.exceptions.Timeout as e:
                log_error("timeout", None, f"Request timed out: {str(e)}", system_prompt, detection_prompt,
                          codebase_content, file_source, url, timestamp)
                continue
            
            except Exception as e:
                log_error("unexpected_error", None, str(e), system_prompt, detection_prompt,
                          codebase_content, file_source, url, timestamp)
                continue
        
        except Exception as file_error:
            continue
    
    # Filter out duplicate entries
    if host_ports_array:
        unique_servers = [dict(t) for t in {tuple(d.items()) for d in host_ports_array}]
        host_ports_array = unique_servers
    
    return host_ports_array


def generate_structured_error_json():
    """Generate structured error JSON in the format: {'Errors': {status_code: [error_objects]}}"""
    structured_errors = {"Errors": {}}
    
    # Process 404 errors
    for log in st.session_state['multi_404_logs']:
        status_code = "404"
        if status_code not in structured_errors["Errors"]:
            structured_errors["Errors"][status_code] = []
        
        error_entry = {
            "system": log['system_prompt'][:100] + "..." if len(log['system_prompt']) > 100 else log['system_prompt'],
            "user": log['user_prompt'][:100] + "..." if len(log['user_prompt']) > 100 else log['user_prompt'],
            "codebase": log['file_source'],
            "error": "404_firewall_block",
            "timestamp": log['timestamp'],
            "full_codebase_length": log['full_codebase_length']
        }
        structured_errors["Errors"][status_code].append(error_entry)
    
    # Process other errors
    for log in st.session_state['multi_error_logs']:
        status_code = str(log['status_code']) if log['status_code'] else "unknown"
        if status_code not in structured_errors["Errors"]:
            structured_errors["Errors"][status_code] = []
        
        error_entry = {
            "system": log['system_prompt'][:100] + "..." if len(log['system_prompt']) > 100 else log['system_prompt'],
            "user": log['user_prompt'][:100] + "..." if len(log['user_prompt']) > 100 else log['user_prompt'],
            "codebase": log['file_source'],
            "error": log['error_type'],
            "timestamp": log['timestamp'],
            "status_code": log['status_code'],
            "error_severity": log.get('error_severity', 'UNKNOWN'),
            "response_text": log.get('response_text_truncated', log.get('response_text', '')),
            "full_response_text": log.get('response_text', ''),
            "full_codebase_length": log['full_codebase_length'],
            "payload_size": log.get('payload_size', 0),
            "url_attempted": log.get('url_attempted', ''),
            "additional_info": log.get('additional_info', {})
        }
        structured_errors["Errors"][status_code].append(error_entry)
    
    return structured_errors


def main():
    st.set_page_config(
        page_title="Multi-Codebase Server Extraction",
        page_icon="🗂️",
        layout="wide"
    )

    st.title("🗂️ Multi-Codebase Server Extraction")
    st.markdown("**Process multiple codebases with comma-separated input - streamlined output**")

    # Main extraction form
    with st.form("multi_codebase_extraction_form"):
        col1, col2 = st.columns(2)

        with col1:
            codebases_input = st.text_area(
                "🗂️ Codebases (comma-separated):",
                placeholder="project1, project2, project3",
                help="Enter multiple codebase names separated by commas",
                height=100
            )

            vector_query = st.text_input(
                "🔍 Vector Search Query:",
                value="server host port configuration",
                help="Query used to find relevant files in vector database"
            )

        with col2:
            vector_results_count = st.number_input(
                '📊 Max Results Per Codebase:',
                value=10,
                min_value=1,
                max_value=50,
                help="Maximum number of files to process from vector search per codebase"
            )

            system_prompt = st.text_area(
                "🤖 System Prompt:",
                value=SERVER_SYSTEM_PROMPT,
                height=100,
                help="Instructions for the AI about its role and context"
            )

        submit_button = st.form_submit_button('🚀 Start Multi-Codebase Extraction', use_container_width=True)

    # Process form submission
    if submit_button:
        if not codebases_input.strip():
            st.error("❌ Please enter at least one codebase name")
        elif not vector_query.strip():
            st.error("❌ Please enter a vector search query")
        elif not system_prompt.strip():
            st.error("❌ System prompt is required")
        else:
            # Clear previous error logs
            st.session_state['multi_404_logs'] = []
            st.session_state['multi_error_logs'] = []
            
            # Parse codebases
            codebases = [cb.strip() for cb in codebases_input.split(',') if cb.strip()]
            
            st.header("🔄 Processing Results")
            st.info(f"Processing {len(codebases)} codebases: {', '.join(codebases)}")
            
            all_server_information = {}
            
            # Process each codebase
            progress_bar = st.progress(0)
            for idx, codebase in enumerate(codebases):
                with st.spinner(f"Processing {codebase}..."):
                    server_info = process_single_codebase(codebase, system_prompt, vector_query, vector_results_count)
                    all_server_information[codebase] = server_info
                
                progress_bar.progress((idx + 1) / len(codebases))
            
            st.success(f"✅ Processing completed for all {len(codebases)} codebases!")
            
            # Generate results
            total_servers = sum(len(servers) for servers in all_server_information.values())
            structured_errors = generate_structured_error_json()
            
            # Complete results with errors included
            complete_results = {
                "extraction_metadata": {
                    "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "codebases_processed": codebases,
                    "vector_query": vector_query,
                    "total_codebases": len(codebases),
                    "total_servers_found": total_servers,
                    "total_errors": len(st.session_state['multi_404_logs']) + len(st.session_state['multi_error_logs'])
                },
                "results": {
                    "Server Information": all_server_information
                },
                "errors": structured_errors
            }
            
            # Clean server info only
            clean_results = {
                "Server Information": all_server_information
            }
            
            # Display JSON Results
            st.header("📊 Results")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.download_button(
                    label="📥 Download Complete Results JSON",
                    data=json.dumps(complete_results, indent=2),
                    file_name=f"multi_server_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            with col2:
                st.download_button(
                    label="📥 Download Server Info Only (Clean)",
                    data=json.dumps(clean_results, indent=2),
                    file_name=f"multi_server_info_clean_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            with col3:
                if structured_errors["Errors"]:
                    st.download_button(
                        label="📥 Download All Errors JSON",
                        data=json.dumps(structured_errors, indent=2),
                        file_name=f"multi_extraction_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                else:
                    st.info("No errors to download")
            
            # Summary
            st.subheader("📈 Summary")
            for codebase, servers in all_server_information.items():
                st.write(f"**{codebase}:** {len(servers)} servers found")
            
            st.write(f"**Total Servers:** {total_servers}")
            st.write(f"**Total Errors:** {len(st.session_state['multi_404_logs']) + len(st.session_state['multi_error_logs'])}")


if __name__ == "__main__":
    main()