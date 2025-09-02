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

            with st.spinner(f"🔄 Detecting database info in {file_source}..."):
                try:
                    response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

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


def llm_transform_database_data(db_info_list, all_vector_results, system_prompt):
    """Use LLM to transform extracted database data into final structured format"""
    st.write("🏗️ **Using LLM to build final database structure from extracted data...**")
    
    if not db_info_list:
        st.warning("⚠️ **No database information to process**")
        return {"Database Information": {}}
    
    st.info(f"**🔢 Processing {len(db_info_list)} extracted database entries using LLM transformation**")
    
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
    
    try:
        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
        payload = {
            "system_prompt": system_prompt + " Focus on creating accurate final output with only real extracted data.",
            "user_prompt": transformation_prompt,
            "codebase": json.dumps(combined_data, indent=2)
        }
        
        with st.spinner("🔄 LLM is structuring the final database specification..."):
            response = requests.post(url, json=payload, headers=HEADERS, timeout=300)
        
        if response.status_code == 200:
            response_json = response.json()
            output = response_json.get('output', '')
            
            if output:
                # Parse the LLM response
                final_structure, parse_error = llm_json_parse(output, "final_transformation")
                
                if final_structure:
                    st.success("✅ **LLM successfully structured the final database specification**")
                    
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
                    st.error(f"❌ **LLM transformation failed:** {parse_error}")
                    return {"Database Information": {"error": "LLM transformation failed"}}
            else:
                st.error("❌ **No output from LLM transformation**")
                return {"Database Information": {"error": "No LLM output"}}
        else:
            st.error(f"❌ **LLM API error:** HTTP {response.status_code}")
            return {"Database Information": {"error": f"HTTP {response.status_code}"}}
            
    except Exception as e:
        st.error(f"❌ **Exception during LLM transformation:** {str(e)}")
        return {"Database Information": {"error": str(e)}}


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
                
                database_data = vector_search_single(vector_name, database_vector_query, vector_results_count, similarity_threshold)
                
                if database_data and database_data['results']:
                    # Step 2: Extract database information
                    st.subheader("🗄️ Step 2: Database Information Extraction")
                    
                    database_information = extract_database_information_from_embeddings(
                        database_data, database_system_prompt, database_vector_query
                    )
                    
                    if database_information:
                        # Step 3: LLM-based final structure generation
                        st.subheader("🏗️ Step 3: LLM-Based Final Structure Generation")
                        final_database_info = llm_transform_database_data(
                            database_information, database_data['results'], database_system_prompt
                        )
                        
                        # Get application metadata (try using the vector name as codebase)
                        st.subheader("🚗 Step 4: Application Metadata")
                        try:
                            # Try to extract metadata using the vector name (removing any suffixes)
                            base_name = vector_name.replace('-readme-embeddings', '').replace('-embeddings', '')
                            metadata = fetch_metadata(base_name)
                            if metadata is None:
                                metadata = {"note": f"No metadata found for {base_name}"}
                                st.warning("⚠️ **No application metadata found**")
                            else:
                                st.success("✅ **Application metadata extracted!**")
                                st.json(metadata)
                        except Exception as e:
                            metadata = {"error": f"Metadata extraction failed: {str(e)}"}
                            st.error(f"❌ **Metadata extraction failed:** {str(e)}")
                        
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
                            "Application": metadata,
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