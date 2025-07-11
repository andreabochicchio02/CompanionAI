import app.services.ollama as ollama
import uuid
from flask import Blueprint, render_template, request, jsonify, Response

bp = Blueprint('chatLLM', __name__)

MAIN_MODEL = "llama3.2:3b"

prompt = ''

@bp.route('/chatLLM')
def chatLLM():
    return render_template('chatLLM.html')

@bp.route('/chatLLM/start', methods=['POST'])
def start_chat():
    global prompt
    data = request.get_json()
    prompt = data.get('prompt')
    session_id = str(uuid.uuid4())
    return jsonify({'session_id': session_id})

@bp.route('/chatLLM/responseLLM')
def responseLLM():
    def event_stream():
        for chunk in ollama.query_ollama_streaming(prompt, MAIN_MODEL):
            yield f"data: {chunk}\n\n"
    return Response(event_stream(), mimetype='text/event-stream')