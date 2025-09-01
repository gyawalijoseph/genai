import streamlit as st
import requests
import os
import shutil
from git import Repo

# Configuration
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
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

def get_files(codebase):
    """Get 5 code files from cloned repository"""
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
                        if len(files) >= 5:  # Hard-coded limit
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

def main():
    st.title("📚 Vectorizing Codebase with README Documentation Flow")
    st.write("Convert 5 code files to README format using LLM for enhanced vectorization")
    
    with st.form("readme_vectorization_form"):
        codebase_name = st.text_input("Codebase Name:", placeholder="my-project")
        submit = st.form_submit_button("🚀 Start README Vectorization")
    
    if submit and codebase_name:
        st.write("**Step 1: Cloning repository...**")
        if clone_repo(codebase_name):
            st.success("✅ Repository cloned")
            
            st.write("**Step 2: Getting files...**")
            files = get_files(codebase_name)
            st.write(f"Found {len(files)} files to process")
            
            st.write("**Step 3: Generating README documentation with LLM...**")
            
            # Progress bar for overall process
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file_data in enumerate(files, 1):
                # Update progress
                progress = i / len(files)
                progress_bar.progress(progress)
                status_text.text(f"Processing file {i}/{len(files)}: {os.path.basename(file_data['path'])}")
                
                st.write(f"**File {i}: {file_data['path']}**")
                
                with st.expander(f"Original Code", expanded=False):
                    st.code(file_data['content'], language="text")
                
                readme_result = call_llm(file_data['content'], file_data['path'])
                
                with st.expander(f"Generated README", expanded=True):
                    st.markdown(readme_result)
            
            # Complete progress
            progress_bar.progress(1.0)
            status_text.text("✅ All files processed successfully!")
            
            st.write("**Step 4: Cleaning up...**")
            delete_repo(codebase_name)
            st.success("🎉 README vectorization flow complete!")

if __name__ == "__main__":
    main()