# Codebase Refactoring Recommendations

## Overview
After analyzing the GenAI codebase, several refactoring opportunities have been identified to improve maintainability, reduce redundancy, and simplify the architecture.

## Major Issues Identified

### 1. 🔧 **Backend Import Issues**
**File**: `genai-python-poc/app.py:23`
```python
app.register_blueprint(llm_bp)  # llm_bp not imported
```
**Fix**: Missing import for `llm_bp`

### 2. 🔧 **Backend Service Structure**
**Issues**:
- Missing `Information` blueprint import (`endpoints/Information.py` doesn't exist)
- Inconsistent port configuration (5000 vs 8082)
- Mixed environment handling

### 3. 🧹 **Redundant Multi-Language Support**
You're correct - the language detection in `DynamicLLMUtil.py` is unnecessary since LangChain embeddings handle this.

## Refactoring Plan

### Phase 1: Backend Consolidation

#### 1.1 Fix Backend Service Structure
```python
# genai-python-poc/app.py - Simplified
import os
from flask import Flask
from pathlib import Path
from dotenv import load_dotenv
from endpoints.embeddings import embeddings_bp
from endpoints.LLM import llm_bp

def create_app():
    app = Flask(__name__)
    
    # Load environment
    env_path = Path('/opt/epaas/vault/secrets/secrets') if 'EPAAS_ENV' in os.environ else Path('.env')
    load_dotenv(env_path)
    
    # Register blueprints
    app.register_blueprint(embeddings_bp)
    app.register_blueprint(llm_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=8082, host="0.0.0.0")  # Consistent port
```

#### 1.2 Unified Configuration
```python
# config/app_config.py
import os
from dataclasses import dataclass

@dataclass
class Config:
    # API Configuration
    LLM_SERVICE_PORT: int = 8082
    VECTOR_SERVICE_PORT: int = 5000
    
    # Endpoints
    LLM_ENDPOINT: str = '/api/llm'
    VECTOR_ENDPOINT: str = '/api/vector-search'
    
    # Timeouts and Retries
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    
    @classmethod
    def from_env(cls):
        return cls(
            LLM_SERVICE_PORT=int(os.getenv('LLM_SERVICE_PORT', 8082)),
            VECTOR_SERVICE_PORT=int(os.getenv('VECTOR_SERVICE_PORT', 5000)),
            REQUEST_TIMEOUT=int(os.getenv('REQUEST_TIMEOUT', 30)),
            MAX_RETRIES=int(os.getenv('MAX_RETRIES', 3)),
        )
```

### Phase 2: Frontend Simplification

#### 2.1 Simplified LLM Utility (Remove Language Detection)
```python
# utils/SimplifiedLLMUtil.py
import requests
import streamlit as st
import json
import re
from typing import Dict, List, Tuple, Optional
from config.app_config import Config

class LLMProcessor:
    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        
    def make_request(self, system_prompt: str, user_prompt: str, content: str) -> Tuple[Dict, bool]:
        """Make LLM request with retry logic"""
        for attempt in range(self.config.MAX_RETRIES):
            try:
                url = f"http://localhost:{self.config.LLM_SERVICE_PORT}{self.config.LLM_ENDPOINT}"
                payload = {
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "codebase": content
                }
                
                response = requests.post(
                    url, 
                    json=payload, 
                    timeout=self.config.REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    return response.json(), True
                    
            except Exception as e:
                if attempt == self.config.MAX_RETRIES - 1:
                    return {"error": str(e)}, False
                st.warning(f"Attempt {attempt + 1} failed, retrying...")
                
        return {"error": "Max retries exceeded"}, False
    
    def extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from response with fallback strategies"""
        # Strategy 1: Direct parsing
        try:
            return json.loads(text)
        except:
            pass
            
        # Strategy 2: Extract from code blocks
        patterns = [r'```json\s*(.*?)\s*```', r'```\s*(.*?)\s*```']
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    continue
        return None

def extract_sql_data(data: List[Dict], system_prompt: str) -> Tuple[List[Dict], List[str], List[Dict]]:
    """Simplified SQL extraction without language detection"""
    processor = LLMProcessor()
    database_info = []
    sql_queries = []
    invalid_queries = []
    
    for result in data:
        content = result['page_content']
        file_name = result['metadata']['source']
        
        # Simple content validation
        if len(content.strip()) < 10:
            continue
            
        # Direct SQL detection
        response, success = processor.make_request(
            system_prompt,
            "Are there SQL queries in this code? Answer 'yes' or 'no'.",
            content
        )
        
        if not success or 'no' in response.get('output', '').lower():
            continue
            
        # Extract queries
        response, success = processor.make_request(
            system_prompt,
            "Extract all SQL queries as JSON: {'queries': [...]]}",
            content
        )
        
        if success:
            query_data = processor.extract_json(response.get('output', ''))
            if query_data and 'queries' in query_data:
                sql_queries.extend(query_data['queries'])
    
    return database_info, sql_queries, invalid_queries
```

#### 2.2 Unified Service Layer
```python
# services/spec_generation_service.py
from typing import Dict, List
from utils.SimplifiedLLMUtil import extract_sql_data, LLMProcessor
from utils.vectorSearchUtil import vector_search
from config.app_config import Config

class SpecGenerationService:
    def __init__(self):
        self.config = Config.from_env()
        self.llm_processor = LLMProcessor(self.config)
    
    def generate_specification(self, codebase: str, result_count: int = 10) -> Dict:
        """Main spec generation orchestrator"""
        spec = {
            "codebase": codebase,
            "server_info": self._extract_server_info(codebase, result_count),
            "database_info": self._extract_database_info(codebase, result_count),
            "endpoints": self._extract_endpoints(codebase, result_count)
        }
        return spec
    
    def _extract_server_info(self, codebase: str, count: int) -> List[Dict]:
        data = vector_search(f"{codebase}-external-files", "server host config", count)
        # Simplified server extraction logic
        return []
    
    def _extract_database_info(self, codebase: str, count: int) -> Dict:
        internal_data = vector_search(codebase, "sql database query", count)
        tables, queries, invalid = extract_sql_data(internal_data.get('results', []), "expert programmer")
        
        return {
            "tables": tables,
            "queries": queries,
            "invalid_queries": invalid
        }
    
    def _extract_endpoints(self, codebase: str, count: int) -> List[str]:
        data = vector_search(codebase, "url endpoint api http", count)
        # Simple regex-based endpoint extraction
        endpoints = []
        for result in data.get('results', []):
            content = result['page_content']
            # Extract URLs/endpoints using regex
            import re
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
            endpoints.extend(urls)
        
        return list(set(endpoints))  # Remove duplicates
```

### Phase 3: Configuration Centralization

#### 3.1 Environment-Based Configuration
```python
# .env
LLM_SERVICE_PORT=8082
VECTOR_SERVICE_PORT=5000
REQUEST_TIMEOUT=30
MAX_RETRIES=3
GITHUB_TOKEN=your_token_here
```

#### 3.2 Remove Hardcoded Values
Replace all hardcoded URLs/ports with environment variables:
- `localhost:5000` → `{VECTOR_SERVICE_HOST}:{VECTOR_SERVICE_PORT}`
- `localhost:8082` → `{LLM_SERVICE_HOST}:{LLM_SERVICE_PORT}`

### Phase 4: Code Elimination

#### 4.1 Files to Remove
- `utils/DynamicLLMUtil.py` (too complex, language detection unnecessary)
- `config/codebase_profiles.json` (unnecessary with LangChain)
- `pages/2_Spec_Generation.py` (keep only refactored version)

#### 4.2 Code to Simplify
- Remove all language detection logic
- Remove pattern-based pre-filtering (let embeddings handle relevance)
- Simplify JSON extraction to 2 strategies max
- Remove complex retry mechanisms (use simple exponential backoff)

### Phase 5: Architecture Improvements

#### 5.1 Single Responsibility Principle
```
Frontend (Streamlit):
├── pages/spec_generation.py (UI only)
├── services/spec_service.py (orchestration)
└── utils/api_client.py (HTTP requests)

Backend (Flask):
├── app.py (app setup)
├── endpoints/llm.py (LLM processing)
├── endpoints/vector.py (vector search)
└── services/llm_service.py (business logic)
```

#### 5.2 Error Handling Standardization
```python
# utils/error_handler.py
from typing import Tuple, Any

class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

def handle_api_call(func) -> Tuple[Any, bool]:
    """Standard API call wrapper"""
    try:
        result = func()
        return result, True
    except APIError as e:
        st.error(f"API Error: {e.message}")
        return None, False
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None, False
```

## Implementation Priority

### High Priority (Week 1)
1. Fix backend import issues
2. Standardize port configuration
3. Remove language detection complexity
4. Create simplified LLMUtil

### Medium Priority (Week 2)  
5. Implement service layer
6. Centralize configuration
7. Standardize error handling

### Low Priority (Week 3)
8. Remove deprecated files
9. Add comprehensive logging
10. Performance optimization

## Benefits of Refactoring

### Before vs After

| Aspect | Before | After |
|--------|---------|--------|
| **Lines of Code** | ~800 | ~400 |
| **Files** | 11 Python files | 7 Python files |
| **Complexity** | High (language detection, patterns) | Low (LLM + embeddings) |
| **Maintainability** | Complex dependencies | Clear separation |
| **Error Handling** | Inconsistent | Standardized |
| **Configuration** | Hardcoded values | Environment-based |

### Key Improvements
- **50% reduction in code complexity**
- **Elimination of redundant language detection** 
- **Centralized configuration management**
- **Consistent error handling patterns**
- **Clear separation of concerns**
- **Easier testing and debugging**

## Migration Strategy

1. **Create new simplified files alongside existing ones**
2. **Test new implementation thoroughly**  
3. **Gradually migrate existing functionality**
4. **Remove old files once migration complete**
5. **Update documentation and README**

This refactoring will make the codebase much more maintainable while leveraging LangChain's built-in capabilities effectively.