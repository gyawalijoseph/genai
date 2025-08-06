import streamlit as st

from utils.githubUtil import commit_json
from utils.vectorSearchUtil import vector_search
from utils.LLMUtil import Server_LLM_Extraction
from constants.server_info import SERVER_SYSTEM_PROMPT, SIMILARITY_SEARCH_QUERY_INPUT, SYSTEM_PROMPT_INPUT
from utils.LLMUtil import SQL_DB_Extraction_v2

def generate_spec(codebase, vector_results_count):
    json_document = {}

    # Car Info
    st.title("Car Info")
    metadata = fetch_metadata(codebase)
    if metadata is not None:
        json_document['Application'] = metadata
    st.markdown("---")

    st.title("Server Info")
    data = vector_search(codebase + "-external-files", "server host", vector_results_count)
    server_information = Server_LLM_Extraction(data, SERVER_SYSTEM_PROMPT)
    st.json(server_information)
    st.markdown("---")

    st.title(f"Database Info")
    data = vector_search(codebase, SIMILARITY_SEARCH_QUERY_INPUT, vector_results_count)
    external_data = vector_search(codebase + "-external-files", SIMILARITY_SEARCH_QUERY_INPUT, vector_results_count)

    st.title("Running code through System/User prompt on LLM")

    # Tables_Columns_Response, Queries_Response = SQL_DB_Extraction(data, SYSTEM_PROMPT_INPUT)
    Tables_Columns_Response_internal, Queries_Response_internal, invalid_sql_queuries_internal = SQL_DB_Extraction_v2(
        data['results'], SYSTEM_PROMPT_INPUT)
    Tables_Columns_Response_external, Queries_Response_external, invalid_sql_queuries_external = SQL_DB_Extraction_v2(
        data['results'], SYSTEM_PROMPT_INPUT)

    Tables_Columns_Response = Tables_Columns_Response_internal + Tables_Columns_Response_external
    Queries_Response = Queries_Response_internal + Queries_Response_external

    json_document["Database Information"] = {}
    json_document["Database Information"]["Table Information"] = []
    json_document["Database Information"]["SQL Queries"] = []

    if Tables_Columns_Response is not None:
        json_document["Database Information"]["Table Information"] = Tables_Columns_Response

    if Queries_Response is not None:
        json_document["Database Information"]["SQL Queries"] = list(Queries_Response)

    if invalid_sql_queuries_internal is not None:
        json_document["Database Information"]["Invalid SQL Queries"] = invalid_sql_queuries_internal
    st.markdown("---")
    json_document["Database Information"]["Server Information"] = server_information


    st.title("Summary")
    st.json(json_document)
    st.text(commit_json(codebase, json_document))

def main():
    st.title("Spec Generation")
    codebase = st.text_input("Codebase Name: ")
    vector_results_count = st.text_input('Codebase name: ', value=10)
    submit_button = st.button('submit')

    if submit_button and codebase and vector_results_count:
        generate_spec(codebase, vector_results_count)
    elif submit_button or codebase:
        if not codebase:
            st.error("Please enter a codebase")
        if not vector_results_count:
            st.error("Please enter a value for vector similarity search results")
        else:
            st.error(
                f"Embeddings for {codebase} does not exist. \n\n Please use embedding generation section to create embeddings")

if __name__ == "__main__":
    main()