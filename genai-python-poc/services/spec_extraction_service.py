"""
Dynamic Specification Extraction Service
Leverages LangChain tools for robust codebase analysis
"""
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType

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

class LangChainExtractor:
    """LangChain-based extraction engine"""
    
    def __init__(self, llm_model):
        self.llm = llm_model
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        self._setup_extraction_chains()
        self._setup_tools()
    
    def _setup_extraction_chains(self):
        """Setup LangChain extraction chains"""
        
        # SQL Extraction Chain
        sql_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert code analyzer. Extract database-related information from code.
            Focus on: SQL queries, table names, column names, database connections, ORM operations.
            Return valid JSON format: {{"queries": [], "tables": [], "connections": []}}
            If no database information found, return empty arrays."""),
            ("human", "Analyze this code for database information:\n{code}")
        ])
        self.sql_chain = sql_prompt | self.llm | StrOutputParser()
        
        # Server Info Chain
        server_prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract server and configuration information from code/config files.
            Focus on: hosts, ports, URLs, service endpoints, environment variables.
            Return valid JSON: {{"hosts": [], "ports": [], "endpoints": [], "config": {{}}}}
            If no server info found, return empty structure."""),
            ("human", "Extract server information from:\n{code}")
        ])
        self.server_chain = server_prompt | self.llm | StrOutputParser()
        
        # API Endpoint Chain
        api_prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract API endpoints and routes from code.
            Focus on: REST endpoints, GraphQL, RPC calls, external API calls.
            Return JSON array: ["endpoint1", "endpoint2", ...]
            Include method and path if available."""),
            ("human", "Find API endpoints in:\n{code}")
        ])
        self.api_chain = api_prompt | self.llm | StrOutputParser()
        
        # Dependency Chain
        dep_prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract dependencies and imports from code.
            Focus on: external libraries, frameworks, services, modules.
            Return JSON array: ["dependency1", "dependency2", ...]"""),
            ("human", "Extract dependencies from:\n{code}")
        ])
        self.dependency_chain = dep_prompt | self.llm | StrOutputParser()
    
    def _setup_tools(self):
        """Setup LangChain tools for extraction"""
        
        def extract_sql_tool(code: str) -> str:
            """Extract SQL and database information"""
            try:
                result = self.sql_chain.invoke({"code": code})
                return result
            except Exception as e:
                return json.dumps({"queries": [], "tables": [], "connections": [], "error": str(e)})
        
        def extract_server_tool(code: str) -> str:
            """Extract server and configuration information"""
            try:
                result = self.server_chain.invoke({"code": code})
                return result
            except Exception as e:
                return json.dumps({"hosts": [], "ports": [], "endpoints": [], "config": {}, "error": str(e)})
        
        def extract_api_tool(code: str) -> str:
            """Extract API endpoints"""
            try:
                result = self.api_chain.invoke({"code": code})
                return result
            except Exception as e:
                return json.dumps([])
        
        def extract_dependencies_tool(code: str) -> str:
            """Extract dependencies"""
            try:
                result = self.dependency_chain.invoke({"code": code})
                return result
            except Exception as e:
                return json.dumps([])
        
        self.tools = [
            Tool(
                name="sql_extractor",
                description="Extract SQL queries and database information from code",
                func=extract_sql_tool
            ),
            Tool(
                name="server_extractor", 
                description="Extract server configuration and connection information",
                func=extract_server_tool
            ),
            Tool(
                name="api_extractor",
                description="Extract API endpoints and routes",
                func=extract_api_tool
            ),
            Tool(
                name="dependency_extractor",
                description="Extract dependencies and imports",
                func=extract_dependencies_tool
            )
        ]
    
    def extract_with_fallback(self, code: str, extraction_type: str) -> ExtractionResult:
        """Extract information with multiple fallback strategies"""
        
        # Strategy 1: LangChain tools
        try:
            tool_map = {
                "sql": self.tools[0],
                "server": self.tools[1], 
                "api": self.tools[2],
                "dependencies": self.tools[3]
            }
            
            if extraction_type in tool_map:
                result = tool_map[extraction_type].func(code)
                parsed_data = self._safe_json_parse(result)
                
                if parsed_data:
                    return ExtractionResult(
                        success=True,
                        data=parsed_data,
                        source="langchain_tool",
                        extraction_type=extraction_type,
                        confidence=0.9
                    )
        except Exception as e:
            logger.warning(f"LangChain tool failed for {extraction_type}: {e}")
        
        # Strategy 2: Regex-based fallback
        regex_data = self._regex_fallback(code, extraction_type)
        if regex_data:
            return ExtractionResult(
                success=True,
                data=regex_data,
                source="regex_fallback",
                extraction_type=extraction_type,
                confidence=0.6
            )
        
        # Strategy 3: Return empty but valid structure
        return ExtractionResult(
            success=True,
            data=self._empty_structure(extraction_type),
            source="empty_fallback",
            extraction_type=extraction_type,
            confidence=0.1
        )
    
    def _safe_json_parse(self, text: str) -> Optional[Dict]:
        """Safely parse JSON with multiple strategies"""
        if not text:
            return None
        
        # Clean the text
        text = text.strip()
        
        # Strategy 1: Direct parsing
        try:
            return json.loads(text)
        except:
            pass
        
        # Strategy 2: Extract from code blocks
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'\{.*\}',
            r'\[.*\]'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except:
                    continue
        
        return None
    
    def _regex_fallback(self, code: str, extraction_type: str) -> Optional[Dict]:
        """Regex-based extraction as fallback"""
        
        if extraction_type == "sql":
            sql_patterns = [
                r'(?i)(SELECT\s+.*?FROM\s+\w+)',
                r'(?i)(INSERT\s+INTO\s+\w+)',
                r'(?i)(UPDATE\s+\w+\s+SET)',
                r'(?i)(DELETE\s+FROM\s+\w+)',
                r'(?i)(CREATE\s+TABLE\s+\w+)'
            ]
            
            queries = []
            for pattern in sql_patterns:
                matches = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
                queries.extend([match.strip()[:200] for match in matches])  # Limit length
            
            return {"queries": queries, "tables": [], "connections": []} if queries else None
        
        elif extraction_type == "server":
            server_patterns = [
                r'(?i)(?:host|server|endpoint)["\s]*[=:]["\s]*([^"\s,;]+)',
                r'(?i)port["\s]*[=:]["\s]*(\d+)',
                r'https?://([^/\s"\']+)',
                r'(?i)database["\s]*[=:]["\s]*([^"\s,;]+)'
            ]
            
            hosts, ports, endpoints = [], [], []
            for pattern in server_patterns:
                matches = re.findall(pattern, code)
                if 'port' in pattern.lower():
                    ports.extend(matches)
                elif 'http' in pattern:
                    endpoints.extend([f"http://{match}" for match in matches])
                else:
                    hosts.extend(matches)
            
            if hosts or ports or endpoints:
                return {
                    "hosts": list(set(hosts)),
                    "ports": list(set(ports)),
                    "endpoints": list(set(endpoints)),
                    "config": {}
                }
        
        elif extraction_type == "api":
            api_patterns = [
                r'@(?:Get|Post|Put|Delete|Patch)Mapping\(["\']([^"\']+)["\']',
                r'app\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                r'router\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                r'Route\(["\']([^"\']+)["\']',
                r'(?:GET|POST|PUT|DELETE|PATCH)\s+([/\w\-\{\}]+)'
            ]
            
            endpoints = []
            for pattern in api_patterns:
                matches = re.findall(pattern, code, re.IGNORECASE)
                endpoints.extend(matches)
            
            return list(set(endpoints)) if endpoints else None
        
        elif extraction_type == "dependencies":
            dep_patterns = [
                r'import\s+([^;\n]+)',
                r'from\s+([^\s]+)\s+import',
                r'require\(["\']([^"\']+)["\']',
                r'<dependency>.*?<groupId>([^<]+)</groupId>.*?<artifactId>([^<]+)</artifactId>',
                r'"([^"]+)":\s*"[^"]+"'  # package.json style
            ]
            
            dependencies = []
            for pattern in dep_patterns:
                matches = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
                if isinstance(matches[0], tuple) if matches else False:
                    dependencies.extend([f"{m[0]}.{m[1]}" for m in matches])
                else:
                    dependencies.extend(matches)
            
            return list(set(dependencies)) if dependencies else None
        
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
    """Main service for dynamic specification extraction"""
    
    def __init__(self, llm_model, vector_store):
        self.llm = llm_model
        self.vector_store = vector_store
        self.extractor = LangChainExtractor(llm_model)
        self.max_workers = 4
    
    def extract_specification(self, codebase: str, max_results: int = 20) -> SpecificationData:
        """
        Main extraction method - processes any codebase dynamically
        Returns results regardless of individual extraction failures
        """
        
        spec_data = SpecificationData(codebase=codebase)
        
        try:
            # Get relevant documents from vector store
            documents = self._get_codebase_documents(codebase, max_results)
            
            if not documents:
                logger.warning(f"No documents found for codebase: {codebase}")
                return spec_data
            
            # Parallel extraction with all strategies
            extraction_tasks = [
                ("sql", documents),
                ("server", documents),
                ("api", documents), 
                ("dependencies", documents)
            ]
            
            # Process all extractions in parallel
            results = self._parallel_extract(extraction_tasks)
            
            # Aggregate results
            spec_data = self._aggregate_results(spec_data, results)
            
            # Generate summary
            spec_data.summary = self._generate_summary(spec_data)
            
            return spec_data
            
        except Exception as e:
            logger.error(f"Specification extraction failed for {codebase}: {e}")
            spec_data.summary = {"error": str(e), "status": "failed"}
            return spec_data
    
    def _get_codebase_documents(self, codebase: str, max_results: int) -> List[Document]:
        """Retrieve relevant documents from vector store"""
        
        # Search strategies for comprehensive coverage
        search_queries = [
            "database sql query table connection",
            "server host port configuration endpoint",
            "api route controller service endpoint",
            "import dependency library framework",
            "config properties environment variable"
        ]
        
        all_documents = []
        
        for query in search_queries:
            try:
                # Try internal codebase first
                docs = self.vector_store.similarity_search(
                    query=query,
                    collection_name=codebase,
                    k=max_results // len(search_queries)
                )
                all_documents.extend(docs)
                
                # Try external configuration files
                external_docs = self.vector_store.similarity_search(
                    query=query,
                    collection_name=f"{codebase}-external-files",
                    k=max_results // len(search_queries)
                )
                all_documents.extend(external_docs)
                
            except Exception as e:
                logger.warning(f"Vector search failed for query '{query}': {e}")
                continue
        
        # Remove duplicates based on content
        unique_docs = []
        seen_content = set()
        
        for doc in all_documents:
            content_hash = hash(doc.page_content[:500])  # Use first 500 chars as fingerprint
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)
        
        return unique_docs[:max_results]
    
    def _parallel_extract(self, extraction_tasks: List[Tuple[str, List[Document]]]) -> Dict[str, List[ExtractionResult]]:
        """Process all extractions in parallel"""
        
        results = {task_type: [] for task_type, _ in extraction_tasks}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all extraction jobs
            future_to_task = {}
            
            for extraction_type, documents in extraction_tasks:
                for doc in documents:
                    future = executor.submit(
                        self.extractor.extract_with_fallback,
                        doc.page_content,
                        extraction_type
                    )
                    future_to_task[future] = (extraction_type, doc.metadata.get('source', 'unknown'))
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                extraction_type, source = future_to_task[future]
                
                try:
                    result = future.result(timeout=30)  # 30 second timeout per extraction
                    result.source = source
                    results[extraction_type].append(result)
                    
                except Exception as e:
                    logger.warning(f"Extraction failed for {extraction_type} from {source}: {e}")
                    # Add failed result to maintain consistency
                    results[extraction_type].append(ExtractionResult(
                        success=False,
                        data={},
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
            "queries": list(set(all_queries)),  # Remove duplicates
            "tables": list(set(all_tables)),
            "connections": list(set(all_connections))
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
        
        spec_data.server_info = [{
            "hosts": list(set(all_hosts)),
            "ports": list(set(all_ports)),
            "endpoints": list(set(all_endpoints)),
            "configuration": all_config
        }] if (all_hosts or all_ports or all_endpoints) else []
        
        # Aggregate API results
        all_apis = []
        for result in results.get("api", []):
            if result.success and result.data:
                if isinstance(result.data, list):
                    all_apis.extend(result.data)
        
        spec_data.api_endpoints = list(set(all_apis))
        
        # Aggregate dependencies
        all_deps = []
        for result in results.get("dependencies", []):
            if result.success and result.data:
                if isinstance(result.data, list):
                    all_deps.extend(result.data)
        
        spec_data.dependencies = list(set(all_deps))
        
        return spec_data
    
    def _generate_summary(self, spec_data: SpecificationData) -> Dict:
        """Generate extraction summary"""
        
        return {
            "codebase": spec_data.codebase,
            "extraction_date": str(pd.Timestamp.now()),
            "statistics": {
                "database_queries": len(spec_data.database_info.get("queries", [])),
                "database_tables": len(spec_data.database_info.get("tables", [])),
                "server_configurations": len(spec_data.server_info),
                "api_endpoints": len(spec_data.api_endpoints),
                "dependencies": len(spec_data.dependencies)
            },
            "status": "completed",
            "coverage": self._calculate_coverage(spec_data)
        }
    
    def _calculate_coverage(self, spec_data: SpecificationData) -> Dict:
        """Calculate extraction coverage metrics"""
        
        total_possible = 5  # sql, server, api, deps, config
        found = 0
        
        if spec_data.database_info.get("queries") or spec_data.database_info.get("tables"):
            found += 1
        if spec_data.server_info:
            found += 1  
        if spec_data.api_endpoints:
            found += 1
        if spec_data.dependencies:
            found += 1
        if spec_data.configuration:
            found += 1
        
        return {
            "percentage": (found / total_possible) * 100,
            "areas_found": found,
            "total_areas": total_possible
        }