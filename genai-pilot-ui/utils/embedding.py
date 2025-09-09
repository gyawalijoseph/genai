import json
import requests
import streamlit as st

from constants.server_info import LOCAL_BACKEND_URL, EMBED_ENDPOINT, EMBED_FULLFILE_ENDPOINT, HEADERS

def create_embeddings(codebase, external):
    payload = json.dumps({
        "codebase": codebase,
        "external": f'{external}'
    })

    with st.spinner("Creating embeddings..."):
        response = requests.request("POST", LOCAL_BACKEND_URL + EMBED_ENDPOINT, headers=HEADERS, data=payload)
    
    if response.status_code == 200:
        if external:
            st.success(f"✅ **External embeddings created for {codebase}**")
        else:
            st.success(f"✅ **Internal embeddings created for {codebase}**")
    else:
        st.error(f"❌ **Failed to create embeddings for {codebase}**")

def create_embeddings_fullfile(codebase):
    """Create embeddings for entire codebase with full file content per embedding."""
    payload = json.dumps({
        "codebase": codebase
    })

    with st.spinner("Creating full-file embeddings..."):
        response = requests.request("POST", LOCAL_BACKEND_URL + EMBED_FULLFILE_ENDPOINT, headers=HEADERS, data=payload)
    
    if response.status_code == 200:
        response_data = response.json()
        files_processed = response_data.get('files_processed', 0)
        vector_store = response_data.get('vector_store', f"{codebase}-codebase-fullfile")
        st.success(f"✅ **Full-file embeddings created for {codebase}**")
        st.info(f"📁 **Files processed:** {files_processed}")
        st.info(f"🗄️ **Vector store:** {vector_store}")
    else:
        try:
            error_data = response.json()
            error_message = error_data.get('message', 'Unknown error')
            st.error(f"❌ **Failed to create full-file embeddings for {codebase}**: {error_message}")
        except:
            st.error(f"❌ **Failed to create full-file embeddings for {codebase}** (Status: {response.status_code})")  