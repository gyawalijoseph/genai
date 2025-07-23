import os
from flask import Flask
from endpoints.Information import information_bp
from pathlib import Path
from dotenv import load_dotenv
from flasgger import Swagger
from endpoints.embeddings import embeddings_bp

if 'EPAAS_ENV' in os.environ:
    myenv = os.environ['EPAAS_ENV']
    dotenv_path = Path('/opt/epaas/vault/secrets/secrets')
else:
    myenv = "e0"
    dotenv_path = Path('..env')

load_dotenv(dotenv_path=dotenv_path)

app = Flask(__name__)
swagger = Swagger(app)

app.register_blueprint(embeddings_bp)

app.register_blueprint(llm_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")
