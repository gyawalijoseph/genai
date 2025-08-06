import streamlit as st
import requests
import json
import os
import re
from datetime import datetime

from utils.githubUtil import commit_json
from utils.metadataUtil import fetch_metadata

# Dynamic configuration - can be modified for any codebase
DEFAULT_DATABASE_SYSTEM_PROMPT = "You are an expert at analyzing code for database configurations, connections, queries, and data models."
DEFAULT_SERVER_SYSTEM_PROMPT = "You are an expert at analyzing code for server configurations, host information, and network settings."
DEFAULT_DATABASE_VECTOR_QUERY = "database sql connection query schema table model"
DEFAULT_SERVER_VECTOR_QUERY = "server host port configuration"
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}

# Initialize session state for error tracking
if 'combined_404_logs' not in st.session_state:
    st.session_state['combined_404_logs'] = []
if 'combined_error_logs' not in st.session_state:
    st.session_state['combined_error_logs'] = []


def vector_search_single(codebase, similarity_search_query, vector_results_count, search_suffix):
    """
    Single vector search implementation for one database
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
            st.warning(f"⚠️ **Search Warning for {search_target}:** HTTP {response.status_code}")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if response.status_code == 404:
                log_404_error("Vector search system", f"Query: {similarity_search_query}", 
                             f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
            
            log_error(f"vector_search_{response.status_code}", response.status_code, response.text, 
                     "Vector search system", f"Query: {similarity_search_query}", 
                     f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
            return {"results": [], "search_target": search_target, "success": False}

        data = response.json()

        if not isinstance(data, dict) or 'results' not in data:
            st.warning(f"⚠️ **Invalid response format from {search_target}**")
            return {"results": [], "search_target": search_target, "success": False}

        if not data['results']:
            st.info(f"ℹ️ **No results found in {search_target}**")
            return {"results": [], "search_target": search_target, "success": True}

        # Add search target info to each result
        for result in data['results']:
            result['search_target'] = search_target
            
        st.success(f"✅ **Found {len(data['results'])} code snippets** from {search_target}")
        return {"results": data['results'], "search_target": search_target, "success": True}

    except requests.exceptions.ConnectionError as e:
        st.error("❌ **Connection Error:** Could not reach vector search service at http://localhost:5000")
        st.info("💡 Make sure the vector search service is running")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_connection_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": [], "search_target": search_target, "success": False}

    except requests.exceptions.Timeout as e:
        st.warning(f"⏰ **Timeout for {search_target}:** Search took too long (>60 seconds)")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_timeout_error", None, f"Timeout after 60 seconds: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": [], "search_target": search_target, "success": False}

    except json.JSONDecodeError as e:
        st.warning(f"⚠️ **JSON Parse Error for {search_target}:** {str(e)}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_json_parse_error", None, f"JSON decode error: {str(e)}", 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": [], "search_target": search_target, "success": False}

    except Exception as e:
        st.warning(f"⚠️ **Search Failed for {search_target}:** {str(e)}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_error("vector_general_error", None, str(e), 
                 "Vector search system", f"Query: {similarity_search_query}", 
                 f"Codebase: {search_target}", "vector-search-endpoint", url, timestamp)
        return {"results": [], "search_target": search_target, "success": False}


def vector_search_multiple(codebase, similarity_search_query, vector_results_count, search_suffixes=["-external-files", ""]):
    """
    Multiple vector search implementation that searches both external files and actual codebase
    """
    all_results = []
    search_summary = []
    
    for suffix in search_suffixes:
        search_name = f"{codebase}{suffix}" if suffix else codebase
        
        result = vector_search_single(codebase, similarity_search_query, vector_results_count, suffix)
        
        search_summary.append({
            "database": search_name,
            "results_count": len(result['results']),
            "success": result['success']
        })
        
        if result['results']:
            all_results.extend(result['results'])
    
    return {"results": all_results, "search_summary": search_summary}


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
    st.session_state['combined_404_logs'].append(log_entry)


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
        "payload_size": len(system_prompt) + len(user_prompt) + len(codebase),
        "additional_info": additional_info or {},
        "error_severity": "HIGH" if status_code and status_code >= 500 else "MEDIUM" if status_code and status_code >= 400 else "LOW"
    }
    st.session_state['combined_error_logs'].append(log_entry)


def display_llm_call_details(step_name, system_prompt, user_prompt, codebase, response_output, file_source, call_number):
    """Display detailed LLM call information in expandable section"""
    with st.expander(f"🔍 **LLM Call Details - {step_name}**", expanded=False):
        st.write(f"**📂 File:** `{file_source}`")
        st.write(f"**🔢 Call #:** {call_number}")
        st.write(f"**⏰ Step:** {step_name}")
        
        # System Prompt
        st.write("**🤖 System Prompt:**")
        st.code(system_prompt, language="text")
        st.write(f"**Length:** {len(system_prompt)} characters")
        
        # User Prompt  
        st.write("**👤 User Prompt:**")
        st.code(user_prompt, language="text")
        st.write(f"**Length:** {len(user_prompt)} characters")
        
        # Codebase Content
        st.write("**📄 Codebase Content:**")
        if len(codebase) > 2000:
            st.write(f"**⚠️ Large content ({len(codebase)} chars) - showing first 2000 characters:**")
            st.code(codebase[:2000] + "\n\n... [TRUNCATED] ...", language="text")
        else:
            st.code(codebase, language="text")
        st.write(f"**Length:** {len(codebase)} characters")
        
        # Response Output
        st.write("**🔄 LLM Response:**")
        if response_output:
            if len(response_output) > 1000:
                st.write(f"**⚠️ Large response ({len(response_output)} chars) - showing first 1000 characters:**")
                st.code(response_output[:1000] + "\n\n... [TRUNCATED] ...", language="json")
            else:
                st.code(response_output, language="json")
            st.write(f"**Length:** {len(response_output)} characters")
        else:
            st.write("*No response received*")
        
        # Analysis Helper
        st.write("**🔍 Quick Analysis:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("System Prompt", f"{len(system_prompt)} chars")
        with col2:
            st.metric("User Prompt", f"{len(user_prompt)} chars") 
        with col3:
            st.metric("Codebase", f"{len(codebase)} chars")
        
        # Potential Issues Detection
        issues = []
        if len(codebase) < 10:
            issues.append("⚠️ Codebase content is very short")
        if len(system_prompt) < 20:
            issues.append("⚠️ System prompt is very short")
        if response_output and ('no' in response_output.lower() or 'none' in response_output.lower()):
            issues.append("ℹ️ LLM indicated no information found")
        if response_output and len(response_output) > 5000:
            issues.append("⚠️ Very long response - possible hallucination")
        
        if issues:
            st.write("**🚨 Potential Issues:**")
            for issue in issues:
                st.write(f"• {issue}")
        else:
            st.success("✅ No obvious issues detected")


def robust_json_parse(text_output, file_source="unknown"):
    """Robust JSON parsing with multiple fallback strategies"""
    if not text_output or not text_output.strip():
        return None, "Empty output from LLM"
    
    # Strategy 1: Direct JSON parsing
    try:
        return json.loads(text_output), None
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([^`]+)\s*```', text_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip()), None
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Extract JSON-like content between { and }
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0)), None
        except json.JSONDecodeError:
            pass
    
    # Strategy 4: Try to fix common JSON issues
    cleaned_text = text_output.strip()
    
    # Remove common prefixes/suffixes
    prefixes_to_remove = ['Here is the JSON:', 'JSON:', 'Result:', 'Output:']
    for prefix in prefixes_to_remove:
        if cleaned_text.startswith(prefix):
            cleaned_text = cleaned_text[len(prefix):].strip()
    
    # Try to extract anything that looks like JSON
    if '{' in cleaned_text and '}' in cleaned_text:
        start_idx = cleaned_text.find('{')
        end_idx = cleaned_text.rfind('}') + 1
        potential_json = cleaned_text[start_idx:end_idx]
        
        try:
            return json.loads(potential_json), None
        except json.JSONDecodeError:
            pass
    
    # Strategy 5: Create structured fallback
    text_stripped = text_output.strip().lower()
    if (text_stripped == 'no' or 
        text_stripped.startswith('no.') or 
        text_stripped.startswith('no,') or
        text_stripped.startswith('no ') or
        'no database' in text_stripped or
        'no server' in text_stripped or
        'none found' in text_stripped):
        return None, "LLM indicated no information found"
    
    # If all else fails, create a simple fallback structure
    fallback_data = {
        "source_file": file_source,
        "raw_llm_output": text_output[:500] + "..." if len(text_output) > 500 else text_output,
        "parsing_error": "Could not parse as valid JSON",
        "extraction_status": "partial"
    }
    
    return fallback_data, "Used fallback structure due to JSON parsing failure"


def deduplicate_server_info(server_info_array):
    """Remove duplicate server information based on host, port, and database_name"""
    if not server_info_array:
        return []
    
    seen_servers = set()
    deduplicated = []
    
    for server_info in server_info_array:
        if not isinstance(server_info, dict):
            continue
            
        # Create a key based on host, port, and database_name
        host = server_info.get('host', '').strip().lower()
        port = str(server_info.get('port', '')).strip()
        db_name = server_info.get('database_name', '').strip().lower()
        
        # Create unique key
        server_key = f"{host}:{port}:{db_name}"
        
        if server_key not in seen_servers and (host or port or db_name):
            seen_servers.add(server_key)
            deduplicated.append(server_info)
            st.info(f"✅ **Added unique server:** {host}:{port}/{db_name}")
        elif server_key in seen_servers:
            st.warning(f"⚠️ **Skipped duplicate server:** {host}:{port}/{db_name}")
    
    st.success(f"🔄 **Deduplication complete:** {len(server_info_array)} → {len(deduplicated)} servers")
    return deduplicated


def extract_server_information(data, system_prompt, vector_query):
    """Extract server information using workflow approach"""
    st.subheader("🖥️ Server Information Extraction")
    st.info(f"**Vector Search Query Used:** `{vector_query}`")
    st.info(f"**Files Found:** {len(data['results'])}")

    server_info_array = []

    for i, result in enumerate(data['results'], 1):
        try:
            similarity_info = ""
            if 'score' in result.get('metadata', {}):
                score = float(result['metadata']['score'])
                similarity_info = f" (Similarity: {score:.3f})"

            search_target = result.get('search_target', 'Unknown Database')
            st.markdown(f"### 🖥️ Processing Server Snippet {i}/{len(data['results'])}: `{result['metadata']['source']}`{similarity_info}")
            st.write(f"**🗄️ Source Database:** `{search_target}`")

            codebase = result['page_content']
            file_source = result['metadata']['source']

            # Apply text cleaning
            original_length = len(codebase)
            codebase = codebase.replace("@aexp", "@aexps")
            codebase = codebase.replace("@", "")
            codebase = codebase.replace("aimid", "")

            st.write(f"**📊 Content Length:** {original_length} → {len(codebase)} characters (after cleaning)")

            # Display codebase content
            try:
                with st.expander(f"📖 Code Snippet - {file_source}", expanded=False):
                    _, extension = os.path.splitext(file_source)
                    st.code(codebase, language=extension[1:] if extension else "text")
            except Exception:
                st.write(f"**Source:** {file_source} ({len(codebase)} chars)")

            if len(codebase) < 4:
                st.error("⚠️ Codebase content is too short to process.")
                continue

            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Server information detection
            st.write("**🔍 Step 1: Detecting Server Information**")
            detection_prompt = "Given the provided code snippet, identify if there are server informations present showing host, port and database information? If none, reply back with 'no'. Else extract the server information. Place in a json with keys 'host', 'port', 'database_name'. Reply with only the JSON. Make sure it's a valid JSON."

            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase
            }

            with st.spinner(f"🔄 Detecting server info in {file_source}..."):
                try:
                    response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

                    if response.status_code == 404:
                        st.error("❌ **404 Error: Request blocked by firewall**")
                        # Show LLM call details even for failures
                        display_llm_call_details("Server Detection (404 Error)", system_prompt, detection_prompt, codebase, "HTTP 404 Error", file_source, i)
                        log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    elif response.status_code != 200:
                        st.error(f"❌ **HTTP {response.status_code} Error:** {response.text}")
                        # Show LLM call details for HTTP errors
                        display_llm_call_details(f"Server Detection (HTTP {response.status_code})", system_prompt, detection_prompt, codebase, response.text, file_source, i)
                        log_error(f"http_{response.status_code}", response.status_code, response.text,
                                  system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    try:
                        response_json = response.json()
                    except json.JSONDecodeError as e:
                        st.error(f"❌ **Invalid JSON Response:** Could not parse response")
                        # Show LLM call details for JSON errors
                        display_llm_call_details("Server Detection (JSON Parse Error)", system_prompt, detection_prompt, codebase, response.text, file_source, i)
                        continue

                    status_code = response_json.get('status_code', response.status_code)
                    output = response_json.get('output', '')

                    # Always show LLM call details for transparency
                    display_llm_call_details("Server Detection", system_prompt, detection_prompt, codebase, output, file_source, i)

                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        continue

                    # Check if no server information found
                    output_stripped = output.strip().lower()
                    if (output_stripped == 'no' or 
                        output_stripped.startswith('no.') or 
                        'no server' in output_stripped):
                        st.warning("⚠️ **No server information found in this file**")
                        continue

                    # Parse JSON response
                    json_document, parse_error = robust_json_parse(output, file_source)
                    
                    if json_document is None:
                        if "no information found" in parse_error:
                            st.warning("⚠️ **No server information found in this file**")
                        else:
                            st.error(f"❌ **JSON Parsing Failed:** {parse_error}")
                        continue
                    
                    if parse_error:
                        st.warning(f"⚠️ **JSON Parsing Warning:** {parse_error}")
                        st.success("✅ **Server information detected (with parsing assistance)!**")
                    else:
                        st.success("✅ **Server information detected!**")
                    
                    try:
                        st.json(json_document)
                    except Exception:
                        st.write("Detected JSON:")
                        st.code(json.dumps(json_document, indent=2), language="json")

                    server_info_array.append(json_document)

                except Exception as e:
                    st.error(f"❌ **Unexpected Error:** {str(e)} - continuing with next file")
                    continue

        except Exception as file_error:
            st.error(f"❌ **Critical Error processing file {i}**: {str(file_error)}")
            continue

    # Deduplicate server information before returning
    deduplicated_servers = deduplicate_server_info(server_info_array)
    return deduplicated_servers


def extract_database_information_workflow(data, system_prompt, vector_query):
    """Extract database information using the enhanced workflow approach"""
    st.subheader("🗄️ Database Information Extraction")
    st.info(f"**Vector Search Query Used:** `{vector_query}`")
    st.info(f"**Files Found:** {len(data['results'])}")

    database_info_array = []

    for i, result in enumerate(data['results'], 1):
        try:
            similarity_info = ""
            if 'score' in result.get('metadata', {}):
                score = float(result['metadata']['score'])
                similarity_info = f" (Similarity: {score:.3f})"

            search_target = result.get('search_target', 'Unknown Database')
            st.markdown(f"### 📄 Processing Database Snippet {i}/{len(data['results'])}: `{result['metadata']['source']}`{similarity_info}")
            st.write(f"**🗄️ Source Database:** `{search_target}`")

            codebase = result['page_content']
            file_source = result['metadata']['source']

            # Apply text cleaning
            original_length = len(codebase)
            codebase = codebase.replace("@aexp", "@aexps")
            codebase = codebase.replace("@", "")
            codebase = codebase.replace("aimid", "")

            st.write(f"**📊 Content Length:** {original_length} → {len(codebase)} characters (after cleaning)")

            # Display codebase content
            try:
                with st.expander(f"📖 Code Snippet - {file_source}", expanded=False):
                    _, extension = os.path.splitext(file_source)
                    st.code(codebase, language=extension[1:] if extension else "text")
            except Exception:
                st.write(f"**Source:** {file_source} ({len(codebase)} chars)")

            if len(codebase) < 4:
                st.error("⚠️ Codebase content is too short to process.")
                continue

            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Database information detection
            st.write("**🔍 Step 1: Detecting Database Information**")
            detection_prompt = "Given the provided code snippet, identify if there are database-related configurations, connections, or queries present? If none, reply back with 'no'. Else extract the database information. Place in a json with keys for any database-related information found. Reply with only the JSON. Make sure it's a valid JSON."

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
                        # Show LLM call details even for failures
                        display_llm_call_details("Database Detection (404 Error)", system_prompt, detection_prompt, codebase, "HTTP 404 Error", file_source, i)
                        log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    elif response.status_code != 200:
                        st.error(f"❌ **HTTP {response.status_code} Error:** {response.text}")
                        # Show LLM call details for HTTP errors
                        display_llm_call_details(f"Database Detection (HTTP {response.status_code})", system_prompt, detection_prompt, codebase, response.text, file_source, i)
                        log_error(f"http_{response.status_code}", response.status_code, response.text,
                                  system_prompt, detection_prompt, codebase, file_source, url, timestamp)
                        continue

                    try:
                        response_json = response.json()
                    except json.JSONDecodeError as e:
                        st.error(f"❌ **Invalid JSON Response:** Could not parse response")
                        # Show LLM call details for JSON errors
                        display_llm_call_details("Database Detection (JSON Parse Error)", system_prompt, detection_prompt, codebase, response.text, file_source, i)
                        continue

                    status_code = response_json.get('status_code', response.status_code)
                    output = response_json.get('output', '')

                    # Always show LLM call details for transparency
                    display_llm_call_details("Database Detection", system_prompt, detection_prompt, codebase, output, file_source, i)

                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        continue

                    # Check if no database information found
                    output_stripped = output.strip().lower()
                    if (output_stripped == 'no' or 
                        output_stripped.startswith('no.') or 
                        'no database' in output_stripped):
                        st.warning("⚠️ **No database information found in this file**")
                        continue

                    # Parse JSON response
                    json_document, parse_error = robust_json_parse(output, file_source)
                    
                    if json_document is None:
                        if "no information found" in parse_error:
                            st.warning("⚠️ **No database information found in this file**")
                        else:
                            st.error(f"❌ **JSON Parsing Failed:** {parse_error}")
                        continue
                    
                    if parse_error:
                        st.warning(f"⚠️ **JSON Parsing Warning:** {parse_error}")
                        st.success("✅ **Database information detected (with parsing assistance)!**")
                    else:
                        st.success("✅ **Database information detected!**")
                    
                    try:
                        st.json(json_document)
                    except Exception:
                        st.write("Detected JSON:")
                        st.code(json.dumps(json_document, indent=2), language="json")

                    database_info_array.append(json_document)

                except Exception as e:
                    st.error(f"❌ **Unexpected Error:** {str(e)} - continuing with next file")
                    continue

        except Exception as file_error:
            st.error(f"❌ **Critical Error processing file {i}**: {str(file_error)}")
            continue

    return database_info_array


def validate_sql_basic(query):
    """Basic SQL validation to check if query looks complete"""
    query_lower = query.lower().strip()
    
    # Check for basic SQL structure
    if query_lower.startswith('select'):
        return 'from' in query_lower
    elif query_lower.startswith('insert'):
        return 'into' in query_lower and ('values' in query_lower or 'select' in query_lower)
    elif query_lower.startswith('update'):
        return 'set' in query_lower
    elif query_lower.startswith('delete'):
        return 'from' in query_lower
    elif query_lower.startswith(('create', 'drop', 'alter')):
        return len(query_lower) > 15  # DDL statements should be reasonably long
    
    return False


def extract_sql_from_codebase(codebase):
    """Extract SQL queries from original codebase using pattern matching"""
    queries = []
    
    # SQL patterns - look for multiline SQL statements
    sql_patterns = [
        r'(?i)(SELECT\s+[\s\S]*?FROM\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
        r'(?i)(INSERT\s+INTO\s+[\s\S]*?VALUES\s*\([^)]*\))',
        r'(?i)(UPDATE\s+[\s\S]*?SET\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
        r'(?i)(DELETE\s+FROM\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
        r'(?i)(CREATE\s+TABLE\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
    ]
    
    for pattern in sql_patterns:
        matches = re.findall(pattern, codebase, re.MULTILINE | re.DOTALL)
        for match in matches:
            cleaned = re.sub(r'\s+', ' ', match.strip())  # Normalize whitespace
            if len(cleaned) > 15 and validate_sql_basic(cleaned):
                queries.append(cleaned)
    
    return queries


def infer_data_type(key, value, original_codebase):
    """Infer data type from key name, value, and codebase context"""
    key_lower = key.lower()
    value_str = str(value).lower()
    
    # Check for explicit type mentions in the key or value
    type_indicators = {
        'string': ['name', 'title', 'description', 'text', 'varchar', 'char'],
        'integer': ['id', 'count', 'number', 'int', 'age', 'year'],
        'boolean': ['is_', 'has_', 'active', 'enabled', 'bool'],
        'datetime': ['date', 'time', 'created', 'updated', 'timestamp'],
        'decimal': ['price', 'amount', 'rate', 'decimal', 'float'],
        'json': ['config', 'settings', 'data', 'json']
    }
    
    for data_type, indicators in type_indicators.items():
        if any(indicator in key_lower for indicator in indicators):
            return data_type
        if any(indicator in value_str for indicator in indicators):
            return data_type
    
    # Check original codebase for type hints
    if original_codebase:
        codebase_lower = original_codebase.lower()
        if value_str in codebase_lower:
            # Look for type annotations or SQL type definitions
            if f'{value_str} varchar' in codebase_lower or f'{value_str} text' in codebase_lower:
                return 'string'
            elif f'{value_str} int' in codebase_lower or f'{value_str} number' in codebase_lower:
                return 'integer'
            elif f'{value_str} date' in codebase_lower or f'{value_str} timestamp' in codebase_lower:
                return 'datetime'
            elif f'{value_str} bool' in codebase_lower:
                return 'boolean'
    
    return 'string'  # Default fallback


def infer_crud_operations(original_codebase, table_name, column_name=None):
    """Infer CRUD operations from codebase analysis"""
    if not original_codebase:
        return 'UNKNOWN'
    
    codebase_lower = original_codebase.lower()
    table_lower = table_name.lower()
    operations = set()
    
    # Check for SQL operations on this table
    if f'select * from {table_lower}' in codebase_lower or f'select' in codebase_lower and table_lower in codebase_lower:
        operations.add('READ')
    
    if f'insert into {table_lower}' in codebase_lower:
        operations.add('CREATE')
    
    if f'update {table_lower}' in codebase_lower:
        operations.add('UPDATE')
    
    if f'delete from {table_lower}' in codebase_lower:
        operations.add('DELETE')
    
    # Check for ORM patterns
    orm_patterns = {
        'READ': [f'{table_lower}.find', f'{table_lower}.get', f'{table_lower}.select'],
        'CREATE': [f'{table_lower}.create', f'{table_lower}.insert', f'{table_lower}.save'],
        'UPDATE': [f'{table_lower}.update', f'{table_lower}.modify', f'{table_lower}.save'],
        'DELETE': [f'{table_lower}.delete', f'{table_lower}.remove', f'{table_lower}.destroy']
    }
    
    for operation, patterns in orm_patterns.items():
        if any(pattern in codebase_lower for pattern in patterns):
            operations.add(operation)
    
    # Column-specific analysis
    if column_name:
        col_lower = column_name.lower()
        if col_lower in ['id', 'uuid', 'primary_key']:
            operations.add('READ')  # IDs are typically read-only
        elif 'password' in col_lower:
            operations.add('CREATE')
            operations.add('UPDATE')  # Passwords are created and updated, rarely read
    
    return ','.join(sorted(operations)) if operations else 'READ'  # Default to READ


def analyze_table_columns(db_entry, original_codebase, table_name):
    """Analyze extracted data and codebase to find detailed column information"""
    columns = []
    
    # Look for column information in the extracted data
    for key, value in db_entry.items():
        key_lower = key.lower()
        
        # Look for column/field lists
        if any(keyword in key_lower for keyword in ['column', 'field', 'attribute']):
            if isinstance(value, list):
                for col in value:
                    if isinstance(col, str):
                        columns.append({
                            "column_name": col,
                            "data_type": infer_data_type(key, col, original_codebase),
                            "CRUD": infer_crud_operations(original_codebase, table_name, col)
                        })
            elif isinstance(value, str):
                columns.append({
                    "column_name": value,
                    "data_type": infer_data_type(key, value, original_codebase),
                    "CRUD": infer_crud_operations(original_codebase, table_name, value)
                })
    
    # If no columns found in extracted data, try to parse from original codebase
    if not columns and original_codebase:
        columns = extract_columns_from_codebase(original_codebase, table_name)
    
    return columns


def extract_columns_from_codebase(codebase, table_name):
    """Extract column information from original codebase"""
    columns = []
    
    # Pattern for SQL CREATE TABLE statements
    create_pattern = rf'(?i)CREATE\s+TABLE\s+{re.escape(table_name)}\s*\((.*?)\)'
    match = re.search(create_pattern, codebase, re.DOTALL)
    
    if match:
        columns_def = match.group(1)
        # Parse column definitions
        column_lines = [line.strip() for line in columns_def.split(',')]
        
        for line in column_lines:
            if line and not line.upper().startswith(('PRIMARY', 'FOREIGN', 'UNIQUE', 'INDEX')):
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0].strip('`"[]')
                    col_type = parts[1].upper()
                    
                    # Map SQL types to our types
                    type_mapping = {
                        'VARCHAR': 'string', 'TEXT': 'string', 'CHAR': 'string',
                        'INT': 'integer', 'INTEGER': 'integer', 'BIGINT': 'integer',
                        'DECIMAL': 'decimal', 'FLOAT': 'decimal', 'DOUBLE': 'decimal',
                        'DATE': 'datetime', 'DATETIME': 'datetime', 'TIMESTAMP': 'datetime',
                        'BOOLEAN': 'boolean', 'BOOL': 'boolean',
                        'JSON': 'json', 'JSONB': 'json'
                    }
                    
                    mapped_type = 'string'  # default
                    for sql_type, our_type in type_mapping.items():
                        if col_type.startswith(sql_type):
                            mapped_type = our_type
                            break
                    
                    columns.append({
                        "column_name": col_name,
                        "data_type": mapped_type,
                        "CRUD": infer_crud_operations(codebase, table_name, col_name)
                    })
    
    return columns


def transform_actual_extracted_data(db_info_list, all_vector_results, system_prompt):
    """Transform actual extracted data into final structure WITHOUT making new LLM calls"""
    st.write("🏗️ **Building final database structure using ACTUAL extracted data...**")
    
    # Initialize the final structure
    final_output = {
        "Table Information": [],
        "SQL_QUERIES": [],
        "Invalid_SQL_Queries": []
    }
    
    if not db_info_list:
        st.warning("⚠️ **No database information to process**")
        return final_output
    
    st.info(f"**🔢 Processing {len(db_info_list)} extracted database entries with REAL data**")
    
    # Process each extracted database entry using the ACTUAL data from initial extraction
    for i, db_entry in enumerate(db_info_list):
        if not isinstance(db_entry, dict):
            st.warning(f"⚠️ **Entry {i+1} is not a dictionary, skipping**")
            continue
        
        # Get source file information
        source_file = f"extracted_data_{i+1}.unknown"
        if 'source_file' in db_entry:
            source_file = db_entry['source_file']
        elif len(all_vector_results) > i:
            source_file = all_vector_results[i].get('metadata', {}).get('source', source_file)
        
        # Get original codebase content for reference
        original_codebase = ""
        if len(all_vector_results) > i:
            original_codebase = all_vector_results[i].get('page_content', '')
        
        st.markdown(f"### 🔍 **Processing REAL Data from:** `{source_file}`")
        
        # Show the comparison between extracted and original with LLM call visibility
        with st.expander(f"🔍 **LLM Call Details - Original Database Detection** (File: {source_file})", expanded=False):
            st.write(f"**📂 File:** `{source_file}`")
            st.write(f"**🔢 Entry #:** {i+1}")
            st.write(f"**⏰ Step:** Database Detection (Original)")
            
            # Show what the LLM originally extracted
            st.write("**🔄 LLM Response (ACTUAL EXTRACTED DATA):**")
            st.code(json.dumps(db_entry, indent=2), language="json")
            st.write(f"**Length:** {len(json.dumps(db_entry))} characters")
            
            # Show original code that was analyzed
            st.write("**📄 Original Codebase Content:**")
            if original_codebase:
                if len(original_codebase) > 2000:
                    st.code(original_codebase[:2000] + "\n\n... [TRUNCATED] ...", language="text")
                else:
                    st.code(original_codebase, language="text")
                st.write(f"**Length:** {len(original_codebase)} characters")
            else:
                st.write("*No original codebase available*")
            
            # Analysis of what was extracted
            st.write("**🔍 Extraction Analysis:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Keys Extracted", len(db_entry.keys()))
            with col2:
                table_keys = [k for k in db_entry.keys() if any(word in k.lower() for word in ['table', 'column', 'field', 'schema'])]
                st.metric("Table-related Keys", len(table_keys))
            with col3:
                sql_content = [v for v in db_entry.values() if isinstance(v, str) and any(word in v.lower() for word in ['select', 'insert', 'update', 'delete'])]
                st.metric("SQL-like Values", len(sql_content))
        
        # Process Table Information using ACTUAL extracted data
        st.write("**🗃️ Step 1: Processing Table Information from REAL Extracted Data**")
        
        table_entry = {source_file: {}}
        table_found = False
        
        # Look through the ACTUAL extracted data for table information with enhanced analysis
        for key, value in db_entry.items():
            key_lower = key.lower()
            
            # Check for table-related keys
            if any(keyword in key_lower for keyword in ['table', 'schema', 'model', 'entity']):
                if isinstance(value, str) and value.strip():
                    # Single table name - analyze for more detailed information
                    table_name = value.strip()
                    columns_info = analyze_table_columns(db_entry, original_codebase, table_name)
                    
                    table_entry[source_file][table_name] = {
                        "Field Information": columns_info if columns_info else [{
                            "column_name": f"extracted_from_{key}",
                            "data_type": infer_data_type(key, value, original_codebase),
                            "CRUD": infer_crud_operations(original_codebase, table_name)
                        }]
                    }
                    table_found = True
                    st.success(f"✅ **Found table '{table_name}' from key '{key}' with {len(table_entry[source_file][table_name]['Field Information'])} field(s)**")
                elif isinstance(value, list):
                    # Multiple tables
                    for table_name in value:
                        if isinstance(table_name, str) and table_name.strip():
                            columns_info = analyze_table_columns(db_entry, original_codebase, table_name)
                            
                            table_entry[source_file][table_name] = {
                                "Field Information": columns_info if columns_info else [{
                                    "column_name": f"from_{key}",
                                    "data_type": infer_data_type(key, table_name, original_codebase),
                                    "CRUD": infer_crud_operations(original_codebase, table_name)
                                }]
                            }
                            table_found = True
                    st.success(f"✅ **Found {len(value)} tables from key '{key}': {value}**")
            
            # Check for column-related keys with enhanced data type detection
            elif any(keyword in key_lower for keyword in ['column', 'field', 'attribute']):
                table_name = "UNKNOWN_TABLE"
                # Try to find associated table name
                for tkey, tvalue in db_entry.items():
                    if any(tkeyword in tkey.lower() for tkeyword in ['table', 'schema', 'model']) and isinstance(tvalue, str):
                        table_name = tvalue
                        break
                
                if isinstance(value, str) and value.strip():
                    if table_name not in table_entry[source_file]:
                        table_entry[source_file][table_name] = {"Field Information": []}
                    
                    # Enhanced column analysis
                    column_info = {
                        "column_name": value,
                        "data_type": infer_data_type(key, value, original_codebase),
                        "CRUD": infer_crud_operations(original_codebase, table_name, value)
                    }
                    
                    table_entry[source_file][table_name]["Field Information"].append(column_info)
                    table_found = True
                    st.success(f"✅ **Found column '{value}' for table '{table_name}' (type: {column_info['data_type']}, CRUD: {column_info['CRUD']})**")
                elif isinstance(value, list):
                    if table_name not in table_entry[source_file]:
                        table_entry[source_file][table_name] = {"Field Information": []}
                    
                    for col_name in value:
                        if isinstance(col_name, str) and col_name.strip():
                            column_info = {
                                "column_name": col_name,
                                "data_type": infer_data_type(key, col_name, original_codebase),
                                "CRUD": infer_crud_operations(original_codebase, table_name, col_name)
                            }
                            table_entry[source_file][table_name]["Field Information"].append(column_info)
                    table_found = True
                    st.success(f"✅ **Found {len(value)} columns for table '{table_name}' with enhanced analysis**")
        
        if table_found and table_entry[source_file]:
            final_output["Table Information"].append(table_entry)
            st.json(table_entry)
        else:
            st.info(f"ℹ️ **No table information found in extracted data for {source_file}**")
        
        # Process SQL Queries using BOTH extracted data AND original codebase
        st.write("**🔍 Step 2: Processing SQL Queries from REAL Extracted Data AND Original Code**")
        
        sql_found = False
        
        # Method 1: Check extracted data for SQL queries
        for key, value in db_entry.items():
            if isinstance(value, str):
                value_lower = value.lower()
                # Check if this value contains SQL keywords
                if any(sql_keyword in value_lower for sql_keyword in ['select', 'insert', 'update', 'delete', 'create', 'drop']):
                    # Enhanced SQL validation
                    cleaned_query = value.strip()
                    if len(cleaned_query) > 10 and validate_sql_basic(cleaned_query):
                        final_output["SQL_QUERIES"].append(cleaned_query)
                        st.success(f"✅ **Found SQL query from extracted key '{key}':**")
                        st.code(cleaned_query, language="sql")
                        sql_found = True
                    else:
                        # Add to invalid queries
                        final_output["Invalid_SQL_Queries"].append({
                            "source_file": source_file,
                            "query": cleaned_query,
                            "reason": "Invalid SQL syntax or too short"
                        })
                        st.warning(f"⚠️ **Found invalid SQL from key '{key}' (validation failed)**")
            elif isinstance(value, list):
                # Handle lists of SQL queries
                for item in value:
                    if isinstance(item, str):
                        item_lower = item.lower()
                        if any(sql_keyword in item_lower for sql_keyword in ['select', 'insert', 'update', 'delete', 'create', 'drop']):
                            cleaned_query = item.strip()
                            if len(cleaned_query) > 10 and validate_sql_basic(cleaned_query):
                                final_output["SQL_QUERIES"].append(cleaned_query)
                                st.success(f"✅ **Found SQL query from list in key '{key}':**")
                                st.code(cleaned_query, language="sql")
                                sql_found = True
                            else:
                                final_output["Invalid_SQL_Queries"].append({
                                    "source_file": source_file,
                                    "query": cleaned_query,
                                    "reason": "Invalid SQL syntax or too short"
                                })
        
        # Method 2: Also scan the original codebase for SQL patterns
        if original_codebase:
            codebase_queries = extract_sql_from_codebase(original_codebase)
            for query in codebase_queries:
                if query not in final_output["SQL_QUERIES"]:  # Avoid duplicates
                    final_output["SQL_QUERIES"].append(query)
                    st.success(f"✅ **Found SQL query from original codebase:**")
                    st.code(query, language="sql")
                    sql_found = True
        
        if not sql_found:
            st.info(f"ℹ️ **No SQL queries found in extracted data or original code for {source_file}**")
    
    # Summary of what was processed using REAL data
    st.markdown("---")
    st.write("**📊 Final Processing Summary (Using ACTUAL Extracted Data):**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tables Found", len(final_output["Table Information"]))
    with col2:
        st.metric("Valid SQL Queries", len(final_output["SQL_QUERIES"]))
    with col3:
        st.metric("Invalid SQL Queries", len(final_output["Invalid_SQL_Queries"]))
    
    st.success("✅ **Final structure built using ONLY the real extracted data - no dummy/placeholder data!**")
    
    return final_output


def transform_with_workflow_approach(db_info_list, all_vector_results):
    """Legacy workflow function - redirects to use actual extracted data instead of dummy data"""
    # This maintains backward compatibility while using the actual data approach
    return transform_actual_extracted_data(db_info_list, all_vector_results, DEFAULT_DATABASE_SYSTEM_PROMPT)


def commit_json_to_github(codebase, json_data):
    """Simple GitHub commit function using utils/githubUtil.py"""
    st.subheader("📤 GitHub Integration")
    
    # Display the JSON that will be pushed
    st.write("**📋 Data to be pushed to GitHub:**")
    with st.expander("📄 View JSON Data", expanded=False):
        st.code(json.dumps(json_data, indent=2), language="json")
    st.write(f"**📊 Data size:** {len(json.dumps(json_data))} characters")
    
    # Use the simple commit_json function from utils
    st.text(commit_json(codebase, json_data))


def display_error_logs():
    """Display comprehensive error logs"""
    total_404s = len(st.session_state['combined_404_logs'])
    total_errors = len(st.session_state['combined_error_logs'])

    if total_404s == 0 and total_errors == 0:
        st.info("🎉 No errors logged yet!")
        return

    # Summary metrics
    if total_404s > 0:
        st.error(f"🚨 {total_404s} 404 Errors")
    if total_errors > 0:
        st.info(f"📊 Total Errors: {total_errors}")

    # Clear logs buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear 404 Logs", type="secondary", key="clear_404"):
            st.session_state['combined_404_logs'] = []
            st.success("404 logs cleared!")
            st.rerun()

    with col2:
        if st.button("🗑️ Clear All Error Logs", type="secondary", key="clear_all"):
            st.session_state['combined_404_logs'] = []
            st.session_state['combined_error_logs'] = []
            st.success("All error logs cleared!")
            st.rerun()


def main():
    st.set_page_config(
        page_title="Combined Information Extraction",
        page_icon="🔍",
        layout="wide"
    )

    st.title("🔍 Combined Information Extraction")
    st.markdown("**Unified server and database information extraction with GitHub integration**")

    # Sidebar for error tracking
    with st.sidebar:
        st.header("🚨 Error Tracking & Debug")
        total_404s = len(st.session_state['combined_404_logs'])
        total_errors = len(st.session_state['combined_error_logs'])

        if total_404s > 0 or total_errors > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("404 Errors", total_404s)
            with col2:
                st.metric("Other Errors", total_errors)

        display_error_logs()

    # Main extraction form
    with st.form("combined_extraction_form"):
        col1, col2 = st.columns(2)

        with col1:
            codebase = st.text_input(
                "🗂️ Codebase Name:",
                placeholder="my-project",
                help="Name of the codebase to search for information"
            )

            database_system_prompt = st.text_area(
                "🗄️ Database System Prompt:",
                value=DEFAULT_DATABASE_SYSTEM_PROMPT,
                height=100,
                help="Instructions for database extraction"
            )

            database_vector_query = st.text_input(
                "🔍 Database Vector Query:",
                value=DEFAULT_DATABASE_VECTOR_QUERY,
                help="Query used to find database-related files"
            )

        with col2:
            vector_results_count = st.number_input(
                '📊 Max Results Count (per database):',
                value=10,
                min_value=1,
                max_value=50,
                help="Maximum number of files to process from each vector database"
            )
            
            server_system_prompt = st.text_area(
                "🖥️ Server System Prompt:",
                value=DEFAULT_SERVER_SYSTEM_PROMPT,
                height=100,
                help="Instructions for server extraction"
            )

            server_vector_query = st.text_input(
                "🔍 Server Vector Query:",
                value=DEFAULT_SERVER_VECTOR_QUERY,
                help="Query used to find server-related files"
            )

        st.info("🗄️ **Automatic Multi-Database Search:** Will search both main codebase and external files")

        submit_button = st.form_submit_button(
            '🚀 Start Combined Information Extraction',
            use_container_width=True
        )

    # Process form submission
    if submit_button:
        if not codebase:
            st.error("❌ Please enter a codebase name")
        elif not database_vector_query.strip() or not server_vector_query.strip():
            st.error("❌ Please enter vector search queries")
        elif not database_system_prompt.strip() or not server_system_prompt.strip():
            st.error("❌ System prompts are required")
        else:
            try:
                st.markdown("---")
                st.header("🔄 Combined Processing Flow")

                # Search suffixes for both main and external files
                search_suffixes = ["-external-files", ""]
                target_databases = [f"{codebase}{suffix}" if suffix else codebase for suffix in search_suffixes]

                # Initialize final combined results
                combined_results = {
                    "extraction_metadata": {
                        "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "codebase": codebase,
                        "databases_searched": target_databases,
                        "extraction_type": "combined_server_database"
                    },
                    "Application": {},
                    "Server Information": [],
                    "Database Information": {
                        "Table Information": [],
                        "SQL_QUERIES": [],
                        "Invalid_SQL_Queries": []
                    }
                }

                # Step 0: Car Info (Application Metadata) Extraction
                st.subheader("🚗 Step 0: Car Info (Application Metadata)")
                st.info(f"**🗂️ Fetching metadata for:** `{codebase}`")
                
                try:
                    metadata = fetch_metadata(codebase)
                    if metadata is not None:
                        combined_results['Application'] = metadata
                        st.success("✅ **Car info extraction completed!**")
                        st.json(metadata)
                    else:
                        st.warning("⚠️ **No car info/metadata found**")
                        combined_results['Application'] = {}
                except Exception as e:
                    st.error(f"❌ **Car info extraction failed:** {str(e)}")
                    combined_results['Application'] = {}

                # Step 1: Server Information Extraction
                st.subheader("🖥️ Step 1: Server Information Extraction")
                st.info(f"**🗂️ Target Databases:** `{', '.join(target_databases)}`")
                st.info(f"**🔍 Search Query:** `{server_vector_query}`")

                server_data = vector_search_multiple(codebase, server_vector_query, vector_results_count, search_suffixes)

                if server_data and 'results' in server_data and len(server_data['results']) > 0:
                    server_information = extract_server_information(server_data, server_system_prompt, server_vector_query)
                    combined_results["Server Information"] = server_information
                    st.success(f"✅ **Server extraction completed!** Found {len(server_information)} server entries")
                else:
                    st.warning("⚠️ **No server information found**")

                # Step 2: Database Information Extraction
                st.subheader("🗄️ Step 2: Database Information Extraction")
                st.info(f"**🔍 Search Query:** `{database_vector_query}`")

                database_data = vector_search_multiple(codebase, database_vector_query, vector_results_count, search_suffixes)

                if database_data and 'results' in database_data and len(database_data['results']) > 0:
                    database_information = extract_database_information_workflow(database_data, database_system_prompt, database_vector_query)
                    
                    # Transform database information using ACTUAL extracted data (no dummy data)
                    transformed_database_data = transform_actual_extracted_data(database_information, database_data['results'], database_system_prompt)
                    combined_results["Database Information"] = transformed_database_data
                    
                    st.success(f"✅ **Database extraction completed!** Found {len(database_information)} database entries")
                else:
                    st.warning("⚠️ **No database information found**")

                # Step 3: Display Combined Results
                st.header("🎯 Combined Final Results")
                st.subheader("📊 Complete Extraction Results")
                st.json(combined_results)

                # Download options
                col1, col2 = st.columns(2)
                with col1:
                    results_json = json.dumps(combined_results, indent=2)
                    st.download_button(
                        label="📥 Download Combined Results JSON",
                        data=results_json,
                        file_name=f"combined_extraction_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )

                with col2:
                    # Clean format without metadata
                    clean_results = {
                        "Application": combined_results["Application"],
                        "Server Information": combined_results["Server Information"],
                        "Database Information": combined_results["Database Information"]
                    }
                    clean_json = json.dumps(clean_results, indent=2)
                    st.download_button(
                        label="📥 Download Clean Format JSON",
                        data=clean_json,
                        file_name=f"combined_clean_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )

                # Step 4: GitHub Integration
                commit_json_to_github(codebase, combined_results)

                st.balloons()

            except Exception as e:
                st.error(f"❌ **Extraction failed:** {str(e)}")
                st.error("Please check if the selected database embeddings exist and the backend is running")


if __name__ == "__main__":
    main()