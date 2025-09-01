
def embed_readme_content(codebase_name, readme_content_list):
    """Embed README content directly without cloning repository"""
    try:
        from utilities.utils import create_embeddings_from_text
        
        # Join all README content into documents
        documents = []
        for i, content in enumerate(readme_content_list):
            documents.append({
                'content': content,
                'metadata': {'source': f'readme_file_{i+1}'}
            })
        
        # Create embeddings
        result = create_embeddings_from_text(codebase_name, documents)
        return {"status": "success", "message": f"Embedded {len(documents)} README documents"}
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