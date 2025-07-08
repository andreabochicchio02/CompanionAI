from flask import Blueprint, render_template, request, jsonify
import app.services.ollama as ollama

bp = Blueprint('chatLLM', __name__)

MAIN_MODEL = "llama3.2:3b"

@bp.route('/chatLLM')
def chatLLM():
    return render_template('chatLLM.html')

@bp.route('/chatLLM/responseLLM', methods=['POST'])
def responseLLM():
    data = request.get_json()
    prompt = data.get('message')

    response = ollama.query_ollama_no_stream(prompt, MAIN_MODEL)
    
    return jsonify({"response": response})