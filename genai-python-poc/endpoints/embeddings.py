import os
from flask import Blueprint, request, jsonify
# from service.services import generate_embeddings
from utilities.utils import similarity_search_pgvector

embeddings_bp = Blueprint('embeddings', __name__)

# @embeddings_bp.route('/embed', methods=['POST'])
# def embed_codebase():
#     data = request.json
#     codebase = data.get('codebase')
#     external = data.get('external')
#
#     result = generate_embeddings(codebase, external)
#     if result.get('status') == 'error':
#         return jsonify(result), 400
#     else:
#         return jsonify(result)

@embeddings_bp.route('/vector-search', methods=['POST'])
def search_vector():
    print("Performing vectorstore similarity search")
    data = request.json
    codebase = data.get('codebase')
    query = data.get('query')
    vector_results_count = int(data.get('vector_results_count', 10))

    try:
        print("Performing vectorstore similarity search with codebase:")
        results = similarity_search_pgvector(codebase, query, vector_results_count)

        return jsonify({
            "codebase": codebase,
            "results": results
        })
    except Exception as e:
        return jsonify({
            "codebase": codebase,
            "status": "error",
            "message": str(e)
        })

