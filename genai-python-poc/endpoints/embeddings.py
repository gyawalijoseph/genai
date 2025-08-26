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
    similarity_threshold = float(data.get('similarity_threshold', 0.4))

    try:
        print(f"Performing vectorstore similarity search with codebase: {codebase}, threshold: {similarity_threshold}")
        results = similarity_search_pgvector(codebase, query, vector_results_count, similarity_threshold)

        return jsonify({
            "codebase": codebase,
            "results": results,
            "similarity_threshold": similarity_threshold,
            "filtered_count": len(results)
        })
    except Exception as e:
        return jsonify({
            "codebase": codebase,
            "status": "error",
            "message": str(e)
        })

