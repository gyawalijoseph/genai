import streamlit as st
import requests
import json
import os
import re
from datetime import datetime

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
                        log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
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
                        continue

                    status_code = response_json.get('status_code', response.status_code)

                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        continue

                    output = response_json.get('output', '')

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

    return server_info_array


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
                        log_404_error(system_prompt, detection_prompt, codebase, file_source, url, timestamp)
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
                        continue

                    status_code = response_json.get('status_code', response.status_code)

                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        continue

                    output = response_json.get('output', '')

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


def transform_with_workflow_approach(db_info_list, all_vector_results):
    """Transform database information using structured workflows"""
    st.write("🏗️ **Building final database structure using workflow approach...**")
    
    # Initialize the final structure
    final_output = {
        "Table Information": [],
        "SQL_QUERIES": [],
        "Invalid_SQL_Queries": []
    }
    
    if not db_info_list:
        return final_output
    
    # Process each extracted database entry with structured workflows
    for i, db_entry in enumerate(db_info_list):
        if not isinstance(db_entry, dict):
            continue
        
        # Get source file information
        source_file = f"extracted_data_{i+1}.unknown"
        if 'source_file' in db_entry:
            source_file = db_entry['source_file']
        elif len(all_vector_results) > i:
            source_file = all_vector_results[i].get('metadata', {}).get('source', source_file)
        
        # Get original codebase content for detailed analysis  
        original_codebase = ""
        if len(all_vector_results) > i:
            original_codebase = all_vector_results[i].get('page_content', '')
        
        st.write(f"**📄 Processing workflow for:** `{source_file}`")
        
        # Create basic table entry from extracted data
        if db_entry:
            table_entry = {source_file: {}}
            
            # Look for table-related information in the extracted data
            table_found = False
            for key, value in db_entry.items():
                if isinstance(value, str) and value.strip() and any(keyword in key.lower() for keyword in ['table', 'column', 'field', 'schema']):
                    table_entry[source_file]["EXTRACTED_TABLE"] = {
                        "Field Information": [{
                            "column_name": key,
                            "data_type": "extracted",
                            "CRUD": "UNKNOWN"
                        }]
                    }
                    table_found = True
                    break
            
            if table_found:
                final_output["Table Information"].append(table_entry)
                st.success(f"✅ **Extracted table information from {source_file}**")
        
        # Look for SQL-like content
        content = json.dumps(db_entry).lower()
        sql_indicators = ['select', 'insert', 'update', 'delete', 'create', 'drop']
        if any(indicator in content for indicator in sql_indicators):
            # Extract potential SQL queries from the content
            for key, value in db_entry.items():
                if isinstance(value, str) and any(indicator in value.lower() for indicator in sql_indicators):
                    final_output["SQL_QUERIES"].append(value)
                    st.success(f"✅ **Found SQL query in {source_file}**")
    
    return final_output


def commit_json_to_github(codebase, json_data):
    """Enhanced GitHub commit function with user confirmation"""
    st.subheader("📤 GitHub Integration")
    
    if st.checkbox("🔧 **Enable GitHub Push**", help="Check this to enable pushing results to GitHub"):
        st.info("⚠️ **GitHub Configuration Required:** Update the URL and credentials below")
        
        # Display the JSON that will be pushed
        st.write("**📋 Data to be pushed to GitHub:**")
        with st.expander("📄 View JSON Data", expanded=False):
            st.code(json.dumps(json_data, indent=2), language="json")
        st.write(f"**📊 Data size:** {len(json.dumps(json_data))} characters")
        
        # Configuration options
        with st.expander("🔧 GitHub Configuration", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                github_token = st.text_input("GitHub Token:", type="password", help="Your GitHub personal access token")
                repo_owner = st.text_input("Repository Owner:", value="yourusername", help="GitHub username or organization")
                repo_name = st.text_input("Repository Name:", value="yourrepo", help="Name of the repository")
                
            with col2:
                file_path = st.text_input("File Path:", value=f"extractions/{codebase}_combined_extraction.json", help="Path where to save the file in the repo")
                branch = st.text_input("Branch:", value="main", help="Target branch")
                commit_message = st.text_area("Commit Message:", value=f"Add combined extraction results for {codebase}", help="Commit message")
        
        # Validation
        if not github_token:
            st.warning("⚠️ **GitHub token is required for authentication**")
            st.info("💡 Generate a token at: https://github.com/settings/tokens")
        elif not repo_owner or not repo_name:
            st.warning("⚠️ **Repository owner and name are required**")
        else:
            # Confirmation step
            st.write("**✅ Configuration Complete - Ready to Push**")
            
            if st.button("🚀 **CONFIRM: Push to GitHub**", type="primary"):
                st.warning("⚠️ **This will commit data to your GitHub repository!**")
                st.write(f"**Target:** `{repo_owner}/{repo_name}` → `{file_path}` (branch: `{branch}`)")
                
                # Final confirmation with unique key
                confirm_key = f"github_confirm_{codebase}_{datetime.now().strftime('%H%M%S')}"
                if st.button("✅ **FINAL CONFIRMATION: Yes, push to GitHub**", type="secondary", key=confirm_key):
                    try:
                        # Actual GitHub API implementation
                        github_url = f"http://localhost:5000/github-commit"
                        
                        payload = {
                            "codebase": codebase,
                            "github_token": github_token,
                            "repo_owner": repo_owner,
                            "repo_name": repo_name,
                            "file_path": file_path,
                            "branch": branch,
                            "commit_message": commit_message,
                            "content": json_data
                        }
                        
                        with st.spinner("📤 Pushing to GitHub..."):
                            response = requests.post(github_url, json=payload, headers=HEADERS, timeout=60)
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('status') == 'success':
                                st.success("🎉 **Successfully pushed to GitHub!**")
                                st.info(f"**Repository:** {repo_owner}/{repo_name}")
                                st.info(f"**Branch:** {branch}")
                                st.info(f"**File Path:** {file_path}")
                                st.info(f"**Commit Message:** {commit_message}")
                                
                                if 'commit_url' in result:
                                    st.info(f"**Commit URL:** {result['commit_url']}")
                                    
                                # Clear sensitive data from session
                            else:
                                st.error(f"❌ **GitHub push failed:** {result.get('message', 'Unknown error')}")
                        else:
                            st.error(f"❌ **GitHub API Error:** HTTP {response.status_code}")
                            if response.text:
                                st.error(f"Response: {response.text}")
                        
                    except requests.exceptions.ConnectionError:
                        st.error("❌ **Connection Error:** Could not reach GitHub service")
                        st.info("💡 Make sure the backend service is running at http://localhost:5000")
                    except requests.exceptions.Timeout:
                        st.error("❌ **Timeout Error:** GitHub push took too long")
                    except Exception as e:
                        st.error(f"❌ **GitHub push failed:** {str(e)}")
                        st.info("💡 Check your GitHub configuration and credentials")
    
    else:
        st.info("💡 **GitHub Push Disabled** - Check the box above to enable GitHub integration")


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
                    "Server Information": [],
                    "Database Information": {
                        "Table Information": [],
                        "SQL_QUERIES": [],
                        "Invalid_SQL_Queries": []
                    }
                }

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
                    
                    # Transform database information using workflow approach
                    transformed_database_data = transform_with_workflow_approach(database_information, database_data['results'])
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