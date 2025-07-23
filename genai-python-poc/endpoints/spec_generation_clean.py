"""
Specification Generation API Endpoint - Clean Version
Clear flow for server component extraction using safechain_llm_call pattern
"""
import json
import time
from flask import Blueprint, request, jsonify, make_response
from typing import Dict, Any
import logging

from services.spec_extraction_service_updated import SpecExtractionService, SpecificationData

logger = logging.getLogger(__name__)

spec_bp = Blueprint('spec_generation', __name__)

# Global service instance
_service_instance = None

def get_service():
    """Get or create service instance - no mocks, real implementation only"""
    global _service_instance
    if _service_instance is None:
        _service_instance = SpecExtractionService(
            max_retries=3,  # Use same retry count as safechain_llm_call
            max_workers=4   # Parallel processing workers
        )
        logger.info("SpecExtractionService initialized with safechain pattern")
    
    return _service_instance

@spec_bp.route('/generate-spec', methods=['POST'])
def generate_specification():
    """
    Generate dynamic specification using safechain_llm_call pattern
    
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
        
        logger.info(f"Starting server extraction for codebase: {codebase}")
        start_time = time.time()
        
        # Get service and extract specification using safechain pattern
        service = get_service()
        spec_data = service.extract_specification(codebase, max_results)
        
        extraction_time = time.time() - start_time
        
        # Prepare response
        response_data = {
            "status": "success",
            "status_code": 200,
            "codebase": codebase,
            "extraction_time_seconds": round(extraction_time, 2),
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
        
        logger.info(f"Server extraction completed for {codebase} in {extraction_time:.2f}s")
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
    Extract specific component (server, sql, api, dependencies)
    
    For server component extraction:
    1. Pulls embeddings related to "server host port configuration endpoint"
    2. Uses safechain_llm_call to extract host, port, database name
    3. Returns structured server information
    
    Request body:
    {
        "codebase": "my-project",
        "component": "server",
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
        
        logger.info(f"Starting {component} component extraction for: {codebase}")
        start_time = time.time()
        
        # Get full specification (in production, you could optimize for single-component)
        service = get_service()
        spec_data = service.extract_specification(codebase, max_results)
        
        extraction_time = time.time() - start_time
        
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
        
        response_data = {
            "status": "success",
            "status_code": 200,
            "codebase": codebase,
            "component": component,
            "extraction_time_seconds": round(extraction_time, 2),
            "data": component_data
        }
        
        # Add component-specific statistics
        if component == 'server' and component_data:
            server_info = component_data[0] if component_data else {}
            response_data["statistics"] = {
                "hosts_found": len(server_info.get("hosts", [])),
                "ports_found": len(server_info.get("ports", [])),
                "endpoints_found": len(server_info.get("endpoints", []))
            }
        
        logger.info(f"{component} extraction completed for {codebase} in {extraction_time:.2f}s")
        return make_response(jsonify(response_data), 200)
        
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
            "service": "safechain-spec-generation",
            "version": "2.1.0",
            "features": [
                "safechain_llm_call integration",
                "parallel processing",
                "regex fallbacks",
                "universal codebase support"
            ]
        }), 200)
    except Exception as e:
        return make_response(jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500)

@spec_bp.route('/validate-codebase', methods=['POST'])
def validate_codebase():
    """
    Validate if codebase exists using your existing vector search
    
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
        
        # Use your existing similarity_search_pgvector to validate
        try:
            from utilities.utils import similarity_search_pgvector
            
            # Try a simple search to see if codebase exists
            test_docs = similarity_search_pgvector(
                codebase=codebase,
                query="test query",
                vector_results_count=1
            )
            exists = len(test_docs) > 0
            
            logger.info(f"Codebase validation for '{codebase}': {'exists' if exists else 'not found'}")
            
        except Exception as e:
            logger.warning(f"Codebase validation failed for '{codebase}': {e}")
            exists = False
        
        return make_response(jsonify({
            "status": "success",
            "codebase": codebase,
            "exists": exists,
            "message": "Codebase found in vector store" if exists else "Codebase not found in vector store",
            "suggestion": "Generate embeddings for this codebase first" if not exists else None
        }), 200)
        
    except Exception as e:
        logger.error(f"Codebase validation failed: {e}")
        return make_response(jsonify({
            "status": "error",
            "message": f"Validation failed: {str(e)}",
            "status_code": 500
        }), 500)