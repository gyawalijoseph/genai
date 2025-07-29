import streamlit as st
import requests
import json
import os
from datetime import datetime

# Dynamic configuration - can be modified for any codebase
DEFAULT_DATABASE_SYSTEM_PROMPT = "You are an expert at analyzing code for database configurations, connections, queries, and data models."
DEFAULT_VECTOR_QUERY = "database sql connection query schema table model"
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}

# Initialize session state for error tracking
if 'db_404_logs' not in st.session_state:
    st.session_state['db_404_logs'] = []
if 'db_error_logs' not in st.session_state:
    st.session_state['db_error_logs'] = []


def vector_search(codebase, similarity_search_query, vector_results_count, search_suffix="-external-files"):
    """
    Dynamic vector search implementation that can work with any codebase
    """
    search_target = f"{codebase}{search_suffix}"
    url = "http://localhost:5000/vector-search"
    payload = {
        "codebase": search_target,
        "query": similarity_search_query,
        "vector_results_count": vector_results_count
    }

    try:
        with st.spinner(f"🔍 Searching '{search_target}' for '{similarity_search_query}'..."):
            response = requests.post(url, json=payload, headers=HEADERS, timeout=60)

        if response.status_code != 200:
            st.error(f"❌ **Vector Search Error:** HTTP {response.status_code}")
            st.error(f"Response: {response.text}")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if response.status_code == 404:
                log_404_error("Vector search system", f"Query: {similarity_search_query}", 
                             f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
            
            log_error(f"vector_search_{response.status_code}", response.status_code, response.text, 
                     "Vector search system", f"Query: {similarity_search_query}", 
                     f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
            return {"results": []}

        data = response.json()

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
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_connection_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except requests.exceptions.Timeout as e:
        st.error("❌ **Timeout Error:** Vector search took too long (>60 seconds)")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_timeout_error", None, f"Timeout after 60 seconds: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except json.JSONDecodeError as e:
        st.error(f"❌ **JSON Parse Error:** {str(e)}")
        st.error(f"Raw response: {response.text[:500]}...")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_json_parse_error", None, f"JSON decode error: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": []}

    except Exception as e:
        st.error(f"❌ **Vector Search Failed:** {str(e)}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_general_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
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
    st.session_state['db_404_logs'].append(log_entry)


def log_error(error_type, status_code, response_text, system_prompt, user_prompt, codebase, file_source, url, timestamp,
              additional_info=None):
    """Log any non-200 response with complete debugging metadata"""
    
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
    st.session_state['db_error_logs'].append(log_entry)


def dynamic_database_extraction(data, system_prompt, vector_query, extraction_config):
    """
    Dynamic database extraction that adapts to different codebase types
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

    database_info_array = []

    for i, result in enumerate(data['results'], 1):
        try:
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

            # Apply configurable text cleaning
            original_length = len(codebase)
            for cleanup_rule in extraction_config.get('text_cleanup_rules', []):
                codebase = codebase.replace(cleanup_rule['find'], cleanup_rule['replace'])

            st.write(f"**📊 Content Length:** {original_length} → {len(codebase)} characters (after cleaning)")

            # Display codebase content from embeddings
            try:
                with st.expander(f"📖 Code Snippet from Embeddings - {file_source}", expanded=False):
                    _, extension = os.path.splitext(file_source)
                    st.code(codebase, language=extension[1:] if extension else "text")

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

            # Step 1: Detection with configurable prompt
            st.write("**🔍 Step 1: Detecting Database Information**")
            detection_prompt = extraction_config.get('detection_prompt', 
                "Given the provided code snippet, identify if there are database-related configurations, connections, or queries present? If none, reply back with 'no'. Else extract the database information. Place in a json with keys for any database-related information found. Reply with only the JSON. Make sure it's a valid JSON.")

            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase
            }

            with st.spinner(f"🔄 Detecting database info in {file_source}..."):
                try:
                    response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

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

                    try:
                        response_json = response.json()
                    except json.JSONDecodeError as e:
                        st.error(f"❌ **Invalid JSON Response:** Could not parse response")
                        log_error("invalid_json_response", 200, response.text, system_prompt, detection_prompt,
                                  codebase, file_source, url, timestamp, {"json_error": str(e)})
                        continue

                    status_code = response_json.get('status_code', response.status_code)

                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        st.info("🔄 **Continuing with next file...**")
                        
                        if status_code == 404:
                            log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        
                        log_error(f"llm_internal_{status_code}", status_code, response_json.get('output', 'Unknown error'),
                                  system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    output = response_json.get('output', '')

                    # Check if no database information found
                    if 'no' in output.lower() or 'No' in output:
                        st.warning("⚠️ **No database information found in this file**")
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
                        st.success("✅ **Database information detected!**")
                        try:
                            st.json(json_document)
                        except Exception as e:
                            st.write("Detected JSON:")
                            st.code(json.dumps(json_document, indent=2), language="json")
                    except json.JSONDecodeError:
                        st.error(f"❌ **Invalid JSON from LLM:** {output}")
                        continue

                    # Step 2: Validation with configurable prompt
                    st.write("**✅ Step 2: Validating Database Information**")
                    validation_prompt = extraction_config.get('validation_prompt',
                        "Is this valid database-related information? If yes, reply with 'yes'. If no, reply with 'no'.")

                    validation_payload = {
                        "system_prompt": system_prompt,
                        "user_prompt": validation_prompt,
                        "codebase": json.dumps(json_document)
                    }

                    with st.spinner(f"🔄 Validating database info from {file_source}..."):
                        try:
                            validation_response = requests.post(url, json=validation_payload, headers=HEADERS, timeout=300)

                            if validation_response.status_code != 200:
                                st.warning(
                                    f"⚠️ **Validation failed with HTTP {validation_response.status_code}** - accepting data anyway")
                                
                                if validation_response.status_code == 404:
                                    log_404_error(system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                                
                                log_error(f"validation_api_{validation_response.status_code}", validation_response.status_code, 
                                         validation_response.text, system_prompt, validation_prompt, 
                                         json.dumps(json_document), file_source, url, timestamp)
                                
                                database_info_array.append(json_document)
                                continue

                            try:
                                validation_json = validation_response.json()
                                validation_output = validation_json.get('output', '')

                                internal_status = validation_json.get('status_code', 200)
                                if internal_status != 200:
                                    st.warning(f"⚠️ **Validation API {internal_status} - Filtered/Blocked:** {validation_output}")
                                    st.info("📝 **Accepting extracted data anyway since detection was successful**")
                                    
                                    if internal_status == 404:
                                        log_404_error(system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                                    
                                    log_error(f"validation_internal_{internal_status}", internal_status, validation_output,
                                             system_prompt, validation_prompt, json.dumps(json_document), file_source, url, timestamp)
                                    
                                    database_info_array.append(json_document)
                                elif 'yes' in validation_output.lower():
                                    st.success("🎯 **Database information validated successfully!**")
                                    database_info_array.append(json_document)
                                else:
                                    st.warning("⚠️ **Validation failed but accepting data anyway**")
                                    st.write(f"**Validation response:** {validation_output}")
                                    database_info_array.append(json_document)

                            except json.JSONDecodeError:
                                st.warning("⚠️ **Validation response unparseable** - accepting data anyway")
                                database_info_array.append(json_document)

                        except Exception as validation_error:
                            st.warning(f"⚠️ **Validation request failed:** {str(validation_error)}")
                            st.info("📝 **Accepting extracted data anyway since detection was successful**")
                            database_info_array.append(json_document)

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

    # Filter out duplicate entries
    if database_info_array:
        st.info(f"🔄 **Filtering duplicates from {len(database_info_array)} entries...**")
        valid_dicts = [d for d in database_info_array if isinstance(d, dict)]
        if len(valid_dicts) < len(database_info_array):
            st.warning(f"⚠️ **Filtered out {len(database_info_array) - len(valid_dicts)} invalid entries**")
        
        if valid_dicts:
            unique_databases = [dict(t) for t in {tuple(d.items()) for d in valid_dicts}]
            if len(unique_databases) < len(valid_dicts):
                st.info(f"🧹 **Removed {len(valid_dicts) - len(unique_databases)} duplicate entries**")
            database_info_array = unique_databases
        else:
            database_info_array = []

    return database_info_array


def generate_structured_error_json():
    """Generate structured error JSON"""
    structured_errors = {"Errors": {}}
    
    # Process 404 errors
    for log in st.session_state['db_404_logs']:
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
    for log in st.session_state['db_error_logs']:
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
    """Display comprehensive error logs"""
    total_404s = len(st.session_state['db_404_logs'])
    total_errors = len(st.session_state['db_error_logs'])

    if total_404s == 0 and total_errors == 0:
        st.info("🎉 No errors logged yet!")
        return

    # Count errors by severity
    high_severity = sum(1 for log in st.session_state['db_error_logs'] if log.get('error_severity') == 'HIGH')
    medium_severity = sum(1 for log in st.session_state['db_error_logs'] if log.get('error_severity') == 'MEDIUM')
    low_severity = sum(1 for log in st.session_state['db_error_logs'] if log.get('error_severity') == 'LOW')
    
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
        file_name=f"database_extraction_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        help="Download errors grouped by status code in structured format"
    )

    # Clear logs buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear 404 Logs", type="secondary", key="clear_404"):
            st.session_state['db_404_logs'] = []
            st.success("404 logs cleared!")
            st.rerun()

    with col2:
        if st.button("🗑️ Clear All Error Logs", type="secondary", key="clear_all"):
            st.session_state['db_404_logs'] = []
            st.session_state['db_error_logs'] = []
            st.success("All error logs cleared!")
            st.rerun()


def get_extraction_config(extraction_type):
    """Get configuration for different extraction types"""
    configs = {
        "standard": {
            "detection_prompt": "Given the provided code snippet, identify if there are database-related configurations, connections, or queries present? If none, reply back with 'no'. Else extract the database information. Place in a json with keys for database name, connection string, host, port, username, schema, table names, or any other database-related information found. Reply with only the JSON. Make sure it's a valid JSON.",
            "validation_prompt": "Is this valid database-related information? If yes, reply with 'yes'. If no, reply with 'no'.",
            "text_cleanup_rules": [
                {"find": "@aexp", "replace": "@aexps"},
                {"find": "@", "replace": ""},
                {"find": "aimid", "replace": ""}
            ]
        },
        "sql_focused": {
            "detection_prompt": "Given the provided code snippet, identify if there are SQL queries, database schemas, table definitions, or database connection configurations present? If none, reply back with 'no'. Else extract the SQL and database information. Place in a json with keys for query_type, tables_involved, database_name, connection_details, or any other SQL-related information found. Reply with only the JSON. Make sure it's a valid JSON.",
            "validation_prompt": "Is this valid SQL or database schema information? If yes, reply with 'yes'. If no, reply with 'no'.",
            "text_cleanup_rules": [
                {"find": "/*", "replace": ""},
                {"find": "*/", "replace": ""},
                {"find": "--", "replace": ""}
            ]
        },
        "config_focused": {
            "detection_prompt": "Given the provided code snippet, identify if there are database configuration files, connection strings, environment variables, or configuration settings present? If none, reply back with 'no'. Else extract the configuration information. Place in a json with keys for config_type, database_url, host, port, credentials, environment, or any other configuration-related information found. Reply with only the JSON. Make sure it's a valid JSON.",
            "validation_prompt": "Is this valid database configuration information? If yes, reply with 'yes'. If no, reply with 'no'.",
            "text_cleanup_rules": [
                {"find": "password=", "replace": "password=***"},
                {"find": "pwd=", "replace": "pwd=***"},
                {"find": "secret=", "replace": "secret=***"}
            ]
        }
    }
    return configs.get(extraction_type, configs["standard"])


def main():
    st.set_page_config(
        page_title="Database Information Extraction",
        page_icon="🗄️",
        layout="wide"
    )

    st.title("🗄️ Database Information Extraction")
    st.markdown("**Dynamic database information extraction that adapts to any codebase**")

    # Sidebar for error tracking
    with st.sidebar:
        st.header("🚨 Error Tracking & Debug")
        total_404s = len(st.session_state['db_404_logs'])
        total_errors = len(st.session_state['db_error_logs'])

        if total_404s > 0 or total_errors > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("404 Errors", total_404s)
            with col2:
                st.metric("Other Errors", total_errors)

        display_error_logs()

    # Main extraction form
    with st.form("database_extraction_form"):
        col1, col2 = st.columns(2)

        with col1:
            codebase = st.text_input(
                "🗂️ Codebase Name:",
                placeholder="my-project",
                help="Name of the codebase to search for database information"
            )

            extraction_type = st.selectbox(
                "🎯 Extraction Type:",
                ["standard", "sql_focused", "config_focused"],
                help="Choose the type of database extraction to perform"
            )

            vector_query = st.text_input(
                "🔍 Vector Search Query:",
                value=DEFAULT_VECTOR_QUERY,
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

            search_suffix = st.text_input(
                "🔍 Search Database Suffix:",
                value="-external-files",
                help="Suffix to add to codebase name for vector search (e.g., -external-files, -internal-files)"
            )

        st.markdown("### 🤖 LLM Prompt Configuration")

        # Get extraction configuration
        extraction_config = get_extraction_config(extraction_type)

        system_prompt = st.text_area(
            "🤖 System Prompt:",
            value=DEFAULT_DATABASE_SYSTEM_PROMPT,
            height=100,
            help="Instructions for the AI about its role and context"
        )

        # Show extraction type details
        with st.expander(f"🔍 View {extraction_type.title()} Extraction Configuration", expanded=False):
            st.text_area(
                "Detection Prompt:",
                extraction_config['detection_prompt'],
                height=150,
                disabled=True
            )
            st.text_area(
                "Validation Prompt:",
                extraction_config['validation_prompt'],
                height=60,
                disabled=True
            )
            
            if extraction_config['text_cleanup_rules']:
                st.write("**Text Cleanup Rules:**")
                for rule in extraction_config['text_cleanup_rules']:
                    st.write(f"• Replace `{rule['find']}` with `{rule['replace']}`")

        submit_button = st.form_submit_button(
            '🚀 Start Database Information Extraction',
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

                st.info(f"**🗂️ Target Database:** `{codebase}{search_suffix}`")
                st.info(f"**🔍 Search Query:** `{vector_query}`")
                st.info(f"**📊 Max Results:** {vector_results_count}")
                st.info(f"**🎯 Extraction Type:** `{extraction_type}`")
                st.info(f"**🌐 Vector Service:** `http://localhost:5000/vector-search`")

                with st.expander("ℹ️ Vector Search Details", expanded=False):
                    st.write("**How it works:**")
                    st.write("1. 🔍 Query embeddings database with similarity search")
                    st.write("2. 📄 Retrieve most relevant code snippets based on semantic similarity")
                    st.write("3. 📊 Rank results by similarity score")
                    st.write("4. 🎯 Return top matches for LLM processing")

                data = vector_search(codebase, vector_query, vector_results_count, search_suffix)

                if not data or 'results' not in data or len(data['results']) == 0:
                    st.warning(f"❌ No content found for query: '{vector_query}' in database: '{codebase}{search_suffix}'")
                    st.info("💡 Try adjusting your search query or check if the codebase embeddings exist")
                else:
                    # Step 2: LLM Processing
                    st.subheader("🤖 Step 2: LLM Processing & Database Extraction")

                    database_information = dynamic_database_extraction(
                        data, system_prompt, vector_query, extraction_config
                    )

                    # Step 3: Final Results
                    st.header("🎯 Final Results")
                    if database_information:
                        st.success(
                            f"✅ **Extraction completed successfully!** Found {len(database_information)} database entries")

                        # Format output in the requested structure
                        final_output = {
                            "Database Information": database_information
                        }

                        st.subheader("📊 Extracted Database Information")
                        st.json(final_output)

                        # Generate structured errors for inclusion in results
                        structured_errors = generate_structured_error_json()
                        
                        # Detailed summary with errors included
                        summary = {
                            "extraction_metadata": {
                                "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "codebase": f"{codebase}{search_suffix}",
                                "extraction_type": extraction_type,
                                "vector_query": vector_query,
                                "total_files_processed": len(data['results']),
                                "total_databases_found": len(database_information),
                                "total_errors": len(st.session_state['db_404_logs']) + len(st.session_state['db_error_logs'])
                            },
                            "results": final_output,
                            "errors": structured_errors
                        }

                        # Download results
                        results_json = json.dumps(summary, indent=2)
                        st.download_button(
                            label="📥 Download Complete Results as JSON",
                            data=results_json,
                            file_name=f"database_extraction_{codebase}_{extraction_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )

                        # Download just the database information in clean format
                        clean_results_json = json.dumps(final_output, indent=2)
                        st.download_button(
                            label="📥 Download Database Info Only (Clean Format)",
                            data=clean_results_json,
                            file_name=f"database_info_clean_{codebase}_{extraction_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )

                        st.balloons()
                    else:
                        st.warning("⚠️ No database information could be extracted from the codebase")
                        st.info("💡 Try adjusting your prompts, search query, or extraction type")
                        
                        # Even if no databases found, still offer error download if there are errors
                        structured_errors = generate_structured_error_json()
                        if structured_errors["Errors"]:
                            st.subheader("🚨 Error Analysis")
                            st.warning(f"Found {len(st.session_state['db_404_logs']) + len(st.session_state['db_error_logs'])} errors during processing")
                            
                            structured_json = json.dumps(structured_errors, indent=2)
                            st.download_button(
                                label="📥 Download All Errors JSON (404s & Failures)",
                                data=structured_json,
                                file_name=f"database_extraction_errors_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json",
                                help="Download all non-200 errors grouped by status code for debugging"
                            )

            except Exception as e:
                st.error(f"❌ **Extraction failed:** {str(e)}")
                st.error("Please check if the codebase embeddings exist and the backend is running")


if __name__ == "__main__":
    main()