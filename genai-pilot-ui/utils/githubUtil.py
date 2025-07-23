import json
import requests
import streamlit as st

from constants.server_info import HEADERS


def commit_json(codebase, json_data):
    url = "https://api.github.com/repos/yourusername/yourrepo/contents/path/to/yourfile.json"

    payload = json.dumps({
        "codebase": codebase,
        "content": json_data,
    })

    with st.spinner(f"Pushing JSON data to GitHub..."):
        response = requests.post(url, headers=HEADERS, data=payload)

    response = response.json()
    if response[0]['status'] == 'error':
        st.error(f"Error pushing JSON data to GitHub: {response[0]['message']}")
    else:
        st.success("JSON data successfully pushed to GitHub!")
        st.json(response[0]['data'])


