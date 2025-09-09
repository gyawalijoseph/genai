import os
import json
from datetime import datetime
import streamlit as st
from utils.vectorSearchUtil import vector_search


def main():
    st.title("Vector Similarity Search")
    codebase = st.text_input("Codebase Name: ")
    query = st.text_input("Query: ")
    vector_results_count = st.text_input("Vector Results Count: ")
    score_threshold = st.number_input("Min Score:", min_value=0.0, max_value=1.0, value=0.0, step=0.01)
    submit_button = st.button("Submit")

    if submit_button and codebase and query and vector_results_count:
        data = vector_search(codebase, query, vector_results_count)
        print(data)
        
        # Log results to JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{codebase}_{timestamp}.json"
        log_filepath = os.path.join("logs", log_filename)
        
        # Extract file names from results
        files = []
        for result in data['results']:
            if 'metadata' in result and 'source' in result['metadata']:
                files.append(result['metadata']['source'])
        
        log_data = {
            "query": query,
            "codebase": codebase,
            "vector_results_count": vector_results_count,
            "score_threshold": score_threshold,
            "timestamp": timestamp,
            "files": files,
            "results": data['results']
        }
        
        os.makedirs("logs", exist_ok=True)
        with open(log_filepath, 'w') as log_file:
            json.dump(log_data, log_file, indent=2)
        
        st.success(f"Results logged to: {log_filename}")
        
        if len(data['results']) == 0:
            st.error("No results found")
        for result in data['results']:
            # Show result if no score filter or if score meets threshold
            show_result = 'score' not in result or result['score'] >= score_threshold
            if show_result:
                score_text = f" (Score: {result['score']:.3f})" if 'score' in result else ""
                st.subheader(f"{result['metadata']['source']}{score_text}")
                _, extension = os.path.splitext(result['metadata']['source'])
                st.code(result['page_content'], language=extension[1:])

if __name__ == "__main__":
    main()