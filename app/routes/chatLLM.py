# --- Topic suggestion ---
import app.services.proactiveLLM as proactiveLLM

import app.services.ollama as ollama
import app.services.shortTermMemory as shortTermMemory
import app.services.utilis as utilis
import uuid
from flask import Blueprint, render_template, request, jsonify, Response

# --- RAG imports ---
import app.services.rag as rag
from sentence_transformers import SentenceTransformer

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


from enum import Enum, auto

class State(Enum):
    START = auto()
    CHOOSING = auto()
    TOPIC = auto()
    CONVERSATION = auto()


# --- Qdrant in-memory initialization ---
# Prova diversi approcci per inizializzare Qdrant
try:
    # Prima, prova ad usare il client in-memory (nessun file di lock)
    from qdrant_client import QdrantClient
    print("Attempting to create in-memory Qdrant client...")
    
    # Opzione 1: Client in-memory
    qdrant_client = QdrantClient(":memory:")
    print("Using in-memory Qdrant client")
    
    # Crea la collezione e riempila
    chunk_list = rag.load_chunks(DOCUMENT_PATH)
    embeddings = rag.compute_embeddings(EMBEDDING_MODEL, chunk_list)
    
    # Inizializza la collezione
    from qdrant_client.models import VectorParams, Distance, PointStruct
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

CHATS = {}

activities = [
    "talk about the past", 
    "talk about what you ate today", 
    "talk about your children", 
    "talk about music", 
    "talk about sports"
]

@bp.route('/chatLLM')
def chatLLM():
    return render_template('chatLLM.html')

@bp.route('/chatLLM/start', methods=['POST'])
def start_chat():
    session_id = str(uuid.uuid4())
    if session_id not in CHATS:
        CHATS[session_id] = {
            'user': [], 
            'assistantAI': [],
            'topic': '',
            'state': State.START
        }
    # Assicurati che la memoria sia completamente pulita per ogni nuova sessione
    #! da rimuovere se vogliamo localstorage della conversazione
    shortTermMemory.clean_history()

    utilis.append_log(f"START")
    utilis.clear_log_complete_file()
    return jsonify({'session_id': session_id})

@bp.route('/chatLLM/sendPrompt', methods=['POST'])
def send_prompt():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    session_id = data.get('sessionId')

    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400

    CHATS[session_id]['user'].append(prompt)
    utilis.append_log(f"USER: {prompt}")
    return jsonify({'error': 'None'})

# Funzione per gestire il flusso di eventi
@bp.route('/chatLLM/responseLLM')
def responseLLM():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHATS:
        return jsonify({'error': 'Invalid session_id'}), 400

    prompt = CHATS[session_id]['user'][-1]
    return Response(event_stream(session_id, prompt), mimetype='text/event-stream')


def event_stream(session_id, prompt):

    if CHATS[session_id]['state'] == State.START:             # STARTING MESSAGE
        evaluation = proactiveLLM.evaluate_init_msg(
            prompt, 
            MAIN_MODEL
        )

        if "INITIAL" in evaluation:
            yield f"data: Hello! I'm your companion. Would you like to ask me something specific, or would you prefer me to suggest a topic for our conversation?\n\n"
            CHATS[session_id]['state'] = State.CHOOSING
            return
        elif "QUESTION" in evaluation:
            CHATS[session_id]['state'] = State.CONVERSATION
            CHATS[session_id]['topic'] = ""
            ollama_prompt = conversation_llm(prompt)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id]['assistantAI'].append(full_response)
            shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)
        # else: # TODO

    elif CHATS[session_id]['state'] == State.CHOOSING:          #CHOOSING TYPE OF TIPIC
        evaluation = proactiveLLM.evaluate_type_topic(
            prompt, 
            MAIN_MODEL
        )

        if "LLM_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(activities)
            if topic:
                CHATS[session_id]['topic'] = topic
                CHATS[session_id]['state'] = State.TOPIC
                yield f"data: {topic_question}\n\n"
                return
            else:
                # TODO no more topic
                return
        elif "USER_TOPIC" in evaluation:
            CHATS[session_id]['state'] = State.CONVERSATION
            CHATS[session_id]['topic'] = ""
            ollama_prompt = conversation_llm(prompt)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id]['assistantAI'].append(full_response)
            shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)
        # else: # TODO

    elif CHATS[session_id]['state'] == State.TOPIC:             # PROPOSING A TOPIC
        evaluation = proactiveLLM.evaluate_choose_topic(
            prompt, 
            CHATS[session_id]['topic'],
            MAIN_MODEL
        )

        if "CONTINUE_TOPIC" in evaluation:
            CHATS[session_id]['state'] = State.CONVERSATION
            ollama_prompt = conversation_llm(prompt)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id]['assistantAI'].append(full_response)
            shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)
        elif "CHANGE_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(activities)
            if topic:
                CHATS[session_id]['topic'] = topic
                CHATS[session_id]['state'] = State.TOPIC
                yield f"data: {topic_question}\n\n"
                return
            else:
                # TODO no more topic
                return
        # else: # TODO

    elif CHATS[session_id]['state'] == State.CONVERSATION:          # CONVERSATION
        recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)

        evaluation = proactiveLLM.evaluate_general_msg(
            prompt, 
            CHATS[session_id]['topic'],
            recent_messages,
            MAIN_MODEL
        )



        if "CONTINUE_TOPIC" in evaluation:
            CHATS[session_id]['state'] = State.CONVERSATION
            ollama_prompt = conversation_llm(prompt)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id]['assistantAI'].append(full_response)
            shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)
        elif "CHANGE_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(activities)
            if topic:
                CHATS[session_id]['topic'] = topic
                CHATS[session_id]['state'] = State.TOPIC
                yield f"data: {topic_question}\n\n"
                return
            else:
                # TODO no more topic
                return
        elif "END" in evaluation:
            yield f"data: Goodbye! It was nice chatting with you. Take care!\n\n"
            return
        elif "NEW_QUESTION" in evaluation:
            CHATS[session_id]['state'] = State.CONVERSATION
            CHATS[session_id]['topic'] = ""
            ollama_prompt = conversation_llm(prompt)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id]['assistantAI'].append(full_response)
            shortTermMemory.update_history(CHATS[session_id]['user'][-1], full_response, MAX_TURNS, SUMMARIZER_MODEL)
        # else: # TODO



def conversation_llm(input):

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

    recent_messages = shortTermMemory.get_recent_messages(MAX_TURNS)

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
                    activities,
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
            activity, topic_question = proactiveLLM.find_the_topic(activities)
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

@bp.route('/chatLLM/clearMemory', methods=['POST'])
def clear_memory():
    shortTermMemory.clean_history()
    return jsonify({'status': 'success', 'message': 'Memory cleared'})