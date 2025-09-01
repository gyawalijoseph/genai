
def embed_readme_content(codebase_name, readme_content_list):
    """Embed README content directly using existing embedding flow"""
    try:
        from utilities.utils import perform_embedding_postgres
        from langchain.schema import Document
        
        # Create Document objects from README content
        documents = []
        for i, content in enumerate(readme_content_list):
            doc = Document(
                page_content=content,
                metadata={'source': f'readme_file_{i+1}.md'}
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