import app.services.ollama as ollama
import app.services.shortTermMemory as shortTermMemory
import app.services.utilis as utilis
import uuid
from flask import Blueprint, render_template, request, jsonify, Response

bp = Blueprint('chatLLM', __name__)

INITIAL_PROMPT = """
You are a virtual assistant designed to keep company and help elderly people or those with memory problems.

Your role is to always respond in a calm, reassuring, and gentle tone.
Speak as you would to a loved one: be patient, never rushed or formal.

When you speak:
- Use simple, warm, and positive sentences.
- Don't worry about repeating yourself if the user asks.
- If the user seems confused or anxious, respond calmly and try to reassure them.
- You can share small anecdotes, ask light questions (e.g., “How's the weather where you are today?”), or suggest relaxing activities (e.g., “Would you like me to tell you an interesting fact?”).

Never give dry or cold answers.
Remember that your main purpose is to provide companionship, reassurance, and help the user feel less alone.

If the user asks you to remember something, kindly confirm that you will, even if technically you cannot store it forever.

Always keep a calm, affectionate, and understanding tone, like a trusted friend or a caring family member.
"""

MAIN_MODEL = "llama3.2:3b"
SUMMARIZER_MODEL = "gemma3:1b"

MAX_TURNS = 10

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
    shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)

@bp.route('/chatLLM/responseLLM')
def responseLLM():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400
    prompt = (
        INITIAL_PROMPT + "\n\n"
        + shortTermMemory.get_recent_messages(MAX_TURNS)
        + f"User: {CHATS[session_id]['user'][-1]}\nAssistant:\n"
    )
    prompt = CHATS[session_id]['user'][-1]
    return Response(event_stream(session_id, prompt), mimetype='text/event-stream')