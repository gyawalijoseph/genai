"""
Dynamic Flask App with Refactored Spec Generation
Updated with LangChain integration and proper error handling
"""
import os
import logging
from flask import Flask
from pathlib import Path
from dotenv import load_dotenv
from flasgger import Swagger

# Import blueprints
from endpoints.embeddings import embeddings_bp
from endpoints.LLM import llm_bp
from endpoints.spec_generation_updated import spec_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern"""
    
    app = Flask(__name__)
    
    # Load environment configuration
    load_environment()
    
    # Configure Flask app
    app.config.update(
        DEBUG=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key'),
        JSON_SORT_KEYS=False
    )
    
    # Initialize Swagger for API documentation
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs/"
    }
    
    swagger = Swagger(app, config=swagger_config)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    logger.info("Flask application created successfully")
    return app

def load_environment():
    """Load environment variables from appropriate source"""
    
    try:
        if 'EPAAS_ENV' in os.environ:
            # Production environment
            env_path = Path('/opt/epaas/vault/secrets/secrets')
            logger.info("Loading production environment variables")
        else:
            # Development environment
            env_path = Path('.env')
            logger.info("Loading development environment variables")
        
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            logger.info(f"Environment loaded from {env_path}")
        else:
            logger.warning(f"Environment file not found at {env_path}")
            
    except Exception as e:
        logger.error(f"Failed to load environment: {e}")

def register_blueprints(app):
    """Register all application blueprints"""
    
    try:
        # Vector search and embeddings
        app.register_blueprint(embeddings_bp, url_prefix='/api')
        logger.info("Registered embeddings blueprint")
        
        # LLM processing  
        app.register_blueprint(llm_bp, url_prefix='/api')
        logger.info("Registered LLM blueprint")
        
        # Dynamic specification generation
        app.register_blueprint(spec_bp, url_prefix='/api')
        logger.info("Registered spec generation blueprint")
        
    except Exception as e:
        logger.error(f"Failed to register blueprints: {e}")
        raise

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return {
            "status": "error",
            "message": "Endpoint not found",
            "status_code": 404
        }, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return {
            "status": "error", 
            "message": "Internal server error",
            "status_code": 500
        }, 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.error(f"Unhandled exception: {error}")
        return {
            "status": "error",
            "message": "An unexpected error occurred", 
            "status_code": 500
        }, 500

@app.route('/health')
def health_check():
    """Application health check"""
    return {
        "status": "healthy",
        "service": "genai-specification-service",
        "version": "2.0.0",
        "endpoints": {
            "embeddings": "/api/vector-search",
            "llm": "/api/LLM-API", 
            "spec_generation": "/api/generate-spec",
            "component_extraction": "/api/extract-component",
            "docs": "/docs/"
        }
    }

# Create the application instance
app = create_app()

if __name__ == '__main__':
    # Configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 8082))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask application on {host}:{port}")
    logger.info(f"Debug mode: {debug}")
    logger.info("API Documentation available at: http://localhost:8082/docs/")
    
    try:
        app.run(
            host=host,
            port=port, 
            debug=debug,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask application: {e}")
        raise