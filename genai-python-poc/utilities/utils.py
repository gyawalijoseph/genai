from datetime import time

from langchain.schema import StrOutputParser


def safechain_llm_call(system_prompt, user_prompt, codebase, max_retries=1, delay=5):
    if system_prompt:
        updated_prompt = ValidChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", f"{user_prompt} {{codebase}}")
        ])
    else:
        updated_prompt = ValidChatPromptTemplate.from_messages([
            ("user", f"{user_prompt} {{codebase}}")
        ])

    codebase = f"""
    {codebase}
    """

    for attempt in range(max_retries):
        try:
            chain = (updated_prompt | model('llama-3') | StrOutputParser())
            output = chain.invoke({
                "codebase": codebase
            })
            return output, 200
        except LCELModelException as e:
            return f"Vertex Model Request failed: {str(e)}", 400
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                return f"Failed after {max_retries} attempts: {str(e)}", 400

def similarity_search_pgvector(codebase, query, vector_results_count, similarity_threshold=0.4):
    vectorstore = get_connection('1', {
        "collection_name": codebase,
        "embedding_model_index": "ada-3",
        "schema": "tapld00"
    })

    # Get more results initially to account for filtering
    search_count = min(vector_results_count * 2, 50)  # Get up to 2x requested, max 50
    similarity_search_response = vectorstore.similarity_search_with_score(query, k=search_count)
    
    # Filter out unwanted files and low similarity scores
    excluded_files = ['buildblock.yaml', 'buildblock.yml', '.buildblock.yaml', '.buildblock.yml']
    filtered_results = []
    
    for doc, score in similarity_search_response:
        source_file = doc.metadata.get('source', '')
        file_name = source_file.split('/')[-1] if '/' in source_file else source_file
        
        # Skip excluded files and low similarity scores
        if (file_name.lower() not in [f.lower() for f in excluded_files] and 
            float(score) >= similarity_threshold):
            filtered_results.append({
                'page_content': doc.page_content, 
                'metadata': doc.metadata,
                'score': float(score)
            })
    
    # Sort by similarity score (highest first) and limit to requested count
    filtered_results.sort(key=lambda x: x['score'], reverse=True)
    return filtered_results[:vector_results_count]

def perform_embedding_postgres(VECTOR_STORE_DIR, split_document):
    print(f"Performing embedding for {VECTOR_STORE_DIR}")
    vectorstore = None
    try:
        COLLECTION_NAME = VECTOR_STORE_DIR
        vectorstore = get_connection('1', {
            "collection_name": COLLECTION_NAME,
            "embedding_model_index": "ada-3",
            "schema": "tapld00"
        })
        
        # Process in smaller batches with progress tracking
        batch_size = 25  # Reduced from 50 for better connection stability
        total_batches = (len(split_document) + batch_size - 1) // batch_size
        
        for i, batch_start in enumerate(range(0, len(split_document), batch_size)):
            batch = split_document[batch_start:batch_start + batch_size]
            print(f"Processing batch {i+1}/{total_batches} ({len(batch)} documents)")
            vectorstore.add_documents(batch)
        
        return {"status": "success", "message": "Embedding performed successfully"}
    except Exception as e:
        print(f"Error performing embedding: {e}")
        return {"status": "error", "message": f"Embedding performed unsuccessfully: {str(e)}"}
    finally:
        # Ensure connection cleanup
        if vectorstore:
            try:
                # Try different cleanup methods depending on the vectorstore implementation
                if hasattr(vectorstore, 'close'):
                    vectorstore.close()
                elif hasattr(vectorstore, '_client') and hasattr(vectorstore._client, 'close'):
                    vectorstore._client.close()
                elif hasattr(vectorstore, 'client') and hasattr(vectorstore.client, 'close'):
                    vectorstore.client.close()
                print("Connection cleanup completed")
            except Exception as cleanup_error:
                print(f"Warning: Connection cleanup failed: {cleanup_error}")