import streamlit as st
import requests
import json
import os
from datetime import datetime

# Constants (embedded to keep single file)
SERVER_SYSTEM_PROMPT = "You are an expert at analyzing code for server configurations, host information, and network settings."
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}

# Initialize session state for error tracking
if '404_logs' not in st.session_state:
    st.session_state['404_logs'] = []
if 'error_logs' not in st.session_state:
    st.session_state['error_logs'] = []


def vector_search(codebase, similarity_search_query, vector_results_count):
    """
    Actual vector search implementation using embeddings database
    """
    url = "http://localhost:5000/vector-search"
    payload = {
        "codebase": codebase,
        "query": similarity_search_query,
        "vector_results_count": vector_results_count
    }

    try:
        with st.spinner(f"🔍 Searching embeddings for '{similarity_search_query}'..."):
            response = requests.post(url, json=payload, headers=HEADERS, timeout=60)

        if response.status_code != 200:
            st.error(f"❌ **Vector Search Error:** HTTP {response.status_code}")
            st.error(f"Response: {response.text}")
            
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
            st.error("❌ **Invalid response format from vector search**")
            return {"results": []}

        if not data['results']:
            st.warning("⚠️ **No results found** - check if embeddings exist for this codebase")
            return {"results": []}

        st.success(f"✅ **Found {len(data['results'])} code snippets** from embeddings")
        return data

    except requests.exceptions.ConnectionError as e:
        st.error("❌ **Connection Error:** Could not reach vector search service at http://localhost:5000")
        st.info("💡 Make sure the vector search service is running")
        
        # Log connection error
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_connection_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except requests.exceptions.Timeout as e:
        st.error("❌ **Timeout Error:** Vector search took too long (>60 seconds)")
        
        # Log timeout error
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_timeout_error", None, f"Timeout after 60 seconds: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except json.JSONDecodeError as e:
        st.error(f"❌ **JSON Parse Error:** {str(e)}")
        st.error(f"Raw response: {response.text[:500]}...")
        
        # Log JSON parse error
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_json_parse_error", None, f"JSON decode error: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {codebase}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except Exception as e:
        st.error(f"❌ **Vector Search Failed:** {str(e)}")
        
        # Log general vector search error
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
    st.session_state['404_logs'].append(log_entry)


def log_error(error_type, status_code, response_text, system_prompt, user_prompt, codebase, file_source, url, timestamp,
              additional_info=None):
    """Log any non-200 response with complete debugging metadata - fully dynamic"""
    
    log_entry = {
        "timestamp": timestamp,
        "error_type": error_type,
        "status_code": status_code,
        "response_text": str(response_text),  # Keep full response text for analysis
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
    st.session_state['error_logs'].append(log_entry)


def safechain_server_extraction(data, system_prompt, vector_query):
    """
    Enhanced server extraction following LLMUtil pattern with proper validation flow
    """
    st.subheader("🔍 Vector Search Results")
    st.info(f"**Vector Search Query Used:** `{vector_query}`")
    st.info(f"**Files Found:** {len(data['results'])}")

    # Display summary of retrieved files
    if data['results']:
        st.write("**📁 Retrieved Files:**")
        file_summary = {}
        for result in data['results']:
            file_path = result['metadata']['source']
            content_length = len(result['page_content'])
            if file_path in file_summary:
                file_summary[file_path]['count'] += 1
                file_summary[file_path]['total_chars'] += content_length
            else:
                file_summary[file_path] = {'count': 1, 'total_chars': content_length}

        for file_path, info in file_summary.items():
            st.write(f"• `{file_path}` - {info['count']} snippet(s), {info['total_chars']} characters total")

        # Show similarity scores if available
        if 'score' in data['results'][0].get('metadata', {}):
            st.write("**🎯 Similarity Scores:**")
            scores = [float(result['metadata'].get('score', 0)) for result in data['results']]
            st.write(f"• Best match: {max(scores):.3f}")
            st.write(f"• Average: {sum(scores) / len(scores):.3f}")
            st.write(f"• Lowest: {min(scores):.3f}")

    host_ports_array = []

    for i, result in enumerate(data['results'], 1):
        try:
            # Display similarity score if available
            similarity_info = ""
            if 'score' in result.get('metadata', {}):
                score = float(result['metadata']['score'])
                similarity_info = f" (Similarity: {score:.3f})"

            st.markdown(
                f"### 📄 Processing Snippet {i}/{len(data['results'])}: `{result['metadata']['source']}`{similarity_info}")

            codebase = result['page_content']
            file_source = result['metadata']['source']

            # Show embedding metadata if available
            metadata = result.get('metadata', {})
            if metadata:
                metadata_info = []
                if 'score' in metadata:
                    metadata_info.append(f"Similarity: {float(metadata['score']):.3f}")
                if 'chunk_id' in metadata:
                    metadata_info.append(f"Chunk: {metadata['chunk_id']}")
                if 'line_start' in metadata and 'line_end' in metadata:
                    metadata_info.append(f"Lines: {metadata['line_start']}-{metadata['line_end']}")

                if metadata_info:
                    st.write(f"**🔍 Embedding Info:** {' | '.join(metadata_info)}")

            # Apply text cleaning for server extraction (consistent with LLMUtil)
            original_length = len(codebase)
            codebase = codebase.replace("@aexp", "@aexps")
            codebase = codebase.replace("@", "")
            codebase = codebase.replace("aimid", "")

            st.write(f"**📊 Content Length:** {original_length} → {len(codebase)} characters (after cleaning)")

            # Display codebase content from embeddings
            try:
                with st.expander(f"📖 Code Snippet from Embeddings - {file_source}", expanded=False):
                    _, extension = os.path.splitext(file_source)
                    st.code(codebase, language=extension[1:] if extension else "text")

                    # Show raw embedding data
                    if st.checkbox(f"Show raw embedding data", key=f"raw_embed_{i}"):
                        st.json(result)
            except Exception as display_error:
                st.write(f"**Source:** {file_source} ({len(codebase)} chars)")
                st.code(codebase[:500] + "..." if len(codebase) > 500 else codebase)

            if len(codebase) < 4:
                st.error("⚠️ Codebase content is too short to process.")
                continue

            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Step 1: Check if server information exists (following LLMUtil pattern)
            st.write("**🔍 Step 1: Detecting Server Information**")
            detection_prompt = "Given the provided code snippet, identify if there are server informations present showing host, port and database information? If none, reply back with 'no'. Else extract the server information. Place in a json with keys 'host', 'port', 'database name'. Reply with only the JSON. Make sure it's a valid JSON."

            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase
            }

            with st.spinner(f"🔄 Detecting server info in {file_source}..."):
                try:
                    response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

                    # Handle HTTP errors
                    if response.status_code == 404:
                        st.error("❌ **404 Error: Request blocked by firewall**")
                        log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        log_error("404_firewall_block", 404, response.text, system_prompt, detection_prompt,
                                  codebase, file_source, url, timestamp)
                        continue

                    elif response.status_code != 200:
                        st.error(f"❌ **HTTP {response.status_code} Error:** {response.text}")
                        log_error(f"http_{response.status_code}", response.status_code, response.text,
                                  system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    # Parse response
                    try:
                        response_json = response.json()
                    except json.JSONDecodeError as e:
                        st.error(f"❌ **Invalid JSON Response:** Could not parse response")
                        log_error("invalid_json_response", 200, response.text, system_prompt, detection_prompt,
                                  codebase, file_source, url, timestamp, {"json_error": str(e)})
                        continue

                    status_code = response_json.get('status_code', response.status_code)

                    # Handle internal status codes (like 400 from LLM API) dynamically
                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        st.info("🔄 **Continuing with next file...**")
                        
                        # Log internal LLM API errors for ANY non-200 status code
                        if status_code == 404:
                            log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        
                        log_error(f"llm_internal_{status_code}", status_code, response_json.get('output', 'Unknown error'),
                                  system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    # Process successful response
                    output = response_json.get('output', '')

                    # Check if no server information found (following LLMUtil pattern)
                    if 'no' in output.lower() or 'No' in output:
                        st.warning("⚠️ **No server information found in this file**")
                        continue

                    # Display raw output
                    with st.expander("🔍 Raw Detection Response", expanded=False):
                        try:
                            st.text_area("Raw Output:", output, height=100, key=f"raw_detect_{file_source}_{i}",
                                         disabled=True)
                        except Exception as e:
                            st.write(f"Raw Output: {output}")

                    # Try to parse the JSON extraction
                    try:
                        json_document = json.loads(output)
                        st.success("✅ **Server information detected!**")
                        try:
                            st.json(json_document)
                        except Exception as e:
                            st.write("Detected JSON:")
                            st.code(json.dumps(json_document, indent=2), language="json")
                    except json.JSONDecodeError:
                        st.error(f"❌ **Invalid JSON from LLM:** {output}")
                        continue

                    # Step 2: Validate the extracted server information (following LLMUtil pattern)
                    st.write("**✅ Step 2: Validating Server Information**")
                    validation_prompt = "Is this valid database server information? If yes, reply with 'yes'. If no, reply with 'no'."

                    validation_payload = {
                        "system_prompt": system_prompt,
                        "user_prompt": validation_prompt,
                        "codebase": json.dumps(json_document)  # Pass the extracted JSON as codebase
                    }

                    with st.spinner(f"🔄 Validating server info from {file_source}..."):
                        try:
                            validation_response = requests.post(url, json=validation_payload, headers=HEADERS, timeout=300)

                            if validation_response.status_code != 200:
                                st.warning(
                                    f"⚠️ **Validation failed with HTTP {validation_response.status_code}** - accepting data anyway")
                                
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
                                    st.warning(f"⚠️ **Validation API {internal_status} - Filtered/Blocked:** {validation_output}")
                                    st.info("📝 **Accepting extracted data anyway since detection was successful**")
                                    
                                    # Log internal validation errors for ANY non-200 status code
                                    if internal_status == 404:
                                        log_404_error(system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                                    
                                    log_error(f"validation_internal_{internal_status}", internal_status, validation_output,
                                             system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                                    
                                    host_ports_array.append(json_document)
                                elif 'yes' in validation_output.lower():
                                    st.success("🎯 **Server information validated successfully!**")
                                    host_ports_array.append(json_document)
                                else:
                                    st.warning("⚠️ **Validation failed but accepting data anyway**")
                                    st.write(f"**Validation response:** {validation_output}")
                                    host_ports_array.append(json_document)

                            except json.JSONDecodeError:
                                st.warning("⚠️ **Validation response unparseable** - accepting data anyway")
                                host_ports_array.append(json_document)

                        except Exception as validation_error:
                            st.warning(f"⚠️ **Validation request failed:** {str(validation_error)}")
                            st.info("📝 **Accepting extracted data anyway since detection was successful**")
                            host_ports_array.append(json_document)

                except requests.exceptions.ConnectionError as e:
                    st.error(f"❌ **Connection Error:** Could not reach LLM API")
                    log_error("connection_error", None, str(e), system_prompt, detection_prompt,
                              codebase, file_source, url, timestamp)
                    continue

                except requests.exceptions.Timeout as e:
                    st.warning(f"⏰ **Timeout Warning:** Request timed out after 300 seconds - continuing with next file")
                    log_error("timeout", None, f"Request timed out: {str(e)}", system_prompt, detection_prompt,
                              codebase, file_source, url, timestamp)
                    continue

                except Exception as e:
                    st.error(f"❌ **Unexpected Error:** {str(e)} - continuing with next file")
                    log_error("unexpected_error", None, str(e), system_prompt, detection_prompt,
                              codebase, file_source, url, timestamp)
                    continue

        except Exception as file_error:
            st.error(f"❌ **Critical Error processing file {i}**: {str(file_error)}")
            st.info("🔄 **Continuing with next file...**")
            continue

    st.markdown("---")

    # Filter out duplicate entries (following LLMUtil pattern)
    if host_ports_array:
        st.info(f"🔄 **Filtering duplicates from {len(host_ports_array)} entries...**")
        unique_servers = [dict(t) for t in {tuple(d.items()) for d in host_ports_array}]
        if len(unique_servers) < len(host_ports_array):
            st.info(f"🧹 **Removed {len(host_ports_array) - len(unique_servers)} duplicate entries**")
        host_ports_array = unique_servers

    return host_ports_array


def generate_structured_error_json():
    """Generate structured error JSON in the format: {'Errors': {status_code: [error_objects]}}"""
    structured_errors = {"Errors": {}}
    
    # Process 404 errors
    for log in st.session_state['404_logs']:
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
    for log in st.session_state['error_logs']:
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


def display_error_logs():
    """Display comprehensive error logs with debugging metadata"""
    total_404s = len(st.session_state['404_logs'])
    total_errors = len(st.session_state['error_logs'])

    if total_404s == 0 and total_errors == 0:
        st.info("🎉 No errors logged yet!")
        return

    # Count errors by severity
    high_severity = sum(1 for log in st.session_state['error_logs'] if log.get('error_severity') == 'HIGH')
    medium_severity = sum(1 for log in st.session_state['error_logs'] if log.get('error_severity') == 'MEDIUM')
    low_severity = sum(1 for log in st.session_state['error_logs'] if log.get('error_severity') == 'LOW')
    
    # Summary metrics
    if total_404s > 0:
        st.error(f"🚨 {total_404s} 404 Errors")
    if high_severity > 0:
        st.error(f"🔥 {high_severity} High Severity Errors (5xx)")
    if medium_severity > 0:
        st.warning(f"⚠️ {medium_severity} Medium Severity Errors (4xx)")
    if low_severity > 0:
        st.info(f"ℹ️ {low_severity} Low Severity Errors")
    if total_errors > 0:
        st.info(f"📊 Total Errors: {total_errors}")

    # Download structured errors JSON
    structured_errors = generate_structured_error_json()
    structured_json = json.dumps(structured_errors, indent=2)
    st.download_button(
        label="📥 Download Structured Errors JSON",
        data=structured_json,
        file_name=f"structured_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        help="Download errors grouped by status code in structured format"
    )

    # Download all logs as JSON (original format)
    all_logs = {
        "404_errors": st.session_state['404_logs'],
        "other_errors": st.session_state['error_logs'],
        "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    logs_json = json.dumps(all_logs, indent=2)
    st.download_button(
        label="📥 Download All Error Logs (Detailed)",
        data=logs_json,
        file_name=f"detailed_error_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        help="Download complete error logs with full debugging metadata"
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
                    st.code(
                        log['system_prompt'][:100] + "..." if len(log['system_prompt']) > 100 else log['system_prompt'])

                st.write("**📝 Codebase Snippet:**")
                st.code(log['codebase_snippet'], language="text")

    # Display other error logs
    if total_errors > 0:
        st.subheader("⚠️ All Other Errors")
        for i, log in enumerate(reversed(st.session_state['error_logs'])):
            # Determine error icon and priority dynamically
            severity = log.get('error_severity', 'UNKNOWN')
            if severity == 'HIGH':
                error_color = "🔥"
                error_priority = "HIGH SEVERITY"
            elif severity == 'MEDIUM':
                error_color = "⚠️"
                error_priority = "MEDIUM SEVERITY"
            elif severity == 'LOW':
                error_color = "ℹ️"
                error_priority = "LOW SEVERITY"
            else:
                error_color = "❓"
                error_priority = "UNKNOWN SEVERITY"
                
            title = f"{error_color} [{severity}] {log['error_type']} #{total_errors - i} - {log['timestamp']} - {log['file_source']}"
                
            with st.expander(title, expanded=(i == 0 or severity == 'HIGH')):
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

                    st.write("**🎯 Error Severity:**")
                    severity_color = "🔥" if log.get('error_severity') == 'HIGH' else "⚠️" if log.get('error_severity') == 'MEDIUM' else "ℹ️"
                    st.code(f"{severity_color} {log.get('error_severity', 'UNKNOWN')}")

                    st.write("**📏 Payload Size:**")
                    st.code(f"{log.get('payload_size', 0)} bytes")

                    st.write("**📏 Codebase Length:**")
                    st.code(f"{log['full_codebase_length']} characters")

                st.write("**🔍 Response Text:**")
                st.code(log.get('response_text_truncated', log.get('response_text', '')))
                
                # Show full response if different from truncated
                if log.get('response_text') and len(log.get('response_text', '')) > 1000:
                    with st.expander("📄 Full Response Text", expanded=False):
                        st.code(log.get('response_text', ''), language="text")

                if log['additional_info']:
                    st.write("**🔧 Additional Debug Info:**")
                    st.json(log['additional_info'])

                try:
                    with st.expander("Full Context", expanded=False):
                        st.write("**🤖 System Prompt:**")
                        try:
                            st.text_area("", log['system_prompt'], height=100, disabled=True,
                                         key=f"sys_err_{i}_{log['timestamp']}")
                        except:
                            st.code(log['system_prompt'])

                        st.write("**👤 User Prompt:**")
                        try:
                            st.text_area("", log['user_prompt'], height=100, disabled=True,
                                         key=f"user_err_{i}_{log['timestamp']}")
                        except:
                            st.code(log['user_prompt'])

                        st.write("**📝 Codebase Snippet:**")
                        st.code(log['codebase_snippet'], language="text")
                except Exception as display_error:
                    st.write("**Context Details:**")
                    st.write(f"System Prompt: {log['system_prompt'][:200]}...")
                    st.write(f"User Prompt: {log['user_prompt'][:200]}...")
                    st.write(f"Codebase: {log['codebase_snippet'][:200]}...")

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

        st.info(
            "📝 **Note:** User prompts are handled automatically by the extraction flow following the LLMUtil pattern")

        with st.expander("🔍 View Automatic Prompts Used", expanded=False):
            st.text_area(
                "Detection Prompt:",
                "Given the provided code snippet, identify if there are server informations present showing host, port and database information? If none, reply back with 'no'. Else extract the server information. Place in a json with keys 'host', 'port', 'database name'. Reply with only the JSON. Make sure it's a valid JSON.",
                height=100,
                disabled=True
            )
            st.text_area(
                "Validation Prompt:",
                "Is this valid database server information? If yes, reply with 'yes'. If no, reply with 'no'.",
                height=60,
                disabled=True
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
        elif not system_prompt.strip():
            st.error("❌ System prompt is required")
        else:
            try:
                st.markdown("---")
                st.header("🔄 Processing Flow")

                # Step 1: Vector Search
                st.subheader("📊 Step 1: Vector Database Search")
                search_target = codebase + "-external-files"  # Always search external files

                st.info(f"**🗂️ Target Database:** `{search_target}`")
                st.info(f"**🔍 Search Query:** `{vector_query}`")
                st.info(f"**📊 Max Results:** {vector_results_count}")
                st.info(f"**🌐 Vector Service:** `http://localhost:5000/vector-search`")

                # Show what we're searching for
                with st.expander("ℹ️ Vector Search Details", expanded=False):
                    st.write("**How it works:**")
                    st.write("1. 🔍 Query embeddings database with similarity search")
                    st.write("2. 📄 Retrieve most relevant code snippets based on semantic similarity")
                    st.write("3. 📊 Rank results by similarity score")
                    st.write("4. 🎯 Return top matches for LLM processing")

                data = vector_search(search_target, vector_query, vector_results_count)

                if not data or 'results' not in data or len(data['results']) == 0:
                    st.warning(f"❌ No content found for query: '{vector_query}' in database: '{search_target}'")
                    st.info("💡 Try adjusting your search query or check if the codebase embeddings exist")
                else:
                    # Step 2: LLM Processing
                    st.subheader("🤖 Step 2: LLM Processing & Server Extraction")

                    server_information = safechain_server_extraction(
                        data, system_prompt, vector_query
                    )

                    # Step 3: Final Results
                    st.header("🎯 Final Results")
                    if server_information:
                        st.success(
                            f"✅ **Extraction completed successfully!** Found {len(server_information)} server entries")

                        # Format output in the requested structure
                        final_output = {
                            "Server Information": server_information
                        }

                        st.subheader("📊 Extracted Server Information")
                        st.json(final_output)

                        # Generate structured errors for inclusion in results
                        structured_errors = generate_structured_error_json()
                        
                        # Detailed summary with errors included
                        summary = {
                            "extraction_metadata": {
                                "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "codebase": search_target,
                                "vector_query": vector_query,
                                "total_files_processed": len(data['results']),
                                "total_servers_found": len(server_information),
                                "total_errors": len(st.session_state['404_logs']) + len(st.session_state['error_logs'])
                            },
                            "results": final_output,
                            "errors": structured_errors
                        }

                        # Download results
                        results_json = json.dumps(summary, indent=2)
                        st.download_button(
                            label="📥 Download Complete Results as JSON",
                            data=results_json,
                            file_name=f"server_extraction_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )

                        # Download just the server information in the clean format
                        clean_results_json = json.dumps(final_output, indent=2)
                        st.download_button(
                            label="📥 Download Server Info Only (Clean Format)",
                            data=clean_results_json,
                            file_name=f"server_info_clean_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                        
                        # Download structured errors JSON
                        if structured_errors["Errors"]:
                            structured_json = json.dumps(structured_errors, indent=2)
                            st.download_button(
                                label="📥 Download All Errors JSON (404s & Failures)",
                                data=structured_json,
                                file_name=f"extraction_errors_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json",
                                help="Download all non-200 errors grouped by status code for debugging"
                            )

                        st.balloons()
                    else:
                        st.warning("⚠️ No server information could be extracted from the codebase")
                        st.info("💡 Try adjusting your prompts or search query")
                        
                        # Even if no servers found, still offer error download if there are errors
                        structured_errors = generate_structured_error_json()
                        if structured_errors["Errors"]:
                            st.subheader("🚨 Error Analysis")
                            st.warning(f"Found {len(st.session_state['404_logs']) + len(st.session_state['error_logs'])} errors during processing")
                            
                            structured_json = json.dumps(structured_errors, indent=2)
                            st.download_button(
                                label="📥 Download All Errors JSON (404s & Failures)",
                                data=structured_json,
                                file_name=f"extraction_errors_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json",
                                help="Download all non-200 errors grouped by status code for debugging"
                            )

            except Exception as e:
                st.error(f"❌ **Extraction failed:** {str(e)}")
                st.error("Please check if the codebase embeddings exist and the backend is running")


if __name__ == "__main__":
    main()