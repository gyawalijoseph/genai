import json
from flask import request, Blueprint, jsonify, make_response

from utilities.utils import safechain_llm_call

llm_bp = Blueprint('llm', __name__)

@llm_bp.route('/LLM-API', methods=['POST'])
def call_llm_api():
    data = request.json
    system_prompt = data.get('system_prompt')
    user_prompt = data.get('user_prompt')
    code_snippet = data.get('codebase')
    output, response_code = safechain_llm_call(system_prompt, user_prompt, code_snippet)
    print(response_code)
    print(output)
    if response_code == 400:
        return make_response(jsonify({
            "status": "error",
            "status_code": response_code,
            "output": output
        }), 400)
    return make_response(jsonify({
        "status": "success",
        "status_code": response_code,
        "output": output
    }), 200)


