import streamlit as st
import requests
import json
import os
import re
from datetime import datetime

from utils.githubUtil import commit_json
from utils.metadataUtil import fetch_metadata

# Dynamic configuration - can be modified for any codebase
DEFAULT_DATABASE_SYSTEM_PROMPT = "You are an expert at analyzing code for NoSQL database configurations, particularly Couchbase. You understand buckets, collections, documents, N1QL queries, indexes, and Couchbase SDK operations."
DEFAULT_DATABASE_VECTOR_QUERY = "couchbase bucket collection document n1ql query index cluster connection sdk nosql json"
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}

# Initialize session state for error tracking
if 'new_db_404_logs' not in st.session_state:
    st.session_state['new_db_404_logs'] = []
if 'new_db_error_logs' not in st.session_state:
    st.session_state['new_db_error_logs'] = []


def vector_search_single(vector_name, similarity_search_query, vector_results_count, similarity_threshold=0.4):
    """Single vector search implementation for existing embeddings"""
    url = "http://localhost:5000/vector-search"
    payload = {
        "codebase": vector_name,
        "query": similarity_search_query,
        "vector_results_count": vector_results_count,
        "similarity_threshold": similarity_threshold
    }

    try:
        with st.spinner(f"🔍 Searching vector '{vector_name}' for '{similarity_search_query}'..."):
            response = requests.post(url, json=payload, headers=HEADERS, timeout=60)

        if response.status_code != 200:
            st.warning(f"⚠️ **Search Warning for {vector_name}:** HTTP {response.status_code}")
            return {"results": [], "search_target": vector_name, "success": False}

        data = response.json()

        if not isinstance(data, dict) or 'results' not in data:
            st.warning(f"⚠️ **Invalid response format from {vector_name}**")
            return {"results": [], "search_target": vector_name, "success": False}

        if not data['results']:
            st.info(f"ℹ️ **No results found in {vector_name}**")
            return {"results": [], "search_target": vector_name, "success": True}

        # Debug: Show what the API actually returned
        st.info(f"**🔍 API Response Debug:**")
        st.write(f"- Requested: {vector_results_count} results")
        st.write(f"- Actually returned: {len(data['results'])} results")
        st.write(f"- Similarity threshold requested: {similarity_threshold}")
        
        # Add search target info to each result
        for result in data['results']:
            result['search_target'] = vector_name
            
        st.success(f"✅ **Found {len(data['results'])} code snippets** from {vector_name}")
        return {"results": data['results'], "search_target": vector_name, "success": True}

    except requests.exceptions.ConnectionError:
        st.error("❌ **Connection Error:** Could not reach vector search service at http://localhost:5000")
        return {"results": [], "search_target": vector_name, "success": False}
    except Exception as e:
        st.warning(f"⚠️ **Search Failed for {vector_name}:** {str(e)}")
        return {"results": [], "search_target": vector_name, "success": False}


def llm_json_parse(text_output, file_source="unknown"):
    """LLM-assisted JSON parsing - let the LLM fix malformed JSON"""
    if not text_output or not text_output.strip():
        return None, "Empty output from LLM"
    
    # First try direct JSON parsing
    try:
        return json.loads(text_output), None
    except json.JSONDecodeError:
        pass
    
    # Check if it's a "no information" response
    text_stripped = text_output.strip().lower()
    if ('no database' in text_stripped or 'no information found' in text_stripped):
        return None, "LLM indicated no database information found"
    
    # Use LLM to fix the JSON if it's malformed
    try:
        fix_prompt = f"""The following text should be valid JSON but has formatting issues. Please return ONLY the corrected JSON with no additional text or explanation:

{text_output}

Return only valid JSON:"""
        
        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
        payload = {
            "system_prompt": "You are a JSON formatting expert. Return only valid JSON, no explanations.",
            "user_prompt": fix_prompt,
            "codebase": ""
        }
        
        response = requests.post(url, json=payload, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            response_json = response.json()
            fixed_output = response_json.get('output', '')
            if fixed_output:
                try:
                    return json.loads(fixed_output), "Fixed by LLM"
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    
    return None, f"Could not parse JSON from: {text_output[:200]}..."


def extract_database_information_from_embeddings(data, system_prompt, vector_query):
    """Extract database information from existing vector embeddings"""
    st.subheader("🗄️ Database Information Extraction from Vector Embeddings")
    st.info(f"**Vector Search Query Used:** `{vector_query}`")
    st.info(f"**Files Found:** {len(data['results'])}")

    # Show similarity scores if available
    if data['results'] and 'similarity_score' in data['results'][0]:
        st.write("**🎯 Similarity Scores (Post-Filtering):**")
        scores = [float(result.get('similarity_score', 0)) for result in data['results']]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Best Match", f"{max(scores):.3f}")
        with col2:
            st.metric("Average", f"{sum(scores) / len(scores):.3f}")
        with col3:
            st.metric("Lowest", f"{min(scores):.3f}")
        with col4:
            st.metric("Results", len(scores))

    database_info_array = []

    for i, result in enumerate(data['results'], 1):
        try:
            similarity_info = ""
            if 'similarity_score' in result:
                score = float(result['similarity_score'])
                similarity_info = f" (Match #{i}, Similarity: {score:.3f})"

            search_target = result.get('search_target', 'Unknown Vector')
            st.markdown(f"### 📄 Processing Database Snippet {i}/{len(data['results'])}: `{result['metadata']['source']}`{similarity_info}")
            st.write(f"**🗄️ Source Vector:** `{search_target}`")

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
                with st.expander(f"📖 README Content - {file_source}", expanded=False):
                    st.markdown(codebase)
            except Exception:
                st.write(f"**Source:** {file_source} ({len(codebase)} chars)")

            if len(codebase) < 10:
                st.error("⚠️ Content is too short to process.")
                continue

            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"

            # Database information detection
            st.write("**🔍 Step 1: Detecting Database Information from README Content**")
            detection_prompt = """Given the provided README documentation content (which may contain database-focused information extracted from source code), identify if there are Couchbase or NoSQL database-related configurations, connections, queries, or data models present?

If none, reply back with 'no database information found'. 

If Couchbase/NoSQL database information is found, extract it and organize into a JSON structure with appropriate keys such as:
- database_type (should be "Couchbase" or other NoSQL type)
- cluster_connection (connection string, hosts, ports)
- bucket_names (Couchbase buckets)
- collection_names (collections within buckets)
- scope_names (scopes if used)
- n1ql_queries (N1QL query statements)
- document_types (types of JSON documents stored)
- indexes (GSI, primary indexes, etc.)
- sdk_operations (get, upsert, insert, replace operations)
- configurations (timeouts, security settings, etc.)

Focus specifically on Couchbase terminology: buckets, collections, scopes, documents, N1QL, GSI indexes, cluster, SDK operations.

Reply with only the JSON. Make sure it's a valid JSON."""

            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase
            }

            # Show detailed LLM API call information for debugging
            with st.expander(f"🔍 **Debug: Individual LLM API Call #{i}** - {os.path.basename(file_source)}", expanded=False):
                st.write("**🌐 Request URL:**")
                st.code(url, language="text")
                
                st.write("**📋 Request Headers:**")
                st.code(json.dumps(HEADERS, indent=2), language="json")
                
                st.write("**🎯 System Prompt Being Sent:**")
                st.text_area(f"System Prompt {i}", value=payload["system_prompt"], height=120, disabled=True, key=f"sys_prompt_individual_{i}")
                
                st.write("**💬 User Prompt Being Sent:**")
                st.text_area(f"User Prompt {i}", value=payload["user_prompt"], height=200, disabled=True, key=f"user_prompt_individual_{i}")
                
                st.write("**📄 Codebase Content Being Sent:**")
                st.write(f"**📊 Size:** {len(codebase):,} characters ({len(codebase)/1024:.1f} KB)")
                
                # Show first and last parts of codebase content
                if len(codebase) > 2000:
                    st.write("**📁 Codebase Content (First 1000 chars):**")
                    st.code(codebase[:1000] + "\n\n... [CONTENT CONTINUES] ...", language="text")
                    st.write("**📁 Codebase Content (Last 1000 chars):**")
                    st.code("... [CONTENT CONTINUES] ...\n\n" + codebase[-1000:], language="text")
                else:
                    st.write("**📁 Complete Codebase Content:**")
                    st.code(codebase, language="text")
                
                st.write("**🔧 Complete Request Payload:**")
                # Show truncated payload to avoid UI overload
                full_payload_str = json.dumps(payload, indent=2)
                if len(full_payload_str) > 3000:
                    st.code(full_payload_str[:1500] + "\n\n... [PAYLOAD CONTINUES] ...\n\n" + full_payload_str[-1500:], language="json")
                else:
                    st.code(full_payload_str, language="json")
                
                # Security analysis for this specific call
                st.write("**🚨 Security Analysis for This Call:**")
                payload_str = json.dumps(payload).lower()
                
                # Extended security terms that might trigger firewall
                security_terms = [
                    'password', 'secret', 'token', 'key', 'auth', 'credential', 'login',
                    'admin', 'root', 'sudo', 'exec', 'eval', 'shell', 'command',
                    'injection', 'xss', 'script', 'exploit', 'attack', 'hack',
                    'database', 'connection', 'query', 'select', 'insert', 'update', 'delete',
                    'api_key', 'access_token', 'bearer', 'oauth', 'jwt', 'session'
                ]
                
                found_terms = [term for term in security_terms if term in payload_str]
                
                if found_terms:
                    st.warning(f"⚠️ **Security-related terms found:** {', '.join(found_terms[:10])}{'...' if len(found_terms) > 10 else ''}")
                    st.write(f"**Total flagged terms:** {len(found_terms)}")
                else:
                    st.success("✅ **No obvious security terms detected**")
                
                # Payload size analysis
                payload_size = len(json.dumps(payload))
                if payload_size > 100000:  # 100KB
                    st.error(f"🚨 **Very large payload:** {payload_size:,} bytes - likely to be rejected")
                elif payload_size > 50000:  # 50KB
                    st.warning(f"⚠️ **Large payload:** {payload_size:,} bytes - may cause issues")
                else:
                    st.info(f"ℹ️ **Payload size:** {payload_size:,} bytes - should be fine")

            with st.spinner(f"🔄 Detecting database info in {file_source}..."):
                try:
                    response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

                    # Show detailed response for each individual LLM call
                    with st.expander(f"📡 **Debug: Individual LLM Response #{i}** - {os.path.basename(file_source)}", expanded=False):
                        st.write("**📡 Response Status:**")
                        st.code(f"HTTP {response.status_code}", language="text")
                        
                        st.write("**📋 Response Headers:**")
                        response_headers = dict(response.headers)
                        st.code(json.dumps(response_headers, indent=2), language="json")
                        
                        st.write("**📄 Raw Response Text:**")
                        response_text = response.text
                        if len(response_text) > 3000:
                            st.code(response_text[:1500] + "\n\n... [RESPONSE CONTINUES] ...\n\n" + response_text[-1500:], language="text")
                        else:
                            st.code(response_text, language="text")
                        
                        st.write("**📊 Response Analysis:**")
                        st.write(f"- **Size:** {len(response_text):,} characters ({len(response_text)/1024:.1f} KB)")
                        
                        # Try to parse and show JSON structure
                        try:
                            if response.status_code == 200:
                                response_json = response.json()
                                st.write("**🔧 Parsed Response JSON:**")
                                st.code(json.dumps(response_json, indent=2)[:2000] + "..." if len(json.dumps(response_json)) > 2000 else json.dumps(response_json, indent=2), language="json")
                                
                                # Show the actual LLM output if present
                                llm_output = response_json.get('output', '')
                                if llm_output:
                                    st.write("**🤖 LLM Output:**")
                                    st.code(llm_output[:1000] + "..." if len(llm_output) > 1000 else llm_output, language="text")
                        except json.JSONDecodeError:
                            st.warning("⚠️ **Response is not valid JSON**")
                        
                        # Firewall/security error detection
                        if response.status_code in [403, 404, 406, 451, 502, 503]:
                            st.error(f"🚨 **Security/Firewall Error:** HTTP {response.status_code}")
                            
                            # Look for specific firewall indicators in response
                            firewall_indicators = [
                                'blocked', 'forbidden', 'denied', 'rejected', 'firewall',
                                'security', 'policy', 'violation', 'restricted', 'filtered'
                            ]
                            
                            response_lower = response_text.lower()
                            found_indicators = [ind for ind in firewall_indicators if ind in response_lower]
                            
                            if found_indicators:
                                st.write(f"**🚨 Firewall indicators found:** {', '.join(found_indicators)}")
                            
                            # Check response headers for firewall info
                            firewall_headers = [h for h in response_headers.keys() if any(fw in h.lower() for fw in ['firewall', 'security', 'block', 'filter'])]
                            if firewall_headers:
                                st.write(f"**🚨 Security headers:** {firewall_headers}")

                    if response.status_code == 404:
                        st.error("❌ **404 Error: Request blocked by firewall**")
                        continue

                    elif response.status_code != 200:
                        st.error(f"❌ **HTTP {response.status_code} Error:** {response.text}")
                        continue

                    try:
                        response_json = response.json()
                    except json.JSONDecodeError:
                        st.error(f"❌ **Invalid JSON Response:** Could not parse response")
                        continue

                    status_code = response_json.get('status_code', response.status_code)
                    output = response_json.get('output') or ''

                    if status_code != 200:
                        st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
                        continue

                    # Check if no database information found
                    output_stripped = output.strip().lower()
                    if ('no database' in output_stripped or 'no information found' in output_stripped):
                        st.warning("⚠️ **No database information found in this README**")
                        continue

                    # Parse JSON response using LLM assistance
                    json_document, parse_error = llm_json_parse(output, file_source)
                    
                    if json_document is None:
                        if "no database information found" in parse_error:
                            st.warning("⚠️ **No database information found in this README**")
                        else:
                            st.error(f"❌ **JSON Parsing Failed:** {parse_error}")
                        continue
                    
                    if parse_error:
                        st.warning(f"⚠️ **JSON Parsing Warning:** {parse_error}")
                        st.success("✅ **Database information detected (with parsing assistance)!**")
                    else:
                        st.success("✅ **Database information detected from README embeddings!**")
                    
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


def llm_transform_database_data_with_retries(db_info_list, all_vector_results, system_prompt, max_retries=3):
    """Use LLM to transform extracted database data with retries and error handling"""
    st.write("🏗️ **Using LLM to build final database structure from extracted data...**")
    
    if not db_info_list:
        st.warning("⚠️ **No database information to process**")
        return {"Database Information": {}}
    
    st.info(f"**🔢 Processing {len(db_info_list)} extracted database entries using LLM transformation**")
    
    # Save progress to session state to prevent data loss
    progress_key = "llm_transform_progress"
    if progress_key not in st.session_state:
        st.session_state[progress_key] = {
            "db_info_list": db_info_list,
            "all_vector_results": all_vector_results,
            "timestamp": datetime.now().isoformat()
        }
    
    # Combine all extracted data for LLM processing
    combined_data = {
        "extracted_entries": db_info_list,
        "source_files": []
    }
    
    # Add source file information
    for i, result in enumerate(all_vector_results):
        if i < len(db_info_list):
            combined_data["source_files"].append({
                "index": i,
                "source": result.get('metadata', {}).get('source', f'unknown_{i}'),
                "similarity_score": result.get('similarity_score', 0)
            })
    
    # Use LLM to structure the final output
    transformation_prompt = """Given the extracted Couchbase/NoSQL database information below, create a comprehensive final database specification. 

ONLY include information that was actually found in the extracted data. Do not add placeholder or dummy data.

Structure the output as JSON with these sections:
1. "Buckets_and_Collections": Only list actual bucket and collection names found
2. "Queries": Only include actual N1QL/SQL queries found  
3. "Document_Types": Only include actual document types/schemas found
4. "Indexes": Only include actual index information found
5. "SDK_Operations": Only include actual SDK operations found
6. "Connection_Details": Only include actual connection information found

If a section has no actual data, omit it entirely or set it to an empty array/object.

Extracted data to process:"""
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                st.info(f"🔄 **Retry attempt {attempt + 1}/{max_retries}** (waiting {wait_time}s before retry)")
                import time
                time.sleep(wait_time)
            
            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
            
            # Split data if it's too large (might cause API errors)
            data_str = json.dumps(combined_data, indent=2)
            if len(data_str) > 50000:  # If data is very large
                st.warning(f"⚠️ **Large dataset detected** ({len(data_str)} chars) - using chunked processing")
                return llm_transform_chunked_data(db_info_list, all_vector_results, system_prompt)
            
            payload = {
                "system_prompt": system_prompt + " Focus on creating accurate final output with only real extracted data.",
                "user_prompt": transformation_prompt,
                "codebase": data_str
            }
            
            # Show detailed request information for debugging
            with st.expander(f"🔍 **Debug: Final Transformation Request Details** (Attempt {attempt + 1})", expanded=False):
                st.write("**🌐 Request URL:**")
                st.code(url, language="text")
                
                st.write("**📋 Request Headers:**")
                st.code(json.dumps(HEADERS, indent=2), language="json")
                
                st.write("**🎯 System Prompt:**")
                st.text_area("System Prompt", value=payload["system_prompt"], height=100, disabled=True, key=f"sys_prompt_{attempt}")
                
                st.write("**💬 User Prompt:**")
                st.text_area("User Prompt", value=payload["user_prompt"], height=150, disabled=True, key=f"user_prompt_{attempt}")
                
                st.write("**📊 Codebase Data Size:**")
                st.write(f"- **Characters:** {len(data_str):,}")
                st.write(f"- **KB:** {len(data_str)/1024:.1f}")
                st.write(f"- **MB:** {len(data_str)/(1024*1024):.2f}")
                
                st.write("**📁 Codebase Data Preview (First 1000 chars):**")
                st.code(data_str[:1000] + "..." if len(data_str) > 1000 else data_str, language="json")
                
                st.write("**🔧 Full Request Payload:**")
                st.code(json.dumps(payload, indent=2)[:2000] + "..." if len(json.dumps(payload)) > 2000 else json.dumps(payload, indent=2), language="json")
                
                # Potential firewall triggers
                st.write("**🚨 Potential Firewall Triggers to Check:**")
                suspicious_terms = []
                payload_str = json.dumps(payload).lower()
                
                # Check for terms that might trigger security filters
                security_terms = [
                    'password', 'secret', 'token', 'key', 'auth', 'credential',
                    'admin', 'root', 'sudo', 'exec', 'eval', 'shell',
                    'injection', 'xss', 'script', 'exploit'
                ]
                
                for term in security_terms:
                    if term in payload_str:
                        suspicious_terms.append(term)
                
                if suspicious_terms:
                    st.warning(f"⚠️ **Found potentially flagged terms:** {', '.join(suspicious_terms)}")
                else:
                    st.success("✅ **No obvious security-related terms detected**")
                
                # Request size warnings
                payload_size = len(json.dumps(payload))
                if payload_size > 100000:  # 100KB
                    st.error(f"🚨 **Large payload detected:** {payload_size:,} bytes - may exceed firewall limits")
                elif payload_size > 50000:  # 50KB
                    st.warning(f"⚠️ **Medium payload size:** {payload_size:,} bytes - monitor for limits")
                else:
                    st.info(f"ℹ️ **Payload size:** {payload_size:,} bytes")
            
            # Increased timeout for large datasets
            timeout = 600 if len(db_info_list) > 20 else 300
            
            with st.spinner(f"🔄 LLM is structuring the final database specification... (Attempt {attempt + 1}/{max_retries})"):
                response = requests.post(url, json=payload, headers=HEADERS, timeout=timeout)
            
            # Show detailed response information for debugging
            with st.expander(f"🔍 **Debug: API Response Details** (Attempt {attempt + 1})", expanded=False):
                st.write("**📡 Response Status:**")
                st.code(f"HTTP {response.status_code}", language="text")
                
                st.write("**📋 Response Headers:**")
                st.code(json.dumps(dict(response.headers), indent=2), language="json")
                
                st.write("**📄 Raw Response Text (First 2000 chars):**")
                response_text = response.text
                st.code(response_text[:2000] + "..." if len(response_text) > 2000 else response_text, language="text")
                
                st.write("**📊 Response Size:**")
                st.write(f"- **Characters:** {len(response_text):,}")
                st.write(f"- **KB:** {len(response_text)/1024:.1f}")
                
                # Try to parse response as JSON for better display
                try:
                    response_json = response.json()
                    st.write("**🔧 Parsed JSON Response:**")
                    st.code(json.dumps(response_json, indent=2)[:2000] + "..." if len(json.dumps(response_json)) > 2000 else json.dumps(response_json, indent=2), language="json")
                except:
                    st.write("**⚠️ Response is not valid JSON**")
                
                # Check for firewall-specific error messages
                if response.status_code in [403, 406, 451, 502, 503]:
                    st.error(f"🚨 **Firewall/Security Error Detected:** HTTP {response.status_code}")
                    st.write("**Common causes:**")
                    st.write("- Content contains flagged keywords")
                    st.write("- Payload size exceeds limits")
                    st.write("- Request rate limiting")
                    st.write("- Security policy violation")
            
            if response.status_code == 200:
                response_json = response.json()
                output = response_json.get('output', '')
                
                if output:
                    # Parse the LLM response
                    final_structure, parse_error = llm_json_parse(output, "final_transformation")
                    
                    if final_structure:
                        st.success("✅ **LLM successfully structured the final database specification**")
                        
                        # Clear progress since we succeeded
                        if progress_key in st.session_state:
                            del st.session_state[progress_key]
                        
                        # Display what was actually found
                        for section, data in final_structure.items():
                            if data:  # Only show sections with actual data
                                st.write(f"**📋 {section.replace('_', ' ')}:** Found actual data")
                                try:
                                    if isinstance(data, list) and len(data) > 0:
                                        st.write(f"- {len(data)} items found")
                                    elif isinstance(data, dict) and len(data) > 0:
                                        st.write(f"- {len(data)} entries found")
                                except:
                                    pass
                        
                        return {"Database Information": final_structure}
                    else:
                        if attempt == max_retries - 1:  # Last attempt
                            st.error(f"❌ **LLM transformation failed after {max_retries} attempts:** {parse_error}")
                            return create_fallback_structure(db_info_list)
                        else:
                            st.warning(f"⚠️ **Parse error on attempt {attempt + 1}:** {parse_error} - Retrying...")
                            continue
                else:
                    if attempt == max_retries - 1:
                        st.error("❌ **No output from LLM transformation after all retries**")
                        return create_fallback_structure(db_info_list)
                    else:
                        st.warning(f"⚠️ **No output on attempt {attempt + 1}** - Retrying...")
                        continue
                        
            elif response.status_code == 429:  # Rate limit
                if attempt == max_retries - 1:
                    st.error("❌ **Rate limited after all retries**")
                    return create_fallback_structure(db_info_list)
                else:
                    st.warning(f"⚠️ **Rate limited on attempt {attempt + 1}** - Will retry with longer backoff...")
                    import time
                    time.sleep(10)  # Extra wait for rate limits
                    continue
                    
            else:
                if attempt == max_retries - 1:
                    st.error(f"❌ **LLM API error after {max_retries} attempts:** HTTP {response.status_code}")
                    st.error(f"**Response:** {response.text}")
                    return create_fallback_structure(db_info_list)
                else:
                    st.warning(f"⚠️ **API error on attempt {attempt + 1}:** HTTP {response.status_code} - Retrying...")
                    continue
                    
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                st.error(f"❌ **Request timeout after {max_retries} attempts**")
                return create_fallback_structure(db_info_list)
            else:
                st.warning(f"⚠️ **Timeout on attempt {attempt + 1}** - Retrying...")
                continue
                
        except requests.exceptions.ConnectionError:
            if attempt == max_retries - 1:
                st.error(f"❌ **Connection error after {max_retries} attempts**")
                return create_fallback_structure(db_info_list)
            else:
                st.warning(f"⚠️ **Connection error on attempt {attempt + 1}** - Retrying...")
                continue
                
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"❌ **Exception after {max_retries} attempts:** {str(e)}")
                return create_fallback_structure(db_info_list)
            else:
                st.warning(f"⚠️ **Exception on attempt {attempt + 1}:** {str(e)} - Retrying...")
                continue
    
    # Should never reach here, but just in case
    return create_fallback_structure(db_info_list)


def create_fallback_structure(db_info_list):
    """Create a fallback structure when LLM transformation fails"""
    st.warning("🛡️ **Using fallback structure generation** - preserving extracted data without LLM transformation")
    
    fallback_structure = {
        "Raw_Extracted_Data": db_info_list,
        "Extraction_Status": "LLM transformation failed, raw data preserved",
        "Timestamp": datetime.now().isoformat(),
        "Note": "Manual review required - LLM transformation could not complete"
    }
    
    # Try to extract some basic info without LLM
    buckets = []
    queries = []
    
    for entry in db_info_list:
        if isinstance(entry, dict):
            for key, value in entry.items():
                if 'bucket' in key.lower() and isinstance(value, (str, list)):
                    if isinstance(value, list):
                        buckets.extend(value)
                    else:
                        buckets.append(value)
                        
                if any(q_word in str(value).lower() for q_word in ['select', 'insert', 'n1ql', 'query']) and len(str(value)) > 10:
                    queries.append(str(value))
    
    if buckets:
        fallback_structure["Buckets_Found"] = list(set(buckets))
    if queries:
        fallback_structure["Queries_Found"] = queries
    
    return {"Database Information": fallback_structure}


def llm_transform_chunked_data(db_info_list, all_vector_results, system_prompt):
    """Handle very large datasets by processing in chunks"""
    st.info("🔄 **Processing large dataset in chunks to avoid API limits**")
    
    chunk_size = 10  # Process 10 entries at a time
    chunks = [db_info_list[i:i + chunk_size] for i in range(0, len(db_info_list), chunk_size)]
    
    final_results = {
        "Buckets_and_Collections": [],
        "Queries": [],
        "Document_Types": [],
        "Indexes": [],
        "SDK_Operations": [],
        "Connection_Details": []
    }
    
    for i, chunk in enumerate(chunks, 1):
        st.info(f"📦 **Processing chunk {i}/{len(chunks)}** ({len(chunk)} entries)")
        
        # Process this chunk
        chunk_results = llm_transform_database_data_with_retries(chunk, all_vector_results[:(len(chunk))], system_prompt, max_retries=2)
        
        # Merge results
        if "Database Information" in chunk_results:
            chunk_data = chunk_results["Database Information"]
            for section, data in chunk_data.items():
                if section in final_results and data:
                    if isinstance(data, list):
                        final_results[section].extend(data)
                    elif isinstance(data, dict):
                        if isinstance(final_results[section], list):
                            final_results[section].append(data)
                        elif isinstance(final_results[section], dict):
                            final_results[section].update(data)
    
    # Remove empty sections
    final_results = {k: v for k, v in final_results.items() if v}
    
    return {"Database Information": final_results}


def commit_json_to_github(vector_name, json_data):
    """GitHub integration for committing results"""
    st.subheader("📤 GitHub Integration")
    
    st.write("**📋 Data to be pushed to GitHub:**")
    with st.expander("📄 View JSON Data", expanded=False):
        st.code(json.dumps(json_data, indent=2), language="json")
    st.write(f"**📊 Data size:** {len(json.dumps(json_data))} characters")
    
    st.text(commit_json(vector_name, json_data))


def main():
    st.set_page_config(
        page_title="New Database Extraction from Vector Embeddings",
        page_icon="🆕",
        layout="wide"
    )

    st.title("🆕 Couchbase Database Extraction from README Vector Embeddings")
    st.markdown("**Extract Couchbase/NoSQL database information from existing vector embeddings created via the Codebase → LLM → README → Vector flow**")

    st.info("💡 **This tool is optimized for Couchbase databases and works with vector embeddings that were already created from README documentation generated by LLMs from your codebase.**")

    with st.form("vector_database_extraction_form"):
        col1, col2 = st.columns(2)

        with col1:
            vector_name = st.text_input(
                "🗂️ Vector Database Name:",
                placeholder="my-project-readme-embeddings",
                help="Name of the existing vector database containing README embeddings"
            )
            
            database_system_prompt = st.text_area(
                "🗄️ Database System Prompt:",
                value=DEFAULT_DATABASE_SYSTEM_PROMPT,
                height=100,
                help="Instructions for database extraction from README content"
            )

            database_vector_query = st.text_input(
                "🔍 Database Vector Query:",
                value=DEFAULT_DATABASE_VECTOR_QUERY,
                help="Query used to find database-related README content"
            )

        with col2:
            vector_results_count = st.number_input(
                '📊 Max Results Count:',
                value=50,
                min_value=1,
                max_value=1000,
                help="Maximum number of results from vector search (set to 1000 for whole codebase)"
            )
            
            similarity_threshold = st.slider(
                '🎯 Similarity Threshold:',
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                help="Filter out results below this similarity score (lower = more comprehensive)"
            )
            
            process_whole_codebase = st.checkbox(
                "🌐 Process Whole Codebase",
                value=False,
                help="Process all available vector results (sets count to 1000 and threshold to 0.1)"
            )

        st.info("🔄 **Enhanced LLM Workflow:** Search Vector Embeddings → LLM Extracts Data → LLM Structures Final Spec")
        
        if process_whole_codebase:
            st.warning("⚡ **Whole Codebase Mode:** This will process many files and may take longer but provides comprehensive coverage")

        submit_button = st.form_submit_button(
            '🚀 Start Database Extraction from Vector Embeddings',
            use_container_width=True
        )

    # Check for saved progress
    progress_key = "llm_transform_progress"
    if progress_key in st.session_state:
        st.warning("⚠️ **Previous session data found** - you can recover from a previous run that may have failed")
        if st.button("🔄 Use Saved Progress"):
            st.info("Using saved database extraction data...")
            saved_data = st.session_state[progress_key]
            final_database_info = llm_transform_database_data_with_retries(
                saved_data["db_info_list"], 
                saved_data["all_vector_results"], 
                database_system_prompt
            )
            if final_database_info:
                st.json(final_database_info)
        if st.button("🗑️ Clear Saved Progress"):
            del st.session_state[progress_key]
            st.success("Saved progress cleared")
            st.rerun()

    if submit_button:
        if not vector_name:
            st.error("❌ Please enter a vector database name")
        else:
            try:
                st.markdown("---")
                st.header("🔄 Database Extraction from README Vector Embeddings")

                # Step 1: Vector search on existing embeddings
                st.subheader("🔍 Step 1: Vector Search on README Embeddings")
                
                # Adjust parameters for whole codebase processing
                if process_whole_codebase:
                    st.info("🌐 **Whole codebase processing enabled** - using expanded search parameters")
                    vector_results_count = 1000
                    similarity_threshold = 0.1
                    st.write(f"**Adjusted parameters:** Count: {vector_results_count}, Threshold: {similarity_threshold}")
                
                # Debug: Show what parameters are actually being used
                st.info(f"**🔍 Search Parameters Being Sent:**")
                st.write(f"- Vector Name: `{vector_name}`")
                st.write(f"- Query: `{database_vector_query}`") 
                st.write(f"- Results Count: `{vector_results_count}`")
                st.write(f"- Similarity Threshold: `{similarity_threshold}`")
                st.write(f"- Whole Codebase Mode: `{process_whole_codebase}`")
                
                database_data = vector_search_single(vector_name, database_vector_query, vector_results_count, similarity_threshold)
                
                if database_data and database_data['results']:
                    # Step 2: Extract database information
                    st.subheader("🗄️ Step 2: Database Information Extraction")
                    
                    database_information = extract_database_information_from_embeddings(
                        database_data, database_system_prompt, database_vector_query
                    )
                    
                    if database_information:
                        # Step 3: LLM-based final structure generation with retries
                        st.subheader("🏗️ Step 3: LLM-Based Final Structure Generation")
                        
                        # Display LLM request details as prominently requested
                        with st.expander("🔍 **LLM Request Details** - System Prompt, User Prompt & Code Snippet", expanded=False):
                            st.write("**What does application metadata do?**")
                            st.info("""
                            **Application Metadata** fetches application details from the backend including:
                            - **Information**: Application Name, Type, Central ID, Company Platform, Tech Platform
                            - **Architecture**: Target Production Environment, Hosting Environment, Internet Facing status
                            - **Risk**: Data Classification
                            - **Regulatory**: SDE/PII information based on data classification
                            
                            This metadata provides context about the application that the database belongs to, helping with compliance and architectural understanding.
                            """)
                            
                            st.write("---")
                            st.write("**📋 LLM Request Information for Final Structure Generation:**")
                            
                            # Show what will be sent to the LLM
                            combined_data = {
                                "extracted_entries": database_information,
                                "source_files": []
                            }
                            
                            # Add source file information
                            for i, result in enumerate(database_data['results']):
                                if i < len(database_information):
                                    combined_data["source_files"].append({
                                        "index": i,
                                        "source": result.get('metadata', {}).get('source', f'unknown_{i}'),
                                        "similarity_score": result.get('similarity_score', 0)
                                    })
                            
                            data_str = json.dumps(combined_data, indent=2)
                            
                            transformation_prompt = """Given the extracted Couchbase/NoSQL database information below, create a comprehensive final database specification. 

ONLY include information that was actually found in the extracted data. Do not add placeholder or dummy data.

Structure the output as JSON with these sections:
1. "Buckets_and_Collections": Only list actual bucket and collection names found
2. "Queries": Only include actual N1QL/SQL queries found  
3. "Document_Types": Only include actual document types/schemas found
4. "Indexes": Only include actual index information found
5. "SDK_Operations": Only include actual SDK operations found
6. "Connection_Details": Only include actual connection information found

If a section has no actual data, omit it entirely or set it to an empty array/object.

Extracted data to process:"""
                            
                            st.write("**🎯 System Prompt:**")
                            st.text_area(
                                "System Prompt", 
                                value=database_system_prompt + " Focus on creating accurate final output with only real extracted data.",
                                height=120, 
                                disabled=True, 
                                key="step3_system_prompt"
                            )
                            
                            st.write("**💬 User Prompt:**")
                            st.text_area(
                                "User Prompt", 
                                value=transformation_prompt,
                                height=200, 
                                disabled=True, 
                                key="step3_user_prompt"
                            )
                            
                            st.write("**📄 Code Snippet/Data Being Sent:**")
                            st.write(f"**📊 Data Size:** {len(data_str):,} characters ({len(data_str)/1024:.1f} KB)")
                            
                            if len(data_str) > 2000:
                                st.write("**📁 Code Snippet (First 1000 chars):**")
                                st.code(data_str[:1000] + "\n\n... [CONTENT CONTINUES] ...", language="json")
                                st.write("**📁 Code Snippet (Last 1000 chars):**")
                                st.code("... [CONTENT CONTINUES] ...\n\n" + data_str[-1000:], language="json")
                            else:
                                st.write("**📁 Complete Code Snippet:**")
                                st.code(data_str, language="json")
                            
                            # Show potential issues
                            st.write("**⚠️ AI_FIREWALL_SRE Issue Analysis:**")
                            payload_str = data_str.lower()
                            
                            security_terms = [
                                'password', 'secret', 'token', 'key', 'auth', 'credential',
                                'admin', 'root', 'sudo', 'exec', 'eval', 'shell',
                                'injection', 'xss', 'script', 'exploit', 'attack'
                            ]
                            
                            found_terms = [term for term in security_terms if term in payload_str]
                            
                            if found_terms:
                                st.warning(f"🚨 **Potential firewall triggers found:** {', '.join(found_terms)}")
                                st.write("These terms might trigger AI_FIREWALL_SRE blocking.")
                            else:
                                st.success("✅ **No obvious security-related terms detected**")
                            
                            payload_size = len(data_str)
                            if payload_size > 100000:  # 100KB
                                st.error(f"🚨 **Large payload:** {payload_size:,} bytes - may exceed firewall limits")
                            elif payload_size > 50000:  # 50KB
                                st.warning(f"⚠️ **Medium payload:** {payload_size:,} bytes - monitor for limits")
                            else:
                                st.info(f"ℹ️ **Payload size:** {payload_size:,} bytes - should be acceptable")
                        
                        final_database_info = llm_transform_database_data_with_retries(
                            database_information, database_data['results'], database_system_prompt
                        )
                        
                        # Prepare final results with only actual data
                        final_results = {
                            "extraction_metadata": {
                                "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "vector_database": vector_name,
                                "extraction_type": "llm_based_couchbase_extraction",
                                "vector_results_processed": len(database_data['results']),
                                "database_entries_extracted": len(database_information),
                                "whole_codebase_processed": process_whole_codebase,
                                "similarity_threshold_used": similarity_threshold
                            },
                            **final_database_info  # Merge the LLM-generated database info directly
                        }
                        
                        # Step 5: Display results
                        st.header("🎯 Final Database Extraction Results")
                        st.json(final_results)
                        
                        # Download and commit options
                        col1, col2 = st.columns(2)
                        with col1:
                            results_json = json.dumps(final_results, indent=2)
                            st.download_button(
                                label="📥 Download Results JSON",
                                data=results_json,
                                file_name=f"db_extraction_{vector_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )

                        with col2:
                            # GitHub integration
                            if st.button("📤 Commit to GitHub"):
                                commit_json_to_github(vector_name, final_results)
                        
                        st.success("🎉 Database extraction from README vector embeddings completed successfully!")
                        st.balloons()
                        
                    else:
                        st.warning("⚠️ **No database information could be extracted from the README embeddings**")
                        
                else:
                    st.warning("⚠️ **No results found in the vector database. Please check:**")
                    st.write("- Vector database name is correct")
                    st.write("- Vector database exists and contains README embeddings")
                    st.write("- Vector search service is running")
                    st.write("- Try adjusting the similarity threshold or search query")

            except Exception as e:
                st.error(f"❌ **Extraction failed:** {str(e)}")


if __name__ == "__main__":
    main()