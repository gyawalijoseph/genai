import os
import json
from datetime import datetime
import streamlit as st
from utils.embedding import create_embeddings_fullfile

def main():
    st.title("Full-File Embedding Generation")
    
    st.markdown("""
    This page allows you to create embeddings for an entire codebase where each file is embedded as a complete unit,
    without text splitting. This approach works well with LLMs that have large token limits and provides better context
    preservation for each file.
    
    **Key Features:**
    - Embeds entire files without splitting
    - Supports common code file extensions (.py, .js, .ts, .java, .cpp, etc.)
    - Skips build artifacts and dependency directories
    - Creates vector store with name: `{codebase}-codebase-fullfile`
    """)
    
    st.divider()
    
    # Input section
    st.subheader("📝 Configuration")
    codebase = st.text_input(
        "Codebase Name:", 
        placeholder="Enter the repository name to embed",
        help="This should be the name of the repository in your GitHub organization"
    )
    
    # Information section
    with st.expander("ℹ️ How it works", expanded=False):
        st.markdown("""
        1. **Repository Cloning**: The system clones the specified repository
        2. **File Discovery**: Scans for supported file types (.py, .js, .ts, .java, etc.)
        3. **Content Loading**: Reads entire file content without splitting
        4. **Embedding Creation**: Creates one embedding per file with complete context
        5. **Storage**: Stores in PostgreSQL vector database with metadata
        6. **Cleanup**: Removes cloned repository after processing
        
        **Supported File Types:**
        - Programming: .py, .js, .ts, .java, .cpp, .c, .h, .cs, .go, .rs, .php, .rb, .swift, .kt, .scala
        - Documentation: .md, .txt
        - Configuration: .yml, .yaml, .json, .xml
        - Web: .html, .css
        """)
    
    with st.expander("🔍 Comparison with Standard Embedding", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Standard Embedding (/embed)**")
            st.markdown("""
            - Uses document splitting
            - Creates multiple chunks per file
            - Good for detailed searches
            - Requires external parameter
            - Better for large files
            """)
        
        with col2:
            st.markdown("**Full-File Embedding (/embed-fullfile)**")
            st.markdown("""
            - Embeds complete files
            - One embedding per file
            - Better file-level context
            - No external parameter needed
            - Works with large token limits
            """)
    
    st.divider()
    
    # Action section
    st.subheader("🚀 Generate Embeddings")
    
    if st.button("Generate Full-File Embeddings", type="primary", disabled=not codebase):
        if codebase:
            # Log the request
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_data = {
                "codebase": codebase,
                "embedding_type": "full-file",
                "timestamp": timestamp,
                "endpoint": "/embed-fullfile"
            }
            
            # Create logs directory if it doesn't exist
            os.makedirs("logs", exist_ok=True)
            log_filename = f"fullfile_embedding_{codebase}_{timestamp}.json"
            log_filepath = os.path.join("logs", log_filename)
            
            # Execute the embedding creation
            create_embeddings_fullfile(codebase)
            
            # Save log after execution
            with open(log_filepath, 'w') as log_file:
                json.dump(log_data, log_file, indent=2)
            
            st.info(f"📄 **Request logged to:** {log_filename}")
        else:
            st.warning("⚠️ Please enter a codebase name")
    
    # Status and help section
    st.divider()
    st.subheader("📊 Usage Tips")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Best for:**")
        st.markdown("""
        - File-level code analysis
        - Complete context preservation  
        - LLMs with large token limits
        - Smaller to medium repositories
        - Understanding full file structure
        """)
    
    with col2:
        st.markdown("**Consider Standard Embedding for:**")
        st.markdown("""
        - Very large files (>100KB)
        - Detailed code section searches
        - Memory-constrained environments
        - Fine-grained similarity search
        - Large repositories with many files
        """)

if __name__ == "__main__":
    main()