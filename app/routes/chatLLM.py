import app.services.ollama as ollama
import app.services.utilis as utilis
import uuid
from flask import Blueprint, render_template, request, jsonify, Response

bp = Blueprint('chatLLM', __name__)

MAIN_MODEL = "llama3.2:3b"
SUMMARIZER_MODEL = "gemma3:1b"

CHATS = {}

@bp.route('/chatLLM')
def chatLLM():
    return render_template('chatLLM.html')

@bp.route('/chatLLM/start', methods=['POST'])
def start_chat():
    session_id = str(uuid.uuid4())
    if session_id not in CHATS:
        CHATS[session_id] = {'user': [], 'assistantAI': []}
    return jsonify({'session_id': session_id})

@bp.route('/chatLLM/sendPrompt', methods=['POST'])
def send_prompt():
    data = request.get_json()
    prompt = data.get('prompt')
    session_id = data.get('sessionId')
    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400
    CHATS[session_id]['user'].append(prompt)
    return jsonify({'error': 'None'})

def event_stream(session_id, prompt):
    full_response = ''

    for chunk in ollama.query_ollama_streaming(prompt, MAIN_MODEL):
        full_response += chunk
        yield f"data: {chunk}\n\n"

    CHATS[session_id]['assistantAI'].append(full_response)

@bp.route('/chatLLM/responseLLM')
def responseLLM():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400
    prompt = CHATS[session_id]['user'][-1]
    return Response(event_stream(session_id, prompt), mimetype='text/event-stream')