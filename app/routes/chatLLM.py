# --- Local imports ---
import app.services.proactiveLLM as proactiveLLM
import app.services.ollama as ollama
from app.services.shortTermMemory import ChatManager
import app.services.utilis as utilis
import app.services.rag as rag

# --- Standard library imports ---
import uuid, json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, Response
from sentence_transformers import SentenceTransformer
from enum import Enum, auto
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

CHATS_FILE = 'app/chats.json'


bp = Blueprint('chatLLM', __name__)

INITIAL_PROMPT = """ You are a virtual assistant designed to keep company and help elderly people or those with memory problems.
Your role is to always respond in a calm, reassuring, and gentle tone.
Speak as you would to a loved one: be patient, never rushed or formal.
When you speak:
- Use simple, warm, and positive sentences.
- Don't worry about repeating yourself if the user asks.
- If the user seems confused or anxious, respond calmly and try to reassure them.
Never give dry or cold answers.
Remember that your main purpose is to provide companionship, reassurance, and help the user feel less alone.
If the user asks you to remember something, kindly confirm that you will, even if technically you cannot store it forever.
Always keep a calm, affectionate, and understanding tone, like a trusted friend or a caring family member.
If the user asks a direct question, answer it directly without suggesting new topics unless explicitly requested.
"""

MAIN_MODEL = "llama3.2:3b"
SUMMARIZER_MODEL = "gemma3:1b"
MAX_TURNS = 10

# --- RAG config ---
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
COLLECTION_NAME = "document_chunks"
DOCUMENT_PATH = "document.txt"
TOP_K = 3
MIN_SCORE = 0.20

# Inizializza Qdrant tramite funzione utility in rag
#DB_PATH = "qdrant_data"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
MAX_TOKENS = 500

CHATS = {}

ACTIVITIES = [
    "talk about the past", 
    "talk about what you ate today", 
    "talk about your children", 
    "talk about music", 
    "talk about sports"
]

class State(Enum):
    START = auto()
    CHOOSING = auto()
    TOPIC = auto()
    CONVERSATION = auto()    


# --- Qdrant in-memory initialization ---
# Prova diversi approcci per inizializzare Qdrant
try:
    # Prima, prova ad usare il client in-memory (nessun file di lock)
    
    print("Attempting to create in-memory Qdrant client...")
    
    # Opzione 1: Client in-memory
    qdrant_client = QdrantClient(":memory:")
    print("Using in-memory Qdrant client")
    
    # Crea la collezione e riempila
    chunk_list = rag.load_chunks(DOCUMENT_PATH)
    embeddings = rag.compute_embeddings(EMBEDDING_MODEL, chunk_list)
    
    # Inizializza la collezione
    
    qdrant_client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
    )
    
    # Aggiungi i punti
    points = [
        PointStruct(id=i, vector=embedding, payload={"chunk": chunk})
        for i, (embedding, chunk) in enumerate(zip(embeddings, chunk_list))
    ]
    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Successfully populated in-memory Qdrant with {len(points)} chunks")
    
except Exception as e:
    print(f"Failed to initialize Qdrant client in memory: {e}")
    print("Falling back to no RAG mode")
    qdrant_client = None


@bp.route('/chatLLM')
def chatLLM():
    # Uncomment the lines below to preload the models into memory.
    # This speeds up the first response time, but introduces a delay when the page initially loads.
    # ollama.preload_model(MAIN_MODEL)
    # ollama.preload_model(SUMMARIZER_MODEL)
    return render_template('chatLLM.html')


@bp.route('/chatLLM/start', methods=['POST'])
def start_chat():
    # Generate a truly unique session ID (not already in CHATS)
    session_id = str(uuid.uuid4())

    # Extremely unlikely, but this ensures we avoid accidental ID collision
    while session_id in CHATS:
        session_id = str(uuid.uuid4())

    # Initialize session data
    CHATS[session_id] = ChatManager(SUMMARIZER_MODEL, State.START, MAX_TURNS)

    # Ensure the memory is completely cleared for every new session
    #! remove this if we want to enable local storage of the conversation

    # Personally, I think this might not be necessary because it prevents keeping conversation context locally.
    # Commenting it out to allow conversation history to persist during the session.
    # shortTermMemory.clean_history()

    utilis.clear_log_file()
    utilis.clear_log_complete_file()
    utilis.append_log("/chatLLM/start request completed successfully.")

    return jsonify({'session_id': session_id})


@bp.route('/chatLLM/sendPrompt', methods=['POST'])
def send_prompt():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    session_id = data.get('sessionId')

    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400

    CHATS[session_id].add_user_message(prompt)

    return jsonify({'error': 'None'})


@bp.route('/chatLLM/responseLLM')
def responseLLM():
    session_id = request.args.get('session_id')

    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400

    prompt = CHATS[session_id].get_last_user_message()
    
    return Response(event_stream(session_id, prompt), mimetype='text/event-stream')

@bp.route('/chatLLM/uploadChats', methods=['POST'])
def get_chats():
    with open(CHATS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Crea una lista di tuple (session_id, timestamp)
    sessions_with_timestamps = []
    for session_id, chat in data.items():
        timestamp = chat.get('timestamp')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
            except ValueError:
                dt = datetime.min  # fallback in caso di formato errato
        else:
            dt = datetime.min  # fallback in caso manchi il timestamp
        sessions_with_timestamps.append((session_id, dt))

    # Ordina per timestamp decrescente
    sorted_sessions = sorted(sessions_with_timestamps, key=lambda x: x[1], reverse=True)

    # Estrai solo i session_id ordinati
    sorted_session_ids = [session_id for session_id, _ in sorted_sessions]

    return jsonify(sorted_session_ids)

@bp.route('/chatLLM/getChat/<session_id>', methods=['POST'])
def get_single_chat(session_id):
    with open(CHATS_FILE) as f:
        data = json.load(f)
    chat = data.get(session_id)
    if chat:
        CHATS[session_id] = ChatManager(SUMMARIZER_MODEL, State.START, MAX_TURNS, chat.get('user', []), chat.get('assistantAI', []), chat.get('topic', ''))
        return jsonify(chat)
    else:
        return jsonify({'error': 'Chat non trovata'}), 404


def event_stream(session_id, prompt):

    if CHATS[session_id].get_chat_state() == State.START:             # STARTING MESSAGE
        evaluation = proactiveLLM.evaluate_init_msg(
            prompt, 
            MAIN_MODEL
        )

        if "INITIAL" in evaluation:
            yield f"data: Hello! I'm your companion. Would you like to ask me something specific, or would you prefer me to suggest a topic for our conversation?\n\n"
            CHATS[session_id].set_chat_state(State.CHOOSING)
            CHATS[session_id].add_assistant_message("Hello! I'm your companion. Would you like to ask me something specific, or would you prefer me to suggest a topic for our conversation?", session_id, CHATS_FILE)
            return
        elif "QUESTION" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            CHATS[session_id].set_chat_topic('')
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, CHATS_FILE)
        # else: # TODO

    elif CHATS[session_id].get_chat_state() == State.CHOOSING:          #CHOOSING TYPE OF TIPIC
        evaluation = proactiveLLM.evaluate_type_topic(
            prompt, 
            MAIN_MODEL
        )

        if "LLM_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(ACTIVITIES)
            if topic:
                CHATS[session_id].set_chat_topic(topic)
                CHATS[session_id].set_chat_state(State.TOPIC)
                yield f"data: {topic_question}\n\n"
                CHATS[session_id].add_assistant_message(topic_question, session_id, CHATS_FILE)
                return
            else:
                # TODO no more topic
                return
        elif "USER_TOPIC" in evaluation:
            CHATS[session_id].set_chat_topic('')
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, CHATS_FILE)
        # else: # TODO

    elif CHATS[session_id].get_chat_state() == State.TOPIC:             # PROPOSING A TOPIC
        evaluation = proactiveLLM.evaluate_choose_topic(
            prompt, 
            CHATS[session_id].get_chat_topic(),
            MAIN_MODEL
        )

        if "CONTINUE_TOPIC" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, CHATS_FILE)
        elif "CHANGE_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(ACTIVITIES)
            if topic:
                CHATS[session_id].set_chat_topic(topic)
                CHATS[session_id].set_chat_state(State.TOPIC)
                yield f"data: {topic_question}\n\n"
                return
            else:
                # TODO no more topic
                return
        # else: # TODO

    elif CHATS[session_id].get_chat_state() == State.CONVERSATION:          # CONVERSATION
        recent_messages = CHATS[session_id].get_recent_messages()

        evaluation = proactiveLLM.evaluate_general_msg(
            prompt, 
            CHATS[session_id].get_chat_topic(),
            recent_messages,
            MAIN_MODEL
        )



        if "CONTINUE_TOPIC" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, CHATS_FILE)
        elif "CHANGE_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(ACTIVITIES)
            if topic:
                CHATS[session_id].set_chat_topic(topic)
                CHATS[session_id].set_chat_state(State.TOPIC)
                yield f"data: {topic_question}\n\n"
                return
            else:
                # TODO no more topic
                return
        elif "END" in evaluation:
            yield f"data: Goodbye! It was nice chatting with you. Take care!\n\n"
            return
        elif "NEW_QUESTION" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            CHATS[session_id].set_chat_topic('')
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, CHATS_FILE)
        # else: # TODO



def conversation_llm(input, session_id):

    prompt = INITIAL_PROMPT

    relevant_chunks = ""
    if qdrant_client:
        try:
            relevant_chunks = rag.get_relevant_chunks(qdrant_client, COLLECTION_NAME, EMBEDDING_MODEL, prompt, TOP_K, MIN_SCORE)

            prompt += (
                f"\nThese are some pieces of information you can base your response on, and the information refers to the person you are talking to:\n"
                f"{relevant_chunks}"
            )

            print("Successfully retrieved relevant chunks from RAG")
        except Exception as e:
            print(f"Error retrieving chunks: {e}")
    else:
        print("Skipping RAG retrieval - Qdrant client not available")

    recent_messages = CHATS[session_id].get_recent_messages()

    prompt += (
        f"\nHere is the conversation so far with the user:\n"
        f"{recent_messages}"
    )

    prompt += (
        f"\nHere is the user's latest message that you need to reply to:\n"
        f"{input}"
    )

    return prompt






'''
def event_stream(session_id, prompt):
    # Inizializza stati della sessione se non presenti
    if 'topic' not in CHATS[session_id]:
        CHATS[session_id]['topic'] = None
    # if 'topic_suggested' not in CHATS[session_id]:
    #     CHATS[session_id]['topic_suggested'] = False

    # Recupera i messaggi recenti per dare contesto alla valutazione

    # Se c'è un topic attivo, valuta se l'utente vuole continuare, cambiare o chiudere
    if CHATS[session_id]['topic']:
        recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
        topic_eval = proactiveLLM.evaluate_topic_continuation(
            prompt,
            CHATS[session_id]['topic'],
            MAIN_MODEL,
            recent_messages=recent_messages
        )
        if topic_eval == "CONTINUE_TOPIC":
            recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
            # L'utente accetta il topic suggerito, si continua su quello
            pass  # prosegui con la risposta normale
        elif topic_eval == "CHANGE_TOPIC":
            # L'utente vuole cambiare argomento: capiamo se è una domanda diretta o vuole un nuovo suggerimento
            recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
            change_eval = proactiveLLM.evaluate_user_message(
                recent_messages,
                prompt,
                MAIN_MODEL
            )
            if change_eval == "OWN_QUESTION":
                recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
                # Procedi con la risposta normale (non suggerire un topic, resetta il topic attivo)
                CHATS[session_id]['topic'] = None
                # ...continua dopo il blocco if, generando la risposta normale...
            elif change_eval == "SUGGEST_TOPIC":
                recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
                activity, topic_question = proactiveLLM.suggest_new_topic(
                    ACTIVITIES,
                    MAIN_MODEL,
                    current_topic=CHATS[session_id]['topic']
                )
                if activity:
                    CHATS[session_id]['topic'] = activity
                    yield f"data: {topic_question}\n\n"
                    return
                else:
                    CHATS[session_id]['topic'] = None
                    yield f"data: What would you like to talk about then?\n\n"
                    return
        elif topic_eval == "END_CONVERSATION":
            yield f"data: Goodbye! It was nice chatting with you. Take care!\n\n"
            return
    else:
        # Nessun topic attivo: valuta il messaggio normalmente
        recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
        evaluation = proactiveLLM.evaluate_user_message(
            recent_messages,
            prompt, 
            MAIN_MODEL
        )

        if evaluation == "END_CONVERSATION":
            yield f"data: Goodbye! It was nice chatting with you. Take care!\n\n"
            return
        elif evaluation == "SUGGEST_TOPIC":
            activity, topic_question = proactiveLLM.find_the_topic(ACTIVITIES)
            if activity:
                CHATS[session_id]['topic'] = activity
                yield f"data: {topic_question}\n\n"
                return
            else:
                yield f"data: I'm sorry, I don't have any more topics to suggest. What would you like to talk about?\n\n"
                return

    # Gestione normale delle risposte con RAG
    relevant_chunks = ""
    if qdrant_client:
        try:
            relevant_chunks = rag.get_relevant_chunks(qdrant_client, COLLECTION_NAME, EMBEDDING_MODEL, prompt, TOP_K, MIN_SCORE)
            print("Successfully retrieved relevant chunks from RAG")
        except Exception as e:
            print(f"Error retrieving chunks: {e}")
    else:
        print("Skipping RAG retrieval - Qdrant client not available")

    # Costruisci il prompt per Ollama
    recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)
    context_prompt = INITIAL_PROMPT
    if CHATS[session_id]['topic']:
        context_prompt += f"\n\nCurrent conversation topic: {CHATS[session_id]['topic']}. Keep the conversation relevant to this topic while being natural and engaging."
    if not recent_messages.strip():
        ollama_prompt = rag.format_rag_prompt(context_prompt, relevant_chunks, "", prompt)
    else:
        ollama_prompt = rag.format_rag_prompt(context_prompt, relevant_chunks, recent_messages, prompt)

    full_response = ''
    for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
        full_response += chunk
        yield f"data: {chunk}\n\n"

    CHATS[session_id]['assistantAI'].append(full_response)
    shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)
'''    

@bp.route('/chatLLM/newChat', methods=['POST'])
def clear_memory():
    # Generate a truly unique session ID (not already in CHATS)
    session_id = str(uuid.uuid4())

    # Extremely unlikely, but this ensures we avoid accidental ID collision
    while session_id in CHATS:
        session_id = str(uuid.uuid4())

    # Initialize session data
    CHATS[session_id] = ChatManager(SUMMARIZER_MODEL, State.START, MAX_TURNS)
    # shortTermMemory.clean_history()
    return jsonify({'session_id': session_id})