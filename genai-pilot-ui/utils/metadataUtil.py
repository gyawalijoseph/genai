import streamlit as st
import json
import requests
from constants.server_info import LOCAL_BACKEND_URL, FETCH_METADATA_ENDPOINT, HEADERS

def fetch_metadata(codebase):
    url = f"{LOCAL_BACKEND_URL}{FETCH_METADATA_ENDPOINT}"

    payload = json.dumps({
        "codebase": codebase
    })

    with st.spinner("Please wait while we retrieve metadata information..."):
        response = requests.request("POST", url, headers=HEADERS, data=payload)
    
    response_data = response.json()
    status_code = response.status_code
    if status_code == 400:
        st.error(f"{response_data}")
        return None
    else:
        application_name = response_data["Application Name"]
        application_type = response_data["Application Type"]
        central_id = response_data["Central ID"]
        company_platform = response_data["Company Platform"]
        tech_platform = response_data["Tech Platform"]
        target_production_environment = response_data["Target Production Environment"]
        hosting_environment = response_data["Hosting Environment"]
        internet_facing = response_data["Internet Facing"]
        data_classification = response_data["Data Classification"]

        st.markdown(f"""
           **Name:** {application_name}\n\n
           **Type:** {application_type}\n\n
           **Central ID:** {central_id}\n\n
           **Company Platform:** {company_platform}\n\n
           **Tech Platform:** {tech_platform}\n\n
           **Target Production Environment:** {target_production_environment}\n\n
           **Hosting Environment:** {hosting_environment}\n\n
           **Internet Facing:** {internet_facing}\n\n
           **Data Classification:** {data_classification}\n\n
        """, unsafe_allow_html=True)

        return {
            "Information": {
                "Name": application_name,
                "Type": application_type,
                "Central ID": central_id,
                "Company Platform": company_platform,
                "Tech Platform": tech_platform
            },
            "Architecture": {
                "Target Production Environment": target_production_environment,
                "Hosting Environment": hosting_environment,
                "Internet Facing": "No" if internet_facing == "None" else "Yes",
            },
            "Risk": {
                "Data Classification": data_classification
            },
            "Regulatory": {
                "Sensitive Data Elements (SDE) / Personally Identifiable Information (PII)": "No" if data_classification == "None" else "Yes",
            }
        }
        
        