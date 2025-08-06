import streamlit as st
import requests
import json
import os
import re
from datetime import datetime

# Configuration
LOCAL_BACKEND_URL = "http://localhost:5000"
LLM_API_ENDPOINT = "/LLM-API"
HEADERS = {"Content-Type": "application/json"}


def vector_search_single(codebase, similarity_search_query, vector_results_count, search_suffix):
    """Single vector search implementation for one database"""
    search_target = f"{codebase}{search_suffix}"
    url = "http://localhost:5000/vector-search"
    payload = {
        "codebase": search_target,
        "query": similarity_search_query,
        "vector_results_count": vector_results_count
    }

    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=60)

        if response.status_code != 200:
            return {"results": [], "search_target": search_target, "success": False}

        data = response.json()

        if not isinstance(data, dict) or 'results' not in data:
            return {"results": [], "search_target": search_target, "success": False}

        if not data['results']:
            return {"results": [], "search_target": search_target, "success": True}

        # Add search target info to each result
        for result in data['results']:
            result['search_target'] = search_target
            
        return {"results": data['results'], "search_target": search_target, "success": True}

    except Exception as e:
        return {"results": [], "search_target": search_target, "success": False}


def vector_search_multiple(codebase, similarity_search_query, vector_results_count, search_suffixes=["-external-files", ""]):
    """Multiple vector search implementation that searches both external files and actual codebase"""
    all_results = []
    search_summary = []
    
    for suffix in search_suffixes:
        search_name = f"{codebase}{suffix}" if suffix else codebase
        
        result = vector_search_single(codebase, similarity_search_query, vector_results_count, suffix)
        
        search_summary.append({
            "database": search_name,
            "results_count": len(result['results']),
            "success": result['success']
        })
        
        if result['results']:
            all_results.extend(result['results'])
    
    return {"results": all_results, "search_summary": search_summary}


def robust_json_parse(text_output, file_source="unknown"):
    """Robust JSON parsing with multiple fallback strategies"""
    if not text_output or not text_output.strip():
        return None, "Empty output from LLM"
    
    # Strategy 1: Direct JSON parsing
    try:
        return json.loads(text_output), None
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([^`]+)\s*```', text_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip()), None
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Extract JSON-like content between { and }
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0)), None
        except json.JSONDecodeError:
            pass
    
    # Strategy 4: Try to fix common JSON issues
    cleaned_text = text_output.strip()
    
    # Remove common prefixes/suffixes
    prefixes_to_remove = ['Here is the JSON:', 'JSON:', 'Result:', 'Output:']
    for prefix in prefixes_to_remove:
        if cleaned_text.startswith(prefix):
            cleaned_text = cleaned_text[len(prefix):].strip()
    
    # Try to extract anything that looks like JSON
    if '{' in cleaned_text and '}' in cleaned_text:
        start_idx = cleaned_text.find('{')
        end_idx = cleaned_text.rfind('}') + 1
        potential_json = cleaned_text[start_idx:end_idx]
        
        try:
            return json.loads(potential_json), None
        except json.JSONDecodeError:
            pass
    
    # Strategy 5: Create structured fallback
    text_stripped = text_output.strip().lower()
    if (text_stripped == 'no' or 
        text_stripped.startswith('no.') or 
        text_stripped.startswith('no,') or
        text_stripped.startswith('no ') or
        'no database' in text_stripped or
        'no server' in text_stripped or
        'none found' in text_stripped):
        return None, "LLM indicated no information found"
    
    # If all else fails, create a simple fallback structure
    fallback_data = {
        "source_file": file_source,
        "raw_llm_output": text_output[:500] + "..." if len(text_output) > 500 else text_output,
        "parsing_error": "Could not parse as valid JSON",
        "extraction_status": "partial"
    }
    
    return fallback_data, "Used fallback structure due to JSON parsing failure"


def deduplicate_server_info(server_info_array):
    """Remove duplicate server information based on host, port, and database_name"""
    if not server_info_array:
        return []
    
    seen_servers = set()
    deduplicated = []
    
    for server_info in server_info_array:
        if not isinstance(server_info, dict):
            continue
            
        # Create a key based on host, port, and database_name
        host = server_info.get('host', '').strip().lower()
        port = str(server_info.get('port', '')).strip()
        db_name = server_info.get('database_name', '').strip().lower()
        
        # Create unique key
        server_key = f"{host}:{port}:{db_name}"
        
        if server_key not in seen_servers and (host or port or db_name):
            seen_servers.add(server_key)
            deduplicated.append(server_info)
        elif server_key in seen_servers:
            continue  # Skip duplicates silently in batch mode
    
    return deduplicated


def extract_server_information_batch(data, system_prompt, vector_query):
    """Extract server information for batch processing (less verbose)"""
    server_info_array = []

    for i, result in enumerate(data['results'], 1):
        try:
            codebase = result['page_content']
            file_source = result['metadata']['source']

            # Apply text cleaning
            codebase = codebase.replace("@aexp", "@aexps")
            codebase = codebase.replace("@", "")
            codebase = codebase.replace("aimid", "")

            if len(codebase) < 4:
                continue

            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Server information detection
            detection_prompt = "Given the provided code snippet, identify if there are server informations present showing host, port and database information? If none, reply back with 'no'. Else extract the server information. Place in a json with keys 'host', 'port', 'database_name'. Reply with only the JSON. Make sure it's a valid JSON."

            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase
            }

            try:
                response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

                if response.status_code != 200:
                    continue

                try:
                    response_json = response.json()
                except json.JSONDecodeError:
                    continue

                status_code = response_json.get('status_code', response.status_code)
                output = response_json.get('output', '')

                if status_code != 200:
                    continue

                # Check if no server information found
                output_stripped = output.strip().lower()
                if (output_stripped == 'no' or 
                    output_stripped.startswith('no.') or 
                    'no server' in output_stripped):
                    continue

                # Parse JSON response
                json_document, parse_error = robust_json_parse(output, file_source)
                
                if json_document is not None:
                    server_info_array.append(json_document)

            except Exception:
                continue

        except Exception:
            continue

    # Deduplicate server information before returning
    deduplicated_servers = deduplicate_server_info(server_info_array)
    return deduplicated_servers


def extract_database_information_batch(data, system_prompt, vector_query):
    """Extract database information for batch processing (less verbose)"""
    database_info_array = []

    for i, result in enumerate(data['results'], 1):
        try:
            codebase = result['page_content']
            file_source = result['metadata']['source']

            # Apply text cleaning
            codebase = codebase.replace("@aexp", "@aexps")
            codebase = codebase.replace("@", "")
            codebase = codebase.replace("aimid", "")

            if len(codebase) < 4:
                continue

            url = f"{LOCAL_BACKEND_URL}{LLM_API_ENDPOINT}"

            # Database information detection
            detection_prompt = "Given the provided code snippet, identify if there are database-related configurations, connections, or queries present? If none, reply back with 'no'. Else extract the database information. Place in a json with keys for any database-related information found. Reply with only the JSON. Make sure it's a valid JSON."

            payload = {
                "system_prompt": system_prompt,
                "user_prompt": detection_prompt,
                "codebase": codebase
            }

            try:
                response = requests.post(url, json=payload, headers=HEADERS, timeout=300)

                if response.status_code != 200:
                    continue

                try:
                    response_json = response.json()
                except json.JSONDecodeError:
                    continue

                status_code = response_json.get('status_code', response.status_code)
                output = response_json.get('output', '')

                if status_code != 200:
                    continue

                # Check if no database information found
                output_stripped = output.strip().lower()
                if (output_stripped == 'no' or 
                    output_stripped.startswith('no.') or 
                    'no database' in output_stripped):
                    continue

                # Parse JSON response
                json_document, parse_error = robust_json_parse(output, file_source)
                
                if json_document is not None:
                    database_info_array.append(json_document)

            except Exception:
                continue

        except Exception:
            continue

    return database_info_array


def validate_sql_basic(query):
    """Basic SQL validation to check if query looks complete"""
    query_lower = query.lower().strip()
    
    # Check for basic SQL structure
    if query_lower.startswith('select'):
        return 'from' in query_lower
    elif query_lower.startswith('insert'):
        return 'into' in query_lower and ('values' in query_lower or 'select' in query_lower)
    elif query_lower.startswith('update'):
        return 'set' in query_lower
    elif query_lower.startswith('delete'):
        return 'from' in query_lower
    elif query_lower.startswith(('create', 'drop', 'alter')):
        return len(query_lower) > 15
    
    return False


def extract_sql_from_codebase(codebase):
    """Extract SQL queries from original codebase using pattern matching"""
    queries = []
    
    # SQL patterns - look for multiline SQL statements
    sql_patterns = [
        r'(?i)(SELECT\s+[\s\S]*?FROM\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
        r'(?i)(INSERT\s+INTO\s+[\s\S]*?VALUES\s*\([^)]*\))',
        r'(?i)(UPDATE\s+[\s\S]*?SET\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
        r'(?i)(DELETE\s+FROM\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
        r'(?i)(CREATE\s+TABLE\s+[\s\S]*?)(?=[;\n]\s*[A-Z]|\n\s*\n|$)',
    ]
    
    for pattern in sql_patterns:
        matches = re.findall(pattern, codebase, re.MULTILINE | re.DOTALL)
        for match in matches:
            cleaned = re.sub(r'\s+', ' ', match.strip())
            if len(cleaned) > 15 and validate_sql_basic(cleaned):
                queries.append(cleaned)
    
    return queries


def infer_data_type(key, value, original_codebase):
    """Infer data type from key name, value, and codebase context"""
    key_lower = key.lower()
    value_str = str(value).lower()
    
    # Check for explicit type mentions in the key or value
    type_indicators = {
        'string': ['name', 'title', 'description', 'text', 'varchar', 'char'],
        'integer': ['id', 'count', 'number', 'int', 'age', 'year'],
        'boolean': ['is_', 'has_', 'active', 'enabled', 'bool'],
        'datetime': ['date', 'time', 'created', 'updated', 'timestamp'],
        'decimal': ['price', 'amount', 'rate', 'decimal', 'float'],
        'json': ['config', 'settings', 'data', 'json']
    }
    
    for data_type, indicators in type_indicators.items():
        if any(indicator in key_lower for indicator in indicators):
            return data_type
        if any(indicator in value_str for indicator in indicators):
            return data_type
    
    return 'string'  # Default fallback


def infer_crud_operations(original_codebase, table_name, column_name=None):
    """Infer CRUD operations from codebase analysis"""
    if not original_codebase:
        return 'UNKNOWN'
    
    codebase_lower = original_codebase.lower()
    table_lower = table_name.lower()
    operations = set()
    
    # Check for SQL operations on this table
    if f'select * from {table_lower}' in codebase_lower or f'select' in codebase_lower and table_lower in codebase_lower:
        operations.add('READ')
    
    if f'insert into {table_lower}' in codebase_lower:
        operations.add('CREATE')
    
    if f'update {table_lower}' in codebase_lower:
        operations.add('UPDATE')
    
    if f'delete from {table_lower}' in codebase_lower:
        operations.add('DELETE')
    
    return ','.join(sorted(operations)) if operations else 'READ'


def transform_extracted_data_batch(db_info_list, all_vector_results, system_prompt):
    """Transform extracted data into final structure for batch processing (simplified)"""
    final_output = {
        "Table Information": [],
        "SQL_QUERIES": [],
        "Invalid_SQL_Queries": []
    }
    
    if not db_info_list:
        return final_output
    
    # Process each extracted database entry
    for i, db_entry in enumerate(db_info_list):
        if not isinstance(db_entry, dict):
            continue
        
        # Get source file information
        source_file = f"extracted_data_{i+1}.unknown"
        if len(all_vector_results) > i:
            source_file = all_vector_results[i].get('metadata', {}).get('source', source_file)
        
        # Get original codebase content for reference
        original_codebase = ""
        if len(all_vector_results) > i:
            original_codebase = all_vector_results[i].get('page_content', '')
        
        # Process Table Information
        table_entry = {source_file: {}}
        table_found = False
        
        # Look through the extracted data for table information
        for key, value in db_entry.items():
            key_lower = key.lower()
            
            # Check for table-related keys
            if any(keyword in key_lower for keyword in ['table', 'schema', 'model', 'entity']):
                if isinstance(value, str) and value.strip():
                    table_name = value.strip()
                    table_entry[source_file][table_name] = {
                        "Field Information": [{
                            "column_name": f"extracted_from_{key}",
                            "data_type": infer_data_type(key, value, original_codebase),
                            "CRUD": infer_crud_operations(original_codebase, table_name)
                        }]
                    }
                    table_found = True
                elif isinstance(value, list):
                    for table_name in value:
                        if isinstance(table_name, str) and table_name.strip():
                            table_entry[source_file][table_name] = {
                                "Field Information": [{
                                    "column_name": f"from_{key}",
                                    "data_type": infer_data_type(key, table_name, original_codebase),
                                    "CRUD": infer_crud_operations(original_codebase, table_name)
                                }]
                            }
                            table_found = True
        
        if table_found and table_entry[source_file]:
            final_output["Table Information"].append(table_entry)
        
        # Process SQL Queries
        for key, value in db_entry.items():
            if isinstance(value, str):
                value_lower = value.lower()
                if any(sql_keyword in value_lower for sql_keyword in ['select', 'insert', 'update', 'delete', 'create', 'drop']):
                    cleaned_query = value.strip()
                    if len(cleaned_query) > 10 and validate_sql_basic(cleaned_query):
                        final_output["SQL_QUERIES"].append(cleaned_query)
                    else:
                        final_output["Invalid_SQL_Queries"].append({
                            "source_file": source_file,
                            "query": cleaned_query,
                            "reason": "Invalid SQL syntax or too short"
                        })
        
        # Also scan the original codebase for SQL patterns
        if original_codebase:
            codebase_queries = extract_sql_from_codebase(original_codebase)
            for query in codebase_queries:
                if query not in final_output["SQL_QUERIES"]:
                    final_output["SQL_QUERIES"].append(query)
    
    return final_output