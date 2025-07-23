import json
import requests
import streamlit as st
from constants.server_info import HEADERS

def vector_search(codebase, similarity_search_query, vector_results_count):
    url = "https://localhost:5000/vector-search"
    payload = json.dumps({
        "codebase": codebase,
        "query": similarity_search_query,
        "vector_results_count": vector_results_count
    })

    with st.spinner("Retrieving data from Embedding..."):
        response = requests.request("POST", url, headers=HEADERS, data=payload)
    data = response.json()
    return data