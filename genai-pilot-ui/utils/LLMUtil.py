import requests
import streamlit as st
import json
import os
from constants.server_info import LOCAL_BACKEND_URL, LLM_API_ENDPOINT, HEADERS
from utils.html_extraction_util import extract_data_from_html_table


def SQL_DB_Extraction_v2(data, system_prompt):
    database_information = []
    sql_queries_information = []
    invalid_sql_queries = []

    for result in data:
        codebase = result['page_content']
        file_name = result['metadata']['source']
        st.subheader(file_name)
        _, extension = os.path.splitext(result['metadata']['source'])
        st.code(result['page_content'], language=extension[1:])
        url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"

        payload = json.dumps({
            "system_prompt": system_prompt,
            "user_prompt": "Given the provided code snippet, are there SQL Queries present in the code snipper? Answer 'yes' or 'no'.",
            "codebase": codebase
        })

        with st.spinner("Retrieving data from LLM..."):
            response = requests.request("POST", url, headers=HEADERS, data=payload)

        response_json = response.json()
        status_code = response_json['status_code']

        if status_code == 400:
            st.error(f"Error: No SQL Interaction found.")
        else:
            if 'no' in response_json['output'] or 'No' in response_json['output']:
                st.error("Error: No SQL Interaction found.")
            elif 'yes' in response_json['output']:
                st.success("Successfully identified SQL interaction.")
                st.text("Attempting to extract the SQL Queries")
                payload = json.dumps({
                    "system_prompt": system_prompt,
                    "user_prompt": "Given the provided code snippet, list only the SQL queries that are explicitly present. Do not infer or generate new queries. Identify and reconstruct queries that might be spread across multiple lines. Represent this as a json. 'Queries' and value as an array. Make sure it's a valid json. Do not include comments",
                    "codebase": codebase
                })
                with st.spinner("Retrieving data from LLM..."):
                    response = requests.request("POST", url, headers=HEADERS, data=payload)
                response_json = response.json()
                status_code = response_json['status_code']

                if status_code == 400:
                    st.error(f"Error: {response_json['output']}")
                else:
                    json_extraction = response_json['output']
                    # If start and end or -1 no hits
                    start = json_extraction.find('```')
                    end = json_extraction.rfind('```')
                    if start == -1 or -1:
                        try:
                            queries = json.loads(json_extraction)['Queries']
                        except json.JSONDecodeError:
                            st.error(f"Error: {json_extraction}")
                            continue
                    else:
                        json_data = json.extraction[start + 3:end].strip()
                        try:
                            queries = json.loads(json_data)['Queries']
                        except json.JSONDecodeError:
                            st.error(f"Error: {json_extraction}")
                            continue

                    payload = json.dumps({
                        "system_prompt": system_prompt,
                        "user_prompt": "Are these valid SQL queries? If yes, reply with 'yes'. If no, reply with 'no'.",
                        "codebase": codebase
                    })
                    with st.spinner("Retrieving data from LLM..."):
                        response = requests.request("POST", url, headers=HEADERS, data=payload)
                    response_json = response.json()
                    status_code = response_json['status_code']
                    if status_code == 400:
                        st.error(f"Error: {response_json['output']}")
                    else:
                        if 'yes' in response_json['output']:
                            st.success("Successfully identified SQL Queries.")
                            st.markdown(f"""{queries}""", unsafe_allow_html=True)
                            for query in queries:
                                sql_queries_information.extend(query)
                            else:
                                st.error({file_name: queries})
                                st. error("Error: Invalid SQL Queries.")
                                if queries:
                                    invalid_sql_queries.append({file_name: queries})
                                continue

                        # st.markdown(f"""{response_json['output']}""", unsafe_allow_html=True)

                        st.header("Extracting Database Table / Column Information")
                        payload = json.dumps({
                            "system_prompt": system_prompt,
                            "user_prompt": "List out all table and column names that are being used in the code below. Also infer the data type of the column, and the CRUD operation. Format your reply in an HTML table.",
                            "codebase": codebase
                        })
                        with st.spinner("Retrieving data from LLM..."):
                            response = requests.request("POST", url, headers=HEADERS, data=payload)
                        response_json = response.json()
                        status_code = response_json['status_code']

                        if status_code == 400:
                            st.error(f"Error: {response_json['output']}")
                        else:
                            st.markdown(f"""
                            {response_json['output']}
                            """, unsafe_allow_html=True)
                        db_table_column_json_data = extract_data_from_html_table(response_json['output'], file_name)
                        print(db_table_column_json_data)
                        database_information.append(db_table_column_json_data)
    return database_information, sql_queries_information, invalid_sql_queries








def Server_LLM_Extraction(data, system_prompt):
    host_ports_array = []
    for result in data['results']:
        codebase = result['page_content']
        codebase = codebase.replace("@aexp", "@aexps")
        codebase = codebase.replace("@", "")
        codebase = codebase.replace("aimid", "")

        st.subheader(result['metadata']['source'])

        _, extension = os.path.splitext(result['metadata']['source'])
        st.code(codebase, language=extension[1:])
        if len(codebase) < 4:
            st.error("Error: Codebase is emplty.")
            continue

        # Add this into the workflow to avoid picking up local calls
        # Is this a database server? Answer 'Yes' or 'No'

        payload = json.dumps({
            "system_prompt": system_prompt,
            "user_prompt": "Given the provided code snipper, identify if there are server informations present showing host, port and database information? If none, reply back with 'no'. Else extract the server information. Place in a json with keys 'Host', 'Port', 'Database Name'. Reply with only the JSON. Make sure it's a valid JSON.",
            "codebase": codebase
        })

        with st.spinner("Retrieving data from LLM..."):
            response = requests.request("POST", f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}", headers=HEADERS, data=payload)

        response_json = response.jsdon()

        status_code = response_json['status_code']
        if status_code == 400:
            st.error(f"Filtered: {response_json['output']}")
        else:
            if 'no' in response_json['output'] or 'No' in response_json['output']:
                st.error("Error: No server interactions found.")
                continue
            else:
                st.success("Successfully identified server information.")
                st.header("Extracting Server Information")
                json_extraction = response_json['output']
                st.markdown(f"""{response_json['output']}""", unsafe_allow_html=True)
                try:
                    json_document = json.loads(json_extraction)
                except json.JSONDecodeError:
                    st.error(f"Error: {response_json['output']}")
                    continue
                payload = json.dumps({
                    "system_prompt": system_prompt,
                    "user_prompt": "Is this valid database server information? If yes, reply with 'yes'. If no, reply with 'no'.",
                    "codebase": json_document
                })

                with st.spinner("Retrieving data from LLM..."):
                    response = requests.request("POST", f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}", headers=HEADERS,
                                                data=payload)
                response_json = response.json()
                status_code = response_json['status_code']
                if status_code == 400:
                    st.error(f"Error: {response_json['output']}")
                else:
                    if 'yes' in response_json['output']:
                        st.success("Successfully identified server information.")
                        host_ports_array.append(json_document)
                    else:
                        st.error("Error: Invalid server information.")
                        continue

    # Filter out duplicate entries
    host_ports_array = [dict(t) for t in {tuple(d.items()) for d in host_ports_array}]
    return host_ports_array



