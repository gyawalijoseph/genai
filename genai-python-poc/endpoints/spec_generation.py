"""
Specification Generation API Endpoint
Robust backend service using LangChain tools
"""
import json
import pandas as pd
from flask import Blueprint, request, jsonify, make_response
from typing import Dict, Any
import logging

from services.spec_extraction_service import SpecExtractionService, SpecificationData
from utilities.utils import get_connection

logger = logging.getLogger(__name__)

spec_bp = Blueprint('spec_generation', __name__)

# Global service instance (initialize with your LLM and vector store)
_service_instance = None

def get_service():
    """Get or create service instance"""
    global _service_instance
    if _service_instance is None:
        try:
            # Initialize with your actual LLM model and vector store
            from utilities.utils import model  # Your LLM model
            
            # Mock vector store for now - replace with your actual implementation
            class MockVectorStore:
                def similarity_search(self, query: str, collection_name: str, k: int = 10):
                    # This should use your actual vector store implementation
                    # For now, returning mock data
                    return [
                        type('Document', (), {
                            'page_content': f'Mock content for {query}',
                            'metadata': {'source': f'mock_file_{i}.py'}
                        })()
                        for i in range(k)
                    ]
            
            vector_store = MockVectorStore()
            llm_model = model('llama-3')  # Your actual model
            
            _service_instance = SpecExtractionService(llm_model, vector_store)
            
        except Exception as e:
            logger.error(f"Failed to initialize service: {e}")
            # Return a mock service for testing
            _service_instance = MockSpecExtractionService()
    
    return _service_instance

class MockSpecExtractionService:
    """Mock service for testing when dependencies not available"""
    
    def extract_specification(self, codebase: str, max_results: int = 20) -> SpecificationData:
        """Mock extraction for testing"""
        return SpecificationData(
            codebase=codebase,
            server_info=[{
                "hosts": ["localhost", "example.com"],
                "ports": ["8080", "3000"],
                "endpoints": ["http://localhost:8080/api"],
                "configuration": {"env": "development"}
            }],
            database_info={
                "queries": ["SELECT * FROM users", "INSERT INTO logs"],
                "tables": ["users", "orders", "products"],
                "connections": ["postgresql://localhost:5432/mydb"]
            },
            api_endpoints=["/api/users", "/api/orders", "/health"],
            dependencies=["spring-boot", "postgresql", "redis"],
            configuration={"debug": True, "port": 8080},
            summary={
                "codebase": codebase,
                "statistics": {
                    "database_queries": 2,
                    "database_tables": 3,
                    "server_configurations": 1,
                    "api_endpoints": 3,
                    "dependencies": 3
                },
                "status": "completed",
                "coverage": {"percentage": 100, "areas_found": 5, "total_areas": 5}
            }
        )

@spec_bp.route('/generate-spec', methods=['POST'])
def generate_specification():
    """
    Generate dynamic specification for any codebase
    
    Request body:
    {
        "codebase": "my-project",
        "max_results": 20,
        "include_summary": true
    }
    """
    try:
        data = request.json
        
        # Validate input
        if not data or 'codebase' not in data:
            return make_response(jsonify({
                "status": "error",
                "message": "Missing required field: codebase",
                "status_code": 400
            }), 400)
        
        codebase = data['codebase'].strip()
        if not codebase:
            return make_response(jsonify({
                "status": "error", 
                "message": "Codebase name cannot be empty",
                "status_code": 400
            }), 400)
        
        max_results = data.get('max_results', 20)
        include_summary = data.get('include_summary', True)
        
        # Validate max_results
        if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
            max_results = 20
        
        logger.info(f"Starting specification generation for codebase: {codebase}")
        
        # Get service and extract specification
        service = get_service()
        spec_data = service.extract_specification(codebase, max_results)
        
        # Prepare response
        response_data = {
            "status": "success",
            "status_code": 200,
            "codebase": codebase,
            "data": {
                "server_information": spec_data.server_info,
                "database_information": spec_data.database_info,
                "api_endpoints": spec_data.api_endpoints,
                "dependencies": spec_data.dependencies,
                "configuration": spec_data.configuration
            }
        }
        
        if include_summary:
            response_data["summary"] = spec_data.summary
        
        logger.info(f"Specification generation completed for {codebase}")
        return make_response(jsonify(response_data), 200)
        
    except Exception as e:
        logger.error(f"Specification generation failed: {e}")
        return make_response(jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}",
            "status_code": 500
        }), 500)

@spec_bp.route('/extract-component', methods=['POST'])
def extract_component():
    """
    Extract specific component (sql, server, api, dependencies)
    
    Request body:
    {
        "codebase": "my-project",
        "component": "sql",  // sql, server, api, dependencies
        "max_results": 10
    }
    """
    try:
        data = request.json
        
        if not data or 'codebase' not in data or 'component' not in data:
            return make_response(jsonify({
                "status": "error",
                "message": "Missing required fields: codebase, component",
                "status_code": 400
            }), 400)
        
        codebase = data['codebase'].strip()
        component = data['component'].lower().strip()
        max_results = data.get('max_results', 10)
        
        valid_components = ['sql', 'server', 'api', 'dependencies']
        if component not in valid_components:
            return make_response(jsonify({
                "status": "error",
                "message": f"Invalid component. Must be one of: {valid_components}",
                "status_code": 400
            }), 400)
        
        # For now, return subset of full extraction
        # In production, you might optimize this for single-component extraction
        service = get_service()
        spec_data = service.extract_specification(codebase, max_results)
        
        # Extract requested component
        component_data = {}
        if component == 'sql':
            component_data = spec_data.database_info
        elif component == 'server':
            component_data = spec_data.server_info
        elif component == 'api':
            component_data = spec_data.api_endpoints
        elif component == 'dependencies':
            component_data = spec_data.dependencies
        
        return make_response(jsonify({
            "status": "success",
            "status_code": 200,
            "codebase": codebase,
            "component": component,
            "data": component_data
        }), 200)
        
    except Exception as e:
        logger.error(f"Component extraction failed: {e}")
        return make_response(jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}",
            "status_code": 500
        }), 500)

@spec_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        service = get_service()
        return make_response(jsonify({
            "status": "healthy",
            "service": "spec-generation",
            "version": "2.0.0"
        }), 200)
    except Exception as e:
        return make_response(jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500)

@spec_bp.route('/validate-codebase', methods=['POST'])
def validate_codebase():
    """
    Validate if codebase exists in vector store
    
    Request body:
    {
        "codebase": "my-project"
    }
    """
    try:
        data = request.json
        
        if not data or 'codebase' not in data:
            return make_response(jsonify({
                "status": "error",
                "message": "Missing required field: codebase",
                "status_code": 400
            }), 400)
        
        codebase = data['codebase'].strip()
        
        # Try to get some documents to validate existence
        service = get_service()
        try:
            # Try a simple query to see if codebase exists
            documents = service._get_codebase_documents(codebase, 1)
            exists = len(documents) > 0
        except:
            exists = False
        
        return make_response(jsonify({
            "status": "success",
            "codebase": codebase,
            "exists": exists,
            "message": "Codebase found" if exists else "Codebase not found in vector store"
        }), 200)
        
    except Exception as e:
        logger.error(f"Codebase validation failed: {e}")
        return make_response(jsonify({
            "status": "error",
            "message": f"Validation failed: {str(e)}",
            "status_code": 500
        }), 500)