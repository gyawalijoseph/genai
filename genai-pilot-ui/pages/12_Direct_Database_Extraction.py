import streamlit as st
import requests
import json
import os
import re
import shutil
from datetime import datetime
from git import Repo

from utils.githubUtil import commit_json
from utils.metadataUtil import fetch_metadata

# Configuration
DEFAULT_DATABASE_SYSTEM_PROMPT = "You are an expert at analyzing code for Couchbase/NoSQL database configurations, connections, queries, and data models."
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
EMBED_DATABASE_ENDPOINT = "/embed-database-spec"
HEADERS = {"Content-Type": "application/json"}

# Hardcoded PAT - Replace with your actual token
GITHUB_PAT = "your_github_pat_here"

def clone_repo(codebase):
    """Clone repository with hardcoded PAT authentication"""
    try:
        repo_url = "https://github.aexp.com/amex-eng/" + codebase
        local_path = "./" + codebase
        auth_repo_url = repo_url.replace("https://", f"https://{GITHUB_PAT}@")
        
        Repo.clone_from(auth_repo_url, local_path)
        return True
    except Exception as e:
        st.error(f"❌ Error cloning repo: {e}")
        return False

def delete_repo(codebase):
    """Delete cloned repository directory"""
    try:
        if os.path.exists(codebase):
            shutil.rmtree(codebase)
    except Exception as e:
        st.error(f"❌ Error deleting repo: {e}")

def get_all_code_files(codebase):
    """Get all code files from repository"""
    file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.sql', '.php', '.rb', '.go', '.cs', '.json', '.yml', '.yaml', '.properties', '.conf']
    files = []
    
    for root, dirs, filenames in os.walk(codebase):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in filenames:
            if any(filename.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if len(content.strip()) > 20:  # Skip tiny files
                        files.append({
                            'path': file_path.replace(f'./{codebase}/', ''),
                            'content': content,
                            'size': len(content)
                        })
                except:
                    continue
    
    return files

def extract_database_spec_directly(files, system_prompt, codebase_name):
    """Extract database specification directly from all code files in one LLM call"""
    st.write("🎯 **Direct Database Specification Extraction**")
    st.info(f"**Processing {len(files)} files** in a single comprehensive analysis")
    
    # Combine all files into one structured input for the LLM
    combined_codebase = f"# Database Specification Extraction for: {codebase_name}\n\n"
    
    for file_data in files:
        combined_codebase += f"## File: {file_data['path']}\n"
        combined_codebase += f"```{get_file_language(file_data['path'])}\n"
        combined_codebase += file_data['content']
        combined_codebase += "\n```\n\n"
    
    # Database-focused extraction prompt
    extraction_prompt = f"""Analyze the entire codebase for {codebase_name} and extract a comprehensive Couchbase/NoSQL database specification.

IMPORTANT: Only include information that is actually present in the code. Do not make assumptions or add placeholder data.

Create a JSON specification with these sections (omit sections if no relevant data is found):

1. "database_type": Type of database system used (Couchbase, MongoDB, etc.)
2. "connection_configuration": 
   - hosts/clusters
   - ports
   - authentication details (without actual credentials)
   - connection strings/URLs
3. "buckets_and_collections":
   - bucket names
   - collection names within buckets
   - scope names if used
4. "document_types_and_schemas":
   - types of documents stored
   - document structures/schemas
   - key patterns
5. "queries_and_operations":
   - N1QL queries found in the code
   - SDK operations (get, upsert, insert, etc.)
   - Query patterns
6. "indexes":
   - GSI (Global Secondary Index) definitions
   - Primary indexes
   - Index creation statements
7. "application_integration":
   - How the application connects to the database
   - Connection pooling
   - Error handling patterns
   - Transaction usage

Focus on Couchbase terminology and concepts. Provide actual code examples where relevant.

Return only valid JSON:"""

    try:
        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": extraction_prompt,
            "codebase": combined_codebase
        }
        
        # Show size info
        payload_size = len(combined_codebase)
        st.info(f"**📊 Analysis Scope:** {payload_size:,} characters across {len(files)} files")
        
        with st.spinner("🔄 Performing comprehensive database specification extraction..."):
            response = requests.post(url, json=payload, headers=HEADERS, timeout=600)
        
        if response.status_code == 200:
            response_json = response.json()
            output = response_json.get('output', '')
            
            if output:
                # Parse the response
                try:
                    database_spec = json.loads(output)
                    st.success("✅ **Database specification extracted successfully!**")
                    
                    # Show what was found
                    sections_found = [section for section, data in database_spec.items() if data]
                    st.write(f"**📋 Sections with data:** {', '.join(sections_found)}")
                    
                    return database_spec
                except json.JSONDecodeError:
                    # Try to fix the JSON
                    st.warning("⚠️ **Fixing malformed JSON response...**")
                    fixed_output = fix_json_with_llm(output)
                    if fixed_output:
                        return fixed_output
                    else:
                        st.error("❌ **Could not parse database specification**")
                        return None
            else:
                st.error("❌ **No output from database specification extraction**")
                return None
        else:
            st.error(f"❌ **API Error:** HTTP {response.status_code}")
            st.error(response.text)
            return None
            
    except Exception as e:
        st.error(f"❌ **Exception during extraction:** {str(e)}")
        return None

def fix_json_with_llm(malformed_json):
    """Use LLM to fix malformed JSON"""
    try:
        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
        payload = {
            "system_prompt": "You are a JSON formatting expert. Fix the malformed JSON and return only valid JSON.",
            "user_prompt": f"Fix this JSON and return only the corrected version:\n\n{malformed_json}",
            "codebase": ""
        }
        
        response = requests.post(url, json=payload, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            response_json = response.json()
            fixed_output = response_json.get('output', '')
            if fixed_output:
                return json.loads(fixed_output)
    except:
        pass
    return None

def get_file_language(file_path):
    """Get language for syntax highlighting based on file extension"""
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.sql': 'sql',
        '.json': 'json', '.yml': 'yaml', '.yaml': 'yaml',
        '.properties': 'properties', '.conf': 'text'
    }
    return mapping.get(ext, 'text')

def create_database_embeddings(codebase_name, database_spec):
    """Create embeddings from the database specification for future searches"""
    st.subheader("🔗 Creating Database Specification Embeddings")
    
    # Convert spec to searchable text format
    spec_text = f"# Database Specification for {codebase_name}\n\n"
    spec_text += json.dumps(database_spec, indent=2)
    
    url = f"{LOCAL_BACKEND_URL}{EMBED_DATABASE_ENDPOINT}"
    payload = {
        "codebase": f"{codebase_name}-database-spec",
        "database_specification": spec_text
    }
    
    try:
        with st.spinner("🔄 Creating database specification embeddings..."):
            response = requests.post(url, json=payload, headers=HEADERS, timeout=300)
        
        if response.status_code == 200:
            st.success(f"✅ **Database specification embedded as '{codebase_name}-database-spec'**")
            return True
        else:
            st.warning(f"⚠️ **Embedding failed:** HTTP {response.status_code}")
            return False
    except Exception as e:
        st.warning(f"⚠️ **Embedding error:** {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="Direct Database Specification Extraction",
        page_icon="⚡",
        layout="wide"
    )

    st.title("⚡ Direct Database Specification Extraction")
    st.markdown("**Single-pass comprehensive database analysis - no redundant LLM calls**")
    
    st.info("🎯 **Efficient Approach:** Clone → Analyze All Code → Extract Complete Database Spec")

    with st.form("direct_extraction_form"):
        col1, col2 = st.columns(2)

        with col1:
            codebase = st.text_input(
                "🗂️ Codebase Name:",
                placeholder="my-project",
                help="Name of the codebase to clone and analyze"
            )
            
            database_system_prompt = st.text_area(
                "🗄️ Database System Prompt:",
                value=DEFAULT_DATABASE_SYSTEM_PROMPT,
                height=100,
                help="Instructions for database extraction"
            )

        with col2:
            create_embeddings = st.checkbox(
                "🔗 Create Database Spec Embeddings",
                value=True,
                help="Create embeddings from the extracted specification for future use"
            )
            
            max_file_size = st.number_input(
                "📁 Max File Size (KB):",
                value=100,
                min_value=10,
                max_value=1000,
                help="Skip files larger than this to avoid API limits"
            )

        st.info("⚡ **Key Benefits:** Single comprehensive analysis, no vector search overhead, direct extraction")

        submit_button = st.form_submit_button(
            '🚀 Start Direct Database Specification Extraction',
            use_container_width=True
        )

    if submit_button:
        if not codebase:
            st.error("❌ Please enter a codebase name")
        else:
            try:
                st.markdown("---")
                st.header("⚡ Direct Database Specification Extraction")

                # Step 1: Clone repository
                st.subheader("📥 Step 1: Repository Cloning")
                if clone_repo(codebase):
                    st.success("✅ Repository cloned successfully")
                    
                    # Step 2: Get all code files
                    st.subheader("📂 Step 2: Code File Collection")
                    
                    with st.spinner("🔄 Collecting all code files..."):
                        all_files = get_all_code_files(codebase)
                        
                        # Filter by file size
                        max_size_bytes = max_file_size * 1024
                        filtered_files = [f for f in all_files if f['size'] <= max_size_bytes]
                        large_files = len(all_files) - len(filtered_files)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Total Files Found", len(all_files))
                    with col2:
                        st.metric("🎯 Files to Process", len(filtered_files))
                    with col3:
                        st.metric("⚠️ Large Files Skipped", large_files)
                    
                    if large_files > 0:
                        st.warning(f"⚠️ Skipped {large_files} files larger than {max_file_size}KB to stay within API limits")
                    
                    # Step 3: Direct database specification extraction
                    st.subheader("🎯 Step 3: Comprehensive Database Analysis")
                    
                    database_spec = extract_database_spec_directly(
                        filtered_files, database_system_prompt, codebase
                    )
                    
                    if database_spec:
                        # Step 4: Get application metadata
                        st.subheader("🚗 Step 4: Application Metadata")
                        try:
                            metadata = fetch_metadata(codebase)
                            if metadata is None:
                                metadata = {"note": f"No metadata found for {codebase}"}
                                st.warning("⚠️ **No application metadata found**")
                            else:
                                st.success("✅ **Application metadata extracted!**")
                        except Exception as e:
                            metadata = {"error": f"Metadata extraction failed: {str(e)}"}
                            st.error(f"❌ **Metadata extraction failed:** {str(e)}")
                        
                        # Step 5: Create embeddings if requested
                        if create_embeddings:
                            st.subheader("🔗 Step 5: Database Specification Embeddings")
                            embedding_success = create_database_embeddings(codebase, database_spec)
                        else:
                            embedding_success = False
                        
                        # Prepare final results
                        final_results = {
                            "extraction_metadata": {
                                "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "codebase": codebase,
                                "extraction_type": "direct_comprehensive_analysis",
                                "files_analyzed": len(filtered_files),
                                "total_files_found": len(all_files),
                                "large_files_skipped": large_files,
                                "embeddings_created": embedding_success
                            },
                            "Application": metadata,
                            "Database_Specification": database_spec
                        }
                        
                        # Step 6: Display results
                        st.header("🎯 Final Database Specification")
                        st.json(final_results)
                        
                        # Download and commit options
                        col1, col2 = st.columns(2)
                        with col1:
                            results_json = json.dumps(final_results, indent=2)
                            st.download_button(
                                label="📥 Download Database Specification",
                                data=results_json,
                                file_name=f"database_spec_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )

                        with col2:
                            if st.button("📤 Commit to GitHub"):
                                commit_json_to_github(codebase, final_results)
                        
                        st.success("🎉 Direct database specification extraction completed!")
                        st.balloons()
                        
                    else:
                        st.error("❌ **Database specification extraction failed**")
                    
                    # Step 7: Cleanup
                    st.subheader("🧹 Cleanup")
                    delete_repo(codebase)
                    st.success("✅ Repository cleanup completed!")
                
                else:
                    st.error("❌ Failed to clone repository")

            except Exception as e:
                st.error(f"❌ **Extraction failed:** {str(e)}")
                delete_repo(codebase)

def commit_json_to_github(codebase, json_data):
    """GitHub integration for committing results"""
    st.subheader("📤 GitHub Integration")
    
    st.write("**📋 Data to be pushed to GitHub:**")
    with st.expander("📄 View JSON Data", expanded=False):
        st.code(json.dumps(json_data, indent=2), language="json")
    st.write(f"**📊 Data size:** {len(json.dumps(json_data))} characters")
    
    st.text(commit_json(codebase, json_data))

if __name__ == "__main__":
    main()