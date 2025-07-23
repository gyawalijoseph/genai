# Server Component Extraction - End-to-End Flow

## Overview

This document explains the complete flow for extracting server information from a codebase, showing exactly how embeddings are pulled and processed to produce the expected output format.

## 🎯 Expected Output Format

```json
{
  "Server Information": {
    "host": "abc.phx.com",
    "port": 1234,
    "database name": "postgres"
  }
}
```

## 🔄 Complete End-to-End Flow

### Step 1: API Request
**Endpoint**: `POST /api/extract-component`
```json
{
  "codebase": "my-spring-app",
  "component": "server",
  "max_results": 10
}
```

### Step 2: Vector Search for Server-Related Embeddings
```python
# Location: services/spec_extraction_service_updated.py:_get_codebase_documents()

# Search query specifically for server interactions
search_queries = [
    ("server host port configuration endpoint", "server configuration"),
    # Other queries for different components...
]

# Pull embeddings using your existing function
from utilities.utils import similarity_search_pgvector

# Internal codebase search
docs = similarity_search_pgvector(
    codebase="my-spring-app",                    # Your codebase name
    query="server host port configuration endpoint",  # Server-specific query
    vector_results_count=10                      # Max results
)

# External configuration files search
external_docs = similarity_search_pgvector(
    codebase="my-spring-app-external-files",    # External files collection
    query="server host port configuration endpoint",
    vector_results_count=10
)
```

**What Gets Retrieved:**
- Configuration files (application.properties, application.yml)
- Database connection strings
- Server configuration classes
- Environment variable definitions
- Deployment configuration files

### Step 3: Parallel Processing with Safechain
```python
# Location: services/spec_extraction_service_updated.py:_parallel_extract_with_safechain()

# Each document is processed in parallel using your safechain_llm_call
with ThreadPoolExecutor(max_workers=4) as executor:
    for doc in server_related_documents:
        future = executor.submit(
            self.extractor.extract_with_safechain,
            doc['page_content'],    # The actual code/config content
            "server",               # Extraction type
            doc['metadata']['source']  # File name
        )
```

### Step 4: Safechain LLM Call for Each Document
```python
# Location: services/spec_extraction_service_updated.py:extract_with_safechain()

# Uses your exact safechain_llm_call pattern
from utilities.utils import safechain_llm_call

# System prompt optimized for server extraction
system_prompt = """You are an expert system configuration analyzer. 
Extract server and configuration information from code/config files.
Focus on: hosts, ports, URLs, service endpoints, environment variables, connection details."""

# User prompt with specific format requirements
user_prompt = """Extract server information from this code and return ONLY valid JSON in this exact format:
{
  "hosts": ["hostname1", "hostname2"],
  "ports": ["8080", "3000"],
  "endpoints": ["http://localhost:8080/api", "https://api.example.com"],
  "config": {"database_name": "postgres", "key2": "value2"}
}

If no server information is found, return:
{"hosts": [], "ports": [], "endpoints": [], "config": {}}"""

# Your safechain call
result_text, status_code = safechain_llm_call(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    codebase=document_content,  # The actual code/config from embeddings
    max_retries=3,
    delay=2
)
```

### Step 5: Example Document Processing

**Input Document** (from embeddings):
```yaml
# application.yml
server:
  port: 8080
  host: abc.phx.com

spring:
  datasource:
    url: jdbc:postgresql://abc.phx.com:5432/postgres
    username: admin
    password: ${DB_PASSWORD}

management:
  server:
    port: 9090
```

**Safechain LLM Call Result**:
```json
{
  "hosts": ["abc.phx.com"],
  "ports": ["8080", "5432", "9090"],
  "endpoints": ["jdbc:postgresql://abc.phx.com:5432/postgres"],
  "config": {
    "database_name": "postgres",
    "management_port": "9090",
    "datasource_url": "jdbc:postgresql://abc.phx.com:5432/postgres"
  }
}
```

### Step 6: Fallback Processing (if Safechain Fails)
```python
# Location: services/spec_extraction_service_updated.py:_regex_fallback()

# If safechain_llm_call fails, use regex patterns
server_patterns = [
    (r'(?i)(?:host|server|endpoint)["\s]*[=:]["\s]*([^"\s,;}{]+)', 'hosts'),
    (r'(?i)port["\s]*[=:]["\s]*(\d+)', 'ports'),
    (r'(https?://[^/\s"\'><}{]+)', 'endpoints'),
    (r'(?i)database["\s]*[=:]["\s]*([^"\s,;}{]+)', 'config')
]

# Extract using regex patterns
for pattern, category in server_patterns:
    matches = re.findall(pattern, document_content)
    # Process matches...
```

### Step 7: Result Aggregation
```python
# Location: services/spec_extraction_service_updated.py:_aggregate_results()

# Combine results from all documents
all_hosts = []
all_ports = []
all_endpoints = []
all_config = {}

for result in server_extraction_results:
    if result.success and result.data:
        data = result.data
        all_hosts.extend(data.get("hosts", []))
        all_ports.extend(data.get("ports", []))
        all_endpoints.extend(data.get("endpoints", []))
        all_config.update(data.get("config", {}))

# Remove duplicates and create final structure
server_info = {
    "hosts": list(dict.fromkeys(all_hosts)),
    "ports": list(dict.fromkeys(all_ports)),
    "endpoints": list(dict.fromkeys(all_endpoints)),
    "configuration": all_config
}
```

### Step 8: Final Response Formatting
```python
# Location: endpoints/spec_generation_clean.py:extract_component()

# Format for your expected output structure
if component == 'server':
    component_data = spec_data.server_info  # From aggregation step

# API Response
{
  "status": "success",
  "codebase": "my-spring-app",
  "component": "server",
  "data": [
    {
      "hosts": ["abc.phx.com"],
      "ports": ["8080", "5432", "9090"],
      "endpoints": ["jdbc:postgresql://abc.phx.com:5432/postgres"],
      "configuration": {
        "database_name": "postgres",
        "management_port": "9090"
      }
    }
  ]
}
```

## 🔍 Key Integration Points

### 1. Uses Your Existing Vector Search
```python
# Pulls embeddings from your PGVector database
similarity_search_pgvector(
    codebase=codebase,                           # Your codebase collection
    query="server host port configuration",     # Server-specific query
    vector_results_count=max_results            # Configurable limit
)
```

### 2. Uses Your Safechain Pattern
```python
# Every LLM call goes through your existing function
safechain_llm_call(
    system_prompt=server_analysis_prompt,
    user_prompt=json_extraction_prompt,
    codebase=document_content,
    max_retries=3,
    delay=2
)
```

### 3. Handles Your Configuration
```python
# Uses your existing get_connection setup
vectorstore = get_connection('1', {
    "collection_name": codebase,
    "embedding_model_index": "ada-3",
    "schema": "tapld00"
})
```

## 📊 Example Full Flow

### Input
```bash
curl -X POST http://localhost:8082/api/extract-component \
  -H "Content-Type: application/json" \
  -d '{
    "codebase": "my-spring-app",
    "component": "server",
    "max_results": 10
  }'
```

### Processing Steps
1. **Vector Search**: Finds 8 documents with server-related content
2. **Parallel Processing**: 4 workers process documents simultaneously
3. **Safechain Calls**: Each document processed with your LLM pattern
4. **Aggregation**: Results combined and deduplicated
5. **Response**: Structured server information returned

### Output
```json
{
  "status": "success",
  "codebase": "my-spring-app",
  "component": "server",
  "extraction_time_seconds": 3.2,
  "data": [
    {
      "hosts": ["abc.phx.com", "localhost"],
      "ports": ["8080", "5432", "9090"],
      "endpoints": [
        "http://abc.phx.com:8080/api",
        "jdbc:postgresql://abc.phx.com:5432/postgres"
      ],
      "configuration": {
        "database_name": "postgres",
        "server_port": "8080",
        "management_port": "9090",
        "profile": "production"
      }
    }
  ],
  "statistics": {
    "hosts_found": 2,
    "ports_found": 3,
    "endpoints_found": 2
  }
}
```

## 🎯 Mapping to Your Expected Format

The system can easily transform the detailed output to your simplified format:

**Current Output**:
```json
{
  "hosts": ["abc.phx.com"],
  "ports": ["5432"],
  "configuration": {"database_name": "postgres"}
}
```

**Your Expected Format**:
```json
{
  "Server Information": {
    "host": "abc.phx.com",
    "port": 5432,
    "database name": "postgres"
  }
}
```

This is just a matter of response formatting - the extraction logic captures all the required information.