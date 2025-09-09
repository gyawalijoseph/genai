
import os
from langchain.schema import Document
from utilities.github_utils import clone_repo, delete_repo
from utilities.utils import perform_embedding_postgres

def load_documents_fullfile(codebase):
    """Load entire files from the cloned repository without splitting."""
    documents = []
    repo_path = f"./{codebase}"
    
    # File extensions to include for embedding
    allowed_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', 
                         '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala',
                         '.md', '.txt', '.yml', '.yaml', '.json', '.xml', '.html', '.css']
    
    for root, dirs, files in os.walk(repo_path):
        # Skip common directories that shouldn't be embedded
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', 'env', 'build', 'dist']]
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in allowed_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if content.strip():  # Only add non-empty files
                            relative_path = os.path.relpath(file_path, repo_path)
                            doc = Document(
                                page_content=content,
                                metadata={
                                    "source": relative_path,
                                    "file_name": file,
                                    "file_type": file_ext
                                }
                            )
                            documents.append(doc)
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
                    continue
    
    return documents

def generate_embeddings_fullfile(codebase):
    """Generate embeddings for the entire codebase with full file content per embedding."""
    VECTOR_STORE_DIRECTORY = f"{codebase}-codebase-fullfile"
    
    # Clone the repository
    clone_repo_status = clone_repo(codebase)
    if not clone_repo_status:
        return {"status": "error", "message": "Failed to clone repository"}
    
    try:
        # Load all documents from the repository
        documents = load_documents_fullfile(codebase)
        
        if not documents:
            delete_repo(codebase)
            return {"status": "error", "message": "No documents found in repository"}
        
        # Delete the cloned repository
        delete_repo(codebase)
        
        # Perform embedding
        embedding_status = perform_embedding_postgres(VECTOR_STORE_DIRECTORY, documents)
        
        if embedding_status.get("status") == "success":
            return {
                "status": "success", 
                "message": f"Embedding performed successfully for {len(documents)} files",
                "codebase": codebase,
                "vector_store": VECTOR_STORE_DIRECTORY,
                "files_processed": len(documents)
            }
        else:
            return {"status": "error", "message": "Embedding failed"}
            
    except Exception as e:
        # Clean up in case of error
        delete_repo(codebase)
        return {"status": "error", "message": f"Error processing repository: {str(e)}"}

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

    embedding_status = perform_embedding_postgres(VECTOR_STORE_DIRECTORY, texts)
    if embedding_status:
        return {"status": "success", "message": "Embedding performed successfully"}
    else:
        return {"status": "error", "message": "Embedding failed"}

    return {
        "codebase": codebase,
        "status": "success",
        "path": VECTOR_STORE_DIRECTORY
    }

