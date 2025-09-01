import streamlit as st
import requests
import json
import os
import sys
from datetime import datetime

sys.path.append('../genai-python-poc')
from utils.githubUtil import commit_json
from utils.metadataUtil import fetch_metadata
from genai_python_poc.utilities.github_utils import clone_repo, delete_repo

# Configuration
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
VECTOR_SEARCH_ENDPOINT = "/vector-search"
HEADERS = {"Content-Type": "application/json"}

# README conversion prompt
README_CONVERSION_PROMPT = """Create a concise readme for this source code. Create an overall summary, and add sections to identify databases used SQL Queries, and for external interfaces and APIs. If information is not there in code your output should say no information found."""

# Initialize session state
if 'new_flow_logs' not in st.session_state:
    st.session_state['new_flow_logs'] = []

def log_error(error_type, status_code, response_text, step_name, timestamp):
    """Log errors for debugging"""
    log_entry = {
        "timestamp": timestamp,
        "error_type": error_type,
        "status_code": status_code,
        "response_text": str(response_text)[:1000],  # Truncate long responses
        "step_name": step_name
    }
    st.session_state['new_flow_logs'].append(log_entry)

def call_llm(system_prompt, user_prompt, content, step_name):
    """Generic LLM call function"""
    url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    payload = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "codebase": content
    }
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=300)
        
        if response.status_code != 200:
            st.error(f"❌ **HTTP {response.status_code} Error:** {response.text}")
            log_error(f"http_{response.status_code}", response.status_code, response.text, step_name, timestamp)
            return None
        
        try:
            response_json = response.json()
        except json.JSONDecodeError:
            st.error("❌ **Invalid JSON Response:** Could not parse response")
            return None
        
        status_code = response_json.get('status_code', response.status_code)
        output = response_json.get('output') or ''
        
        if status_code != 200:
            st.warning(f"⚠️ **LLM API {status_code} - Filtered/Blocked:** {response_json.get('output', 'Unknown error')}")
            return None
        
        return output
        
    except requests.exceptions.ConnectionError:
        st.error("❌ **Connection Error:** Could not reach LLM service")
        return None
    except Exception as e:
        st.error(f"❌ **Unexpected Error:** {str(e)}")
        log_error("llm_call_error", None, str(e), step_name, timestamp)
        return None

def get_codebase_files_from_git(codebase_name, max_files=5):
    """Get files from the codebase by cloning from git and scanning actual files"""
    st.write(f"**📁 Step 1: Getting {max_files} files from git repository**")
    
    # Try to clone and scan actual files
    with st.spinner("🔄 Cloning repository and scanning for code files..."):
        success = clone_repo(codebase_name)
        
        if success:
            st.success("✅ Repository cloned successfully!")
            
            # Scan for all code files in the repository
            all_file_paths = []
            file_extensions = ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', '.sql', '.yaml', '.yml', '.json', '.go', '.rs', '.php', '.rb', '.cs']
            
            for root, dirs, files in os.walk("."):
                # Skip hidden directories and common non-code directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', 'env', 'build', 'dist', 'target']]
                
                for file in files:
                    if any(file.endswith(ext) for ext in file_extensions):
                        relative_path = os.path.relpath(os.path.join(root, file), ".")
                        # Skip very large files and test files for initial processing
                        try:
                            file_size = os.path.getsize(os.path.join(root, file))
                            if file_size < 50000 and not any(skip in relative_path.lower() for skip in ['test_', '_test', '.test.', 'spec.', '.spec.']):  # Skip files larger than 50KB and test files
                                all_file_paths.append(relative_path)
                        except:
                            continue
            
            total_files = len(all_file_paths)
            st.info(f"**📂 Found {total_files} code files in repository (excluding tests and large files)**")
            
            # Select files to process (first N files)
            selected_files = all_file_paths[:max_files] if all_file_paths else []
            
            if not selected_files:
                st.warning("⚠️ No suitable code files found in repository")
                delete_repo(codebase_name)
                return []
            
            st.info(f"**📄 Selected {len(selected_files)} files for processing:**")
            for i, file in enumerate(selected_files, 1):
                st.text(f"{i}. {file}")
            
            # Read selected files from local filesystem
            all_files = []
            for file_path in selected_files:
                try:
                    full_path = os.path.join(".", file_path)
                    if os.path.exists(full_path):
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Skip empty files
                        if len(content.strip()) > 100:  # Only process files with substantial content
                            file_data = {
                                'metadata': {'source': file_path},
                                'page_content': content,
                                'similarity_score': 1.0  # Perfect match since we selected these files
                            }
                            all_files.append(file_data)
                            st.success(f"✅ Read file: {file_path} ({len(content)} chars)")
                        else:
                            st.info(f"ℹ️ Skipped empty/small file: {file_path}")
                    else:
                        st.warning(f"⚠️ File not found: {file_path}")
                except Exception as e:
                    st.error(f"❌ Error reading {file_path}: {str(e)}")
            
            # Clean up cloned repository
            delete_repo(codebase_name)
            st.info("🧹 Cleaned up cloned repository")
            
            if all_files:
                st.success(f"✅ **Retrieved {len(all_files)} files from git repository '{codebase_name}'** (out of {total_files} total files)")
                return all_files
            else:
                st.error("❌ **No files could be read from the repository**")
                return []
        else:
            st.error("❌ **Failed to clone repository - falling back to vector search**")
            return get_codebase_files_vector_search(codebase_name, max_files)

def get_codebase_files_vector_search(codebase_name, max_files=5):
    """Get files from the codebase using vector search (fallback method)"""
    st.write("**📁 Using vector search as fallback**")
    
    url = f"{LOCAL_BACKEND_URL}{VECTOR_SEARCH_ENDPOINT}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Search for diverse file types
    search_queries = [
        "database connection config",
        "api endpoint service", 
        "main application logic",
        "model schema table",
        "controller handler"
    ]
    
    all_files = []
    
    for query in search_queries:
        payload = {
            "codebase": codebase_name,
            "query": query,
            "vector_results_count": 2,  # Get 2 files per query type
            "similarity_threshold": 0.3
        }
        
        with st.spinner(f"🔄 Searching for files with query: '{query}'..."):
            try:
                response = requests.post(url, json=payload, headers=HEADERS, timeout=60)
                
                if response.status_code == 200:
                    response_json = response.json()
                    results = response_json.get('results', [])
                    
                    for result in results:
                        # Avoid duplicates
                        file_path = result.get('metadata', {}).get('source', '')
                        if not any(f.get('metadata', {}).get('source', '') == file_path for f in all_files):
                            all_files.append(result)
                            if len(all_files) >= max_files:
                                break
                    
                    if results:
                        st.success(f"✅ Found {len(results)} files for query '{query}'")
                    else:
                        st.info(f"ℹ️ No files found for query '{query}'")
                else:
                    st.warning(f"⚠️ Search failed for query '{query}': HTTP {response.status_code}")
                    
            except Exception as e:
                st.error(f"❌ Error searching with query '{query}': {str(e)}")
                log_error("file_search_error", None, str(e), f"File Search - {query}", timestamp)
        
        if len(all_files) >= max_files:
            break
    
    if all_files:
        st.success(f"✅ **Retrieved {len(all_files)} files from codebase '{codebase_name}'**")
        return all_files[:max_files]  # Limit to max_files
    else:
        st.error(f"❌ **No files found in codebase '{codebase_name}'**")
        return []

def get_codebase_files(codebase_name, max_files=5, use_git=True):
    """Get files from the codebase - either from git or vector search"""
    if use_git:
        return get_codebase_files_from_git(codebase_name, max_files)
    else:
        return get_codebase_files_vector_search(codebase_name, max_files)

def convert_code_to_readme(code_snippet, file_source):
    """Convert code snippet to README format using LLM"""
    with st.spinner(f"🔄 Converting {file_source} to README format..."):
        readme_content = call_llm(
            system_prompt="You are an expert technical writer who creates clear, concise documentation from source code.",
            user_prompt=README_CONVERSION_PROMPT,
            content=code_snippet,
            step_name=f"README Conversion - {file_source}"
        )
        
        if readme_content:
            return readme_content
        else:
            return None

def process_files_to_readme(files):
    """Process multiple files and convert each to README format"""
    st.write("**📝 Step 2: Converting files to README format**")
    
    readme_outputs = []
    
    for i, file_data in enumerate(files, 1):
        file_source = file_data.get('metadata', {}).get('source', f'file_{i}')
        code_content = file_data.get('page_content', '')
        similarity = file_data.get('similarity_score', 0)
        
        st.markdown(f"### 📄 Processing File {i}/{len(files)}: `{file_source}`")
        st.write(f"**🎯 Similarity Score:** {similarity:.3f}")
        st.write(f"**📊 Content Length:** {len(code_content)} characters")
        
        # Display original code
        with st.expander(f"📖 Original Code - {file_source}", expanded=False):
            st.code(code_content, language="text")
        
        # Convert to README
        readme_content = convert_code_to_readme(code_content, file_source)
        
        if readme_content:
            st.success(f"✅ **File {i} converted to README format!**")
            
            # Display the generated README
            with st.expander(f"📋 Generated README for {file_source}", expanded=True):
                st.markdown(readme_content)
            
            readme_output = {
                "file_number": i,
                "source_file": file_source,
                "original_content": code_content,
                "generated_readme": readme_content,
                "similarity_score": similarity,
                "conversion_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "content_stats": {
                    "original_length": len(code_content),
                    "readme_length": len(readme_content)
                }
            }
            
            readme_outputs.append(readme_output)
        else:
            st.error(f"❌ **Failed to convert file {i} to README format**")
    
    return readme_outputs

def analyze_readme_content(readme_outputs):
    """Analyze the generated README content for database information"""
    st.write("**🔍 Step 3: Analyzing README content for database information**")
    
    analysis_results = []
    
    for readme_data in readme_outputs:
        file_source = readme_data['source_file']
        readme_content = readme_data['generated_readme']
        file_number = readme_data['file_number']
        
        st.markdown(f"### 🔍 Analyzing README {file_number}: `{file_source}`")
        
        # LLM Call 1: Check for database presence
        st.write(f"**🔍 LLM Call 1: Checking for database information**")
        database_check = call_llm(
            system_prompt="You are a database expert. Your job is to identify if the given README content contains any database-related information.",
            user_prompt="Does this README content contain any database-related information? Answer with 'YES' or 'NO' and provide a brief explanation.",
            content=readme_content,
            step_name=f"Database Check - {file_source}"
        )
        
        if not database_check:
            st.warning(f"⚠️ **Could not verify database presence in {file_source}**")
            continue
        
        st.write(f"**Database Check Result:** {database_check}")
        
        analysis_result = {
            "file_number": file_number,
            "source_file": file_source,
            "readme_content": readme_content,
            "database_check": database_check,
            "llm_calls_completed": 1,
            "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if "yes" in database_check.lower():
            # LLM Call 2: Extract database types and names
            st.write(f"**🔍 LLM Call 2: Extracting database types**")
            database_types = call_llm(
                system_prompt="You are a database expert. Extract database types and names from the given README content.",
                user_prompt="Extract all database types (MySQL, PostgreSQL, MongoDB, etc.) and database names mentioned in this README. Return as JSON with keys 'database_types' and 'database_names'. If none found, return empty arrays.",
                content=readme_content,
                step_name=f"Database Types - {file_source}"
            )
            
            # LLM Call 3: Extract SQL queries
            st.write(f"**🔍 LLM Call 3: Extracting SQL queries**")
            sql_queries = call_llm(
                system_prompt="You are a SQL expert. Extract SQL queries from the given README content.",
                user_prompt="Extract all SQL queries (SELECT, INSERT, UPDATE, DELETE, CREATE, etc.) from this README. Return as JSON with key 'sql_queries' containing an array of queries. If none found, return empty array.",
                content=readme_content,
                step_name=f"SQL Queries - {file_source}"
            )
            
            # LLM Call 4: Extract APIs and external interfaces
            st.write(f"**🔍 LLM Call 4: Extracting APIs and interfaces**")
            apis_interfaces = call_llm(
                system_prompt="You are an API and integration expert. Extract API endpoints and external interfaces from the given README content.",
                user_prompt="Extract all API endpoints, external services, and interfaces mentioned in this README. Return as JSON with keys 'api_endpoints' and 'external_interfaces'. If none found, return empty arrays.",
                content=readme_content,
                step_name=f"APIs/Interfaces - {file_source}"
            )
            
            # Update analysis result with additional data
            analysis_result.update({
                "database_types_raw": database_types,
                "sql_queries_raw": sql_queries,
                "apis_interfaces_raw": apis_interfaces,
                "llm_calls_completed": 4
            })
            
            # Try to parse JSON responses
            for key in ['database_types_raw', 'sql_queries_raw', 'apis_interfaces_raw']:
                raw_value = analysis_result[key]
                if raw_value:
                    try:
                        parsed = json.loads(raw_value)
                        analysis_result[key.replace('_raw', '_parsed')] = parsed
                        st.success(f"✅ **Successfully parsed {key.replace('_raw', '')} JSON**")
                    except json.JSONDecodeError:
                        st.info(f"ℹ️ **{key.replace('_raw', '')} is not JSON format - keeping as text**")
                        analysis_result[key.replace('_raw', '_parsed')] = raw_value
            
            st.success(f"✅ **Analysis completed for {file_source} with {analysis_result['llm_calls_completed']} LLM calls**")
        else:
            st.info(f"ℹ️ **No database information detected in {file_source}**")
        
        analysis_results.append(analysis_result)
    
    return analysis_results

def display_error_logs():
    """Display error logs in sidebar"""
    total_errors = len(st.session_state['new_flow_logs'])
    
    if total_errors == 0:
        st.info("🎉 No errors logged yet!")
        return
    
    st.error(f"📊 Total Errors: {total_errors}")
    
    if st.button("🗑️ Clear Error Logs", key="clear_new_flow_logs"):
        st.session_state['new_flow_logs'] = []
        st.success("Error logs cleared!")
        st.rerun()
    
    # Show recent errors
    if total_errors > 0:
        with st.expander("🐛 Recent Errors", expanded=False):
            for i, log in enumerate(st.session_state['new_flow_logs'][-5:], 1):  # Show last 5 errors
                st.write(f"**Error {i}:** {log['step_name']} - {log['error_type']}")
                st.write(f"**Time:** {log['timestamp']}")
                if log['status_code']:
                    st.write(f"**Status:** {log['status_code']}")
                st.write(f"**Details:** {log['response_text'][:200]}...")
                st.write("---")

def main():
    st.set_page_config(
        page_title="New Combined Flow",
        page_icon="🔄",
        layout="wide"
    )
    
    st.title("🔄 Multi-File README Conversion Flow")
    st.markdown("**Codebase Files → LLM README Conversion → Database Analysis → Display Results**")
    
    # Sidebar for error tracking
    with st.sidebar:
        st.header("🚨 Error Tracking")
        display_error_logs()
    
    # Information about the new approach
    st.info("🧠 **New Approach**: This flow scans your actual codebase files, converts each to README format using LLM, then analyzes for database information. Test with a small number of files first to evaluate README conversion quality before processing the entire codebase.")
    
    # Main form
    with st.form("new_flow_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            codebase_name = st.text_input(
                "🗂️ Codebase Name:",
                placeholder="my-project",
                help="Name of the codebase to process (must exist in vector database)"
            )
            
            max_files = st.number_input(
                "📊 Number of Files to Process:",
                min_value=1,
                max_value=100,
                value=10,
                help="Number of files to retrieve and process from the codebase. Start with a smaller number to test README conversion quality."
            )
        
        with col2:
            st.write("**🔄 Processing Flow:**")
            st.write("1. 📁 Scan actual codebase files (.py, .js, .ts, etc.)")
            st.write("2. 📝 Convert each file to README format using LLM")
            st.write("3. 🔍 Analyze README content with LLM calls:")
            st.write("   - Database presence check")
            st.write("   - Database types extraction") 
            st.write("   - SQL queries extraction")
            st.write("   - APIs/interfaces extraction")
            st.write("4. 📊 Display structured results")
            
            st.info("💡 **Testing Approach**: Start with 5-10 files to evaluate README conversion quality, then scale up once satisfied with results.")
        
        submit_button = st.form_submit_button(
            '🚀 Start Multi-File README Processing',
            use_container_width=True
        )
    
    # Process form submission
    if submit_button:
        if not codebase_name:
            st.error("❌ Please enter a codebase name")
        else:
            try:
                st.markdown("---")
                st.header("🔄 Multi-File README Processing")
                
                # Step 1: Get files from codebase
                files = get_codebase_files(codebase_name, max_files)
                
                if files:
                    # Step 2: Process files to README format
                    readme_outputs = process_files_to_readme(files)
                    
                    if readme_outputs:
                        # Step 3: Analyze README content
                        analysis_results = analyze_readme_content(readme_outputs)
                        
                        if analysis_results:
                            # Step 4: Display final results
                            st.header("🎯 Final Processing Results")
                            
                            # Create final structure
                            final_results = {
                                "extraction_metadata": {
                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "codebase": codebase_name,
                                    "flow_type": "multi_file_readme_to_database_analysis",
                                    "files_processed": len(readme_outputs),
                                    "total_llm_calls": len(readme_outputs) + sum(info.get('llm_calls_completed', 0) for info in analysis_results),
                                    "files_with_db_info": len([info for info in analysis_results if "yes" in info.get('database_check', '').lower()])
                                },
                                "readme_outputs": readme_outputs,
                                "database_analysis": analysis_results
                            }
                            
                            st.subheader("📊 Complete Results")
                            st.json(final_results)
                            
                            # Summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Files Processed", len(readme_outputs))
                            with col2:
                                st.metric("Total LLM Calls", final_results["extraction_metadata"]["total_llm_calls"])
                            with col3:
                                db_files = final_results["extraction_metadata"]["files_with_db_info"]
                                st.metric("Files with DB Info", db_files)
                            with col4:
                                st.metric("Processing Time", datetime.now().strftime("%H:%M:%S"))
                            
                            # Download option
                            results_json = json.dumps(final_results, indent=2)
                            st.download_button(
                                label="📥 Download Complete Results JSON",
                                data=results_json,
                                file_name=f"multi_file_readme_results_{codebase_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )
                            
                            # GitHub commit option
                            st.subheader("📤 GitHub Integration")
                            if st.button("🚀 Commit to GitHub"):
                                commit_result = commit_json(codebase_name, final_results)
                                st.text(commit_result)
                            
                            st.balloons()
                        else:
                            st.warning("⚠️ No analysis results generated")
                    else:
                        st.warning("⚠️ Could not convert any files to README format")
                else:
                    st.warning("⚠️ Could not retrieve files from codebase")
                    
            except Exception as e:
                st.error(f"❌ **Processing failed:** {str(e)}")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_error("processing_error", None, str(e), "Main Processing", timestamp)

if __name__ == "__main__":
    main()