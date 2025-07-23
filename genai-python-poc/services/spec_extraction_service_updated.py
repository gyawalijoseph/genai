"""
Dynamic Specification Extraction Service - Updated
Uses safechain_llm_call pattern as foundation with LangChain integration
"""
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time

from utilities.utils import safechain_llm_call, similarity_search_pgvector

logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    """Standardized result structure"""
    success: bool
    data: Any
    source: str
    extraction_type: str
    confidence: float = 0.0
    errors: List[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class SpecificationData:
    """Complete specification structure"""
    codebase: str
    server_info: List[Dict] = None
    database_info: Dict = None
    api_endpoints: List[str] = None
    dependencies: List[str] = None
    configuration: Dict = None
    summary: Dict = None
    
    def __post_init__(self):
        self.server_info = self.server_info or []
        self.database_info = self.database_info or {
            "tables": [], "queries": [], "connections": []
        }
        self.api_endpoints = self.api_endpoints or []
        self.dependencies = self.dependencies or []
        self.configuration = self.configuration or {}
        self.summary = self.summary or {}

class SafeChainExtractor:
    """Extraction engine using your safechain_llm_call pattern"""
    
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.delay = 2  # seconds between retries
        self._setup_extraction_prompts()
    
    def _setup_extraction_prompts(self):
        """Define system and user prompts for different extraction types"""
        
        self.extraction_prompts = {
            "sql": {
                "system": """You are an expert database analyzer. Extract database-related information from code.
Focus on: SQL queries, table names, column names, database connections, ORM operations.
Be thorough but accurate - only extract what is actually present in the code.""",
                
                "user": """Analyze this code for database information and return ONLY valid JSON in this exact format:
{
  "queries": ["actual SQL query 1", "actual SQL query 2"],
  "tables": ["table_name_1", "table_name_2"], 
  "connections": ["connection_string_1", "connection_string_2"]
}

If no database information is found, return:
{"queries": [], "tables": [], "connections": []}

Do not include explanations, comments, or markdown formatting."""
            },
            
            "server": {
                "system": """You are an expert system configuration analyzer. Extract server and configuration information from code/config files.
Focus on: hosts, ports, URLs, service endpoints, environment variables, connection details.""",
                
                "user": """Extract server information from this code and return ONLY valid JSON in this exact format:
{
  "hosts": ["hostname1", "hostname2"],
  "ports": ["8080", "3000"],
  "endpoints": ["http://localhost:8080/api", "https://api.example.com"],
  "config": {"key1": "value1", "key2": "value2"}
}

If no server information is found, return:
{"hosts": [], "ports": [], "endpoints": [], "config": {}}

Do not include explanations, comments, or markdown formatting."""
            },
            
            "api": {
                "system": """You are an expert API analyzer. Extract API endpoints and routes from code.
Focus on: REST endpoints, GraphQL, RPC calls, route definitions, controller mappings.""",
                
                "user": """Find all API endpoints in this code and return ONLY a valid JSON array:
["GET /api/users", "POST /api/orders", "/graphql", "PUT /api/products/{id}"]

Include the HTTP method if available. If no API endpoints found, return: []

Do not include explanations, comments, or markdown formatting."""
            },
            
            "dependencies": {
                "system": """You are an expert dependency analyzer. Extract dependencies and imports from code.
Focus on: external libraries, frameworks, services, modules, packages.""",
                
                "user": """Extract all dependencies from this code and return ONLY a valid JSON array:
["spring-boot-starter-web", "postgresql", "redis", "lombok", "jackson"]

Include library names, frameworks, and external services. If no dependencies found, return: []

Do not include explanations, comments, or markdown formatting."""
            }
        }
    
    def extract_with_safechain(self, code: str, extraction_type: str, file_source: str = "unknown") -> ExtractionResult:
        """Extract information using safechain_llm_call pattern with fallbacks"""
        
        if extraction_type not in self.extraction_prompts:
            return ExtractionResult(
                success=False,
                data=self._empty_structure(extraction_type),
                source=file_source,
                extraction_type=extraction_type,
                errors=[f"Unknown extraction type: {extraction_type}"]
            )
        
        prompts = self.extraction_prompts[extraction_type]
        
        # Strategy 1: Use safechain_llm_call (primary method)
        try:
            logger.debug(f"Extracting {extraction_type} from {file_source} using safechain_llm_call")
            
            result_text, status_code = safechain_llm_call(
                system_prompt=prompts["system"],
                user_prompt=prompts["user"],
                codebase=code,
                max_retries=self.max_retries,
                delay=self.delay
            )
            
            if status_code == 200:
                # Parse the JSON response
                parsed_data = self._safe_json_parse(result_text)
                
                if parsed_data is not None:
                    return ExtractionResult(
                        success=True,
                        data=parsed_data,
                        source=file_source,
                        extraction_type=extraction_type,
                        confidence=0.9
                    )
                else:
                    logger.warning(f"Failed to parse JSON from safechain_llm_call for {extraction_type}")
            else:
                logger.warning(f"safechain_llm_call failed with status {status_code}: {result_text}")
                
        except Exception as e:
            logger.warning(f"safechain_llm_call failed for {extraction_type}: {e}")
        
        # Strategy 2: Regex-based fallback
        logger.debug(f"Falling back to regex extraction for {extraction_type}")
        regex_data = self._regex_fallback(code, extraction_type)
        if regex_data:
            return ExtractionResult(
                success=True,
                data=regex_data,
                source=file_source,
                extraction_type=extraction_type,
                confidence=0.6
            )
        
        # Strategy 3: Return empty but valid structure
        return ExtractionResult(
            success=True,
            data=self._empty_structure(extraction_type),
            source=file_source,
            extraction_type=extraction_type,
            confidence=0.1
        )
    
    def _safe_json_parse(self, text: str) -> Optional[Dict]:
        """Safely parse JSON with multiple strategies"""
        if not text or not isinstance(text, str):
            return None
        
        # Clean the text
        text = text.strip()
        
        # Strategy 1: Direct parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract from code blocks
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Match nested JSON objects
            r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]'  # Match JSON arrays
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    cleaned_match = match.strip()
                    if cleaned_match:
                        return json.loads(cleaned_match)
                except json.JSONDecodeError:
                    continue
        
        # Strategy 3: Try to find any JSON-like structure
        try:
            # Look for anything that starts with { or [
            json_start = -1
            for i, char in enumerate(text):
                if char in '{[':
                    json_start = i
                    break
            
            if json_start >= 0:
                # Find the matching closing bracket
                bracket_count = 0
                closing_char = '}' if text[json_start] == '{' else ']'
                
                for i in range(json_start, len(text)):
                    if text[i] in '{[':
                        bracket_count += 1
                    elif text[i] in '}]':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_text = text[json_start:i+1]
                            return json.loads(json_text)
        except:
            pass
        
        return None
    
    def _regex_fallback(self, code: str, extraction_type: str) -> Optional[Dict]:
        """Regex-based extraction as fallback"""
        
        if extraction_type == "sql":
            sql_patterns = [
                r'(?i)(SELECT\s+(?:(?!SELECT|INSERT|UPDATE|DELETE)[^;])+)',
                r'(?i)(INSERT\s+INTO\s+\w+(?:(?!SELECT|INSERT|UPDATE|DELETE)[^;])*)',
                r'(?i)(UPDATE\s+\w+\s+SET(?:(?!SELECT|INSERT|UPDATE|DELETE)[^;])*)',
                r'(?i)(DELETE\s+FROM\s+\w+(?:(?!SELECT|INSERT|UPDATE|DELETE)[^;])*)',
                r'(?i)(CREATE\s+TABLE\s+\w+(?:(?!SELECT|INSERT|UPDATE|DELETE)[^;])*)'
            ]
            
            queries = []
            tables = set()
            
            for pattern in sql_patterns:
                matches = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
                for match in matches:
                    cleaned_query = re.sub(r'\s+', ' ', match.strip())
                    if len(cleaned_query) > 10:  # Filter out very short matches
                        queries.append(cleaned_query[:300])  # Limit length
                        
                        # Extract table names
                        table_patterns = [
                            r'(?i)FROM\s+(\w+)',
                            r'(?i)INTO\s+(\w+)',
                            r'(?i)UPDATE\s+(\w+)',
                            r'(?i)TABLE\s+(\w+)'
                        ]
                        for table_pattern in table_patterns:
                            table_matches = re.findall(table_pattern, match)
                            tables.update(table_matches)
            
            if queries or tables:
                return {
                    "queries": queries,
                    "tables": list(tables),
                    "connections": []
                }
        
        elif extraction_type == "server":
            server_patterns = [
                (r'(?i)(?:host|server|endpoint)["\s]*[=:]["\s]*([^"\s,;}{]+)', 'hosts'),
                (r'(?i)port["\s]*[=:]["\s]*(\d+)', 'ports'),
                (r'(https?://[^/\s"\'><}{]+)', 'endpoints'),
                (r'(?i)database["\s]*[=:]["\s]*([^"\s,;}{]+)', 'config')
            ]
            
            result = {"hosts": [], "ports": [], "endpoints": [], "config": {}}
            
            for pattern, category in server_patterns:
                matches = re.findall(pattern, code)
                if category == 'config':
                    for match in matches:
                        result['config']['database'] = match
                else:
                    result[category].extend(matches)
            
            # Remove duplicates
            for key in ['hosts', 'ports', 'endpoints']:
                result[key] = list(set(result[key]))
            
            if any(result[key] for key in ['hosts', 'ports', 'endpoints']) or result['config']:
                return result
        
        elif extraction_type == "api":
            api_patterns = [
                r'@(?:Get|Post|Put|Delete|Patch)Mapping\(["\']([^"\']+)["\']',
                r'app\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                r'router\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                r'Route\(["\']([^"\']+)["\']',
                r'(?:GET|POST|PUT|DELETE|PATCH)\s+([/\w\-\{\}]+)',
                r'@RequestMapping\(["\']([^"\']+)["\']',
                r'@Path\(["\']([^"\']+)["\']'
            ]
            
            endpoints = []
            for pattern in api_patterns:
                matches = re.findall(pattern, code, re.IGNORECASE)
                endpoints.extend(matches)
            
            # Clean and deduplicate
            cleaned_endpoints = []
            for endpoint in endpoints:
                if endpoint.startswith('/') or endpoint.startswith('http'):
                    cleaned_endpoints.append(endpoint)
            
            return list(set(cleaned_endpoints)) if cleaned_endpoints else None
        
        elif extraction_type == "dependencies":
            dep_patterns = [
                r'import\s+([^;\n\s]+)',
                r'from\s+([^\s]+)\s+import',
                r'require\(["\']([^"\']+)["\']',
                r'<dependency>.*?<groupId>([^<]+)</groupId>.*?<artifactId>([^<]+)</artifactId>',
                r'"([^"@]+)"\s*:\s*"[^"]+"',  # package.json style
                r'implementation\s+["\']([^"\']+)["\']',  # Gradle
                r'compile\s+["\']([^"\']+)["\']'  # Gradle
            ]
            
            dependencies = []
            for pattern in dep_patterns:
                matches = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
                if matches and isinstance(matches[0], tuple):
                    # Handle grouped matches like Maven dependencies
                    dependencies.extend([f"{m[0]}:{m[1]}" if len(m) > 1 else m[0] for m in matches])
                else:
                    dependencies.extend(matches)
            
            # Filter out common false positives
            filtered_deps = []
            exclude_patterns = [r'^[A-Z_]+$', r'^\d+$', r'^[a-z]$', r'^[./]+$']
            
            for dep in dependencies:
                if dep and len(dep) > 2:
                    exclude = False
                    for exclude_pattern in exclude_patterns:
                        if re.match(exclude_pattern, dep):
                            exclude = True
                            break
                    if not exclude:
                        filtered_deps.append(dep)
            
            return list(set(filtered_deps)) if filtered_deps else None
        
        return None
    
    def _empty_structure(self, extraction_type: str) -> Dict:
        """Return appropriate empty structure"""
        structures = {
            "sql": {"queries": [], "tables": [], "connections": []},
            "server": {"hosts": [], "ports": [], "endpoints": [], "config": {}},
            "api": [],
            "dependencies": []
        }
        return structures.get(extraction_type, {})


class SpecExtractionService:
    """Main service for dynamic specification extraction using safechain pattern"""
    
    def __init__(self, max_retries=3, max_workers=4):
        self.extractor = SafeChainExtractor(max_retries=max_retries)
        self.max_workers = max_workers
    
    def extract_specification(self, codebase: str, max_results: int = 20) -> SpecificationData:
        """
        Main extraction method using safechain_llm_call pattern
        Always returns results regardless of individual extraction failures
        """
        
        spec_data = SpecificationData(codebase=codebase)
        
        try:
            # Get relevant documents using your existing vector search
            documents = self._get_codebase_documents(codebase, max_results)
            
            if not documents:
                logger.warning(f"No documents found for codebase: {codebase}")
                spec_data.summary = {
                    "status": "no_documents",
                    "message": f"No documents found for codebase '{codebase}'"
                }
                return spec_data
            
            logger.info(f"Processing {len(documents)} documents for codebase: {codebase}")
            
            # Parallel extraction with all strategies
            extraction_tasks = [
                ("sql", documents),
                ("server", documents),
                ("api", documents), 
                ("dependencies", documents)
            ]
            
            # Process all extractions in parallel using safechain
            results = self._parallel_extract_with_safechain(extraction_tasks)
            
            # Aggregate results
            spec_data = self._aggregate_results(spec_data, results)
            
            # Generate summary
            spec_data.summary = self._generate_summary(spec_data, len(documents))
            
            return spec_data
            
        except Exception as e:
            logger.error(f"Specification extraction failed for {codebase}: {e}")
            spec_data.summary = {
                "error": str(e), 
                "status": "failed",
                "codebase": codebase
            }
            return spec_data
    
    def _get_codebase_documents(self, codebase: str, max_results: int) -> List[Dict]:
        """Get relevant documents using your existing similarity_search_pgvector"""
        
        # Search strategies for comprehensive coverage
        search_queries = [
            ("database sql query table connection", "sql-related content"),
            ("server host port configuration endpoint", "server configuration"),
            ("api route controller service endpoint", "API endpoints"),
            ("import dependency library framework", "dependencies"),
            ("config properties environment variable", "configuration files")
        ]
        
        all_documents = []
        
        for query, description in search_queries:
            try:
                logger.debug(f"Searching for {description} in {codebase}")
                
                # Try internal codebase first
                docs = similarity_search_pgvector(
                    codebase=codebase,
                    query=query,
                    vector_results_count=max_results // len(search_queries)
                )
                all_documents.extend(docs)
                
                # Try external configuration files
                try:
                    external_docs = similarity_search_pgvector(
                        codebase=f"{codebase}-external-files",
                        query=query,
                        vector_results_count=max_results // len(search_queries)
                    )
                    all_documents.extend(external_docs)
                except Exception as e:
                    logger.debug(f"No external files found for {codebase}: {e}")
                
            except Exception as e:
                logger.warning(f"Vector search failed for query '{query}': {e}")
                continue
        
        # Remove duplicates based on content hash
        unique_docs = []
        seen_content = set()
        
        for doc in all_documents:
            content_hash = hash(doc['page_content'][:200])  # Use first 200 chars as fingerprint
            if content_hash not in seen_content and len(doc['page_content'].strip()) > 10:
                seen_content.add(content_hash)
                unique_docs.append(doc)
        
        logger.info(f"Found {len(unique_docs)} unique documents for {codebase}")
        return unique_docs[:max_results]
    
    def _parallel_extract_with_safechain(self, extraction_tasks: List[Tuple[str, List[Dict]]]) -> Dict[str, List[ExtractionResult]]:
        """Process all extractions in parallel using safechain pattern"""
        
        results = {task_type: [] for task_type, _ in extraction_tasks}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all extraction jobs
            future_to_task = {}
            
            for extraction_type, documents in extraction_tasks:
                for doc in documents:
                    future = executor.submit(
                        self.extractor.extract_with_safechain,
                        doc['page_content'],
                        extraction_type,
                        doc['metadata'].get('source', 'unknown')
                    )
                    future_to_task[future] = (extraction_type, doc['metadata'].get('source', 'unknown'))
            
            # Collect results as they complete
            completed_count = 0
            total_count = len(future_to_task)
            
            for future in as_completed(future_to_task):
                extraction_type, source = future_to_task[future]
                completed_count += 1
                
                try:
                    result = future.result(timeout=45)  # 45 second timeout per extraction
                    results[extraction_type].append(result)
                    logger.debug(f"Completed {extraction_type} extraction from {source} ({completed_count}/{total_count})")
                    
                except Exception as e:
                    logger.warning(f"Extraction failed for {extraction_type} from {source}: {e}")
                    # Add failed result to maintain consistency
                    results[extraction_type].append(ExtractionResult(
                        success=False,
                        data=self.extractor._empty_structure(extraction_type),
                        source=source,
                        extraction_type=extraction_type,
                        errors=[str(e)]
                    ))
        
        return results
    
    def _aggregate_results(self, spec_data: SpecificationData, results: Dict[str, List[ExtractionResult]]) -> SpecificationData:
        """Aggregate parallel extraction results"""
        
        # Aggregate SQL results
        all_queries, all_tables, all_connections = [], [], []
        for result in results.get("sql", []):
            if result.success and result.data:
                data = result.data
                all_queries.extend(data.get("queries", []))
                all_tables.extend(data.get("tables", []))
                all_connections.extend(data.get("connections", []))
        
        spec_data.database_info = {
            "queries": list(dict.fromkeys(all_queries)),  # Remove duplicates preserving order
            "tables": list(dict.fromkeys(all_tables)),
            "connections": list(dict.fromkeys(all_connections))
        }
        
        # Aggregate server results
        all_hosts, all_ports, all_endpoints = [], [], []
        all_config = {}
        for result in results.get("server", []):
            if result.success and result.data:
                data = result.data
                all_hosts.extend(data.get("hosts", []))
                all_ports.extend(data.get("ports", []))
                all_endpoints.extend(data.get("endpoints", []))
                all_config.update(data.get("config", {}))
        
        if all_hosts or all_ports or all_endpoints or all_config:
            spec_data.server_info = [{
                "hosts": list(dict.fromkeys(all_hosts)),
                "ports": list(dict.fromkeys(all_ports)),
                "endpoints": list(dict.fromkeys(all_endpoints)),
                "configuration": all_config
            }]
        
        # Aggregate API results
        all_apis = []
        for result in results.get("api", []):
            if result.success and result.data:
                if isinstance(result.data, list):
                    all_apis.extend(result.data)
        
        spec_data.api_endpoints = list(dict.fromkeys(all_apis))
        
        # Aggregate dependencies
        all_deps = []
        for result in results.get("dependencies", []):
            if result.success and result.data:
                if isinstance(result.data, list):
                    all_deps.extend(result.data)
        
        spec_data.dependencies = list(dict.fromkeys(all_deps))
        
        return spec_data
    
    def _generate_summary(self, spec_data: SpecificationData, doc_count: int) -> Dict:
        """Generate extraction summary"""
        
        return {
            "codebase": spec_data.codebase,
            "extraction_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "documents_processed": doc_count,
            "statistics": {
                "database_queries": len(spec_data.database_info.get("queries", [])),
                "database_tables": len(spec_data.database_info.get("tables", [])),
                "database_connections": len(spec_data.database_info.get("connections", [])),
                "server_configurations": len(spec_data.server_info),
                "api_endpoints": len(spec_data.api_endpoints),
                "dependencies": len(spec_data.dependencies)
            },
            "status": "completed",
            "coverage": self._calculate_coverage(spec_data)
        }
    
    def _calculate_coverage(self, spec_data: SpecificationData) -> Dict:
        """Calculate extraction coverage metrics"""
        
        areas = [
            ("database", bool(spec_data.database_info.get("queries") or spec_data.database_info.get("tables"))),
            ("server", bool(spec_data.server_info)),
            ("api", bool(spec_data.api_endpoints)),
            ("dependencies", bool(spec_data.dependencies)),
            ("configuration", bool(spec_data.configuration))
        ]
        
        found_areas = sum(1 for _, found in areas if found)
        total_areas = len(areas)
        
        return {
            "percentage": (found_areas / total_areas) * 100,
            "areas_found": found_areas,
            "total_areas": total_areas,
            "areas": {area: found for area, found in areas}
        }