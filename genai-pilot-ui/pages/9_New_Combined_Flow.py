import streamlit as st
import requests
import os
import shutil
from git import Repo

# Configuration
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
EMBED_README_ENDPOINT = "/embed-readme"
HEADERS = {"Content-Type": "application/json"}

# Hardcoded PAT - Replace with your actual token
GITHUB_PAT = "your_github_pat_here"

# README conversion prompt
README_CONVERSION_PROMPT = """Create a concise readme for this source code. Create an overall summary, and add sections to identify databases used SQL Queries, and for external interfaces and APIs. If information is not there in code your output should say no information found."""

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

def count_total_files(codebase):
    """Count total code files in the repository"""
    file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.sql']
    total_count = 0
    
    for root, dirs, filenames in os.walk(codebase):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in filenames:
            if any(filename.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if len(content.strip()) > 100:  # Skip small files
                        total_count += 1
                except:
                    continue
    return total_count

def get_files(codebase, max_files=5):
    """Get code files from cloned repository"""
    file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.sql']
    files = []
    
    for root, dirs, filenames in os.walk(codebase):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in filenames:
            if any(filename.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if len(content.strip()) > 100:  # Skip small files
                        files.append({
                            'path': file_path,
                            'content': content
                        })
                        if len(files) >= max_files:
                            return files
                except:
                    continue
    return files

def call_llm(content, file_path):
    """Call LLM API with README conversion prompt and progress bar"""
    url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
    payload = {
        "system_prompt": "You are an expert technical writer who creates clear, concise documentation from source code.",
        "user_prompt": README_CONVERSION_PROMPT,
        "codebase": content
    }
    
    with st.spinner(f"🔄 Generating README for {file_path}... Please wait, this may take a moment."):
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=300)
            if response.status_code == 200:
                response_json = response.json()
                return response_json.get('output', 'No output received')
            else:
                return f"Error: HTTP {response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"

def embed_readme_docs(codebase_name, readme_results):
    """Embed the generated README documentation"""
    url = f"{LOCAL_BACKEND_URL}{EMBED_README_ENDPOINT}"
    payload = {
        "codebase": codebase_name,
        "readme_content": readme_results
    }
    
    with st.spinner(f"🔄 Embedding README documentation as '{codebase_name}'..."):
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=300)
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def main():
    st.title("📚 Vectorizing Codebase with README Documentation Flow")
    st.write("Convert 5 code files to README format using LLM for enhanced vectorization")
    
    with st.form("readme_vectorization_form"):
        codebase_name = st.text_input("Codebase Name:", placeholder="my-project")
        file_count = st.number_input("Number of Files:", min_value=1, max_value=50, value=5)
        enable_embedding = st.checkbox("Create embeddings after README generation")
        
        submit = st.form_submit_button("🚀 Start README Vectorization")
    
    if submit and codebase_name:
        st.write("**Step 1: Cloning repository...**")
        if clone_repo(codebase_name):
            st.success("✅ Repository cloned")
            
            st.write("**Step 2: Analyzing codebase...**")
            
            # Count total files and get files to process simultaneously
            with st.spinner("🔄 Scanning codebase for files..."):
                total_files = count_total_files(codebase_name)
                files = get_files(codebase_name, file_count)
            
            # Display file count information
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total Code Files", total_files)
            with col2:
                st.metric("🎯 Processing", len(files))
            with col3:
                st.metric("📈 Coverage", f"{len(files)/total_files*100:.1f}%" if total_files > 0 else "0%")
            
            st.write("**Step 3: Generating README documentation with LLM...**")
            
            # Progress bar for overall process
            progress_bar = st.progress(0)
            status_text = st.empty()
            readme_results = []
            
            for i, file_data in enumerate(files, 1):
                # Update progress
                progress = i / len(files)
                progress_bar.progress(progress)
                status_text.text(f"Processing file {i}/{len(files)}: {os.path.basename(file_data['path'])}")
                
                st.write(f"**File {i}: {file_data['path']}**")
                
                with st.expander(f"Original Code", expanded=False):
                    st.code(file_data['content'], language="text")
                
                readme_result = call_llm(file_data['content'], file_data['path'])
                readme_results.append(readme_result)
                
                with st.expander(f"Generated README", expanded=True):
                    st.markdown(readme_result)
            
            # Complete progress
            progress_bar.progress(1.0)
            status_text.text("✅ All files processed successfully!")
            
            if enable_embedding:
                st.write("**Step 4: Creating embeddings...**")
                embed_result = embed_readme_docs(codebase_name, readme_results)
                
                if embed_result.get('status') == 'error':
                    st.error(f"❌ Embedding failed: {embed_result.get('message')}")
                else:
                    st.success(f"✅ README documentation embedded successfully as '{codebase_name}'")
            
            st.write("**Step 4: Cleaning up...**" if not enable_embedding else "**Step 5: Cleaning up...**")
            delete_repo(codebase_name)
            st.success("🎉 README vectorization flow complete!")

if __name__ == "__main__":
    main()