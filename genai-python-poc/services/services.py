
def embed_readme_content(codebase_name, readme_content_list):
    """Embed README content directly using existing embedding flow"""
    try:
        from utilities.utils import perform_embedding_postgres
        from langchain.schema import Document
        import os
        
        # Create Document objects from README content
        documents = []
        for item in readme_content_list:
            # Handle both old format (string) and new format (dict)
            if isinstance(item, dict):
                content = item['content']
                original_path = item['original_path']
                # Convert original file extension to .md
                base_name = os.path.splitext(original_path)[0]
                readme_filename = f"{base_name}.md"
            else:
                # Fallback for old format
                content = item
                readme_filename = f'readme_file_{len(documents)+1}.md'
            
            doc = Document(
                page_content=content,
                metadata={'source': readme_filename}
            )
            documents.append(doc)
        
        # Use existing embedding function
        result = perform_embedding_postgres(codebase_name, documents)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

def generate_embeddings(codebase, external):
    VECTOR_STORE_DIRECTORY = codebase
    if external:
        VECTOR_STORE_DIRECTORY = f"{codebase}-external-files"
    
    clone_repo_status = clone_repo(codebase)
    if clone_repo_status:
        generate_embeddings(VECTOR_STORE_DIRECTORY)
    else:
        return {"status": "error", "message": "Failed to clone repository"}

    texts = load_documents(codebase, external)
    delete_repo(codebase)