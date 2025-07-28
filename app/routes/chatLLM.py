# --- Local imports ---
import app.services.proactiveLLM as proactiveLLM
import app.services.ollama as ollama
from app.services.shortTermMemory import ChatManager
import app.services.utils as utils
import app.services.rag as rag
import app.services.config as config
from app.services.config import State as State

# --- Standard library imports ---
import uuid, json, random
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, Response

bp = Blueprint('chatLLM', __name__)

# Initialize vector database for RAG service
utils.append_server_log("Initializing RAG service...")
rag.initialize_db()
utils.append_server_log("RAG service initialized successfully.")

# Dictionary to store chat sessions.
# Each key is a session ID, and each value is an instance of the ChatManager class (from shortTermMemory.py).
# ChatManager is used to keep track of the conversation history and other useful parameters.
CHATS = {}


@bp.route('/chatLLM')
def chatLLM():
    '''
    Handles the GET request to /chatLLM.
    Optionally preloads models (commented out), and clears previous log files
    before rendering the chat interface.
    '''

    # ollama.preload_model(MAIN_MODEL)
    # ollama.preload_model(SUMMARIZER_MODEL)

    # Clear previous log files to start fresh for the new session
    utils.clear_server_log()
    utils.clear_conversation_log()

    # Render the chat interface template
    return render_template('chatLLM.html')


@bp.route('/chatLLM/newSessionID', methods=['POST'])
def new_session_id():
    '''
    Handles the POST request to /chatLLM/start.
    Generates a new unique session ID and initializes a new ChatManager instance
    for that session. Returns the session ID as a JSON response.
    '''

    # Generate a truly unique session ID (not already present in CHATS)
    session_id = generate_session_id()

    # Initialize a new ChatManager instance for the session
    # This manages the conversation history and short-term memory
    CHATS[session_id] = ChatManager(config.SUMMARIZER_MODEL, State.START, config.MAX_TURNS)

    # Log that the start request has been successfully processed
    utils.append_server_log("/chatLLM/start request completed successfully.")

    # Return a structured JSON response with success and session ID
    return jsonify({'success': True, 'message': session_id})


@bp.route('/chatLLM/sendPrompt', methods=['POST'])
def send_prompt():
    '''
    Handles the POST request to /chatLLM/sendPrompt.
    Receives a user prompt and session ID from the client,
    validates the session, and adds the prompt to the chat history.
    Returns a JSON response indicating success or error.
    '''

    # Parse JSON data from the request
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    session_id = data.get('sessionId')

    # Validate the session ID
    if not session_id or session_id not in CHATS:
        return jsonify({'success': False, 'message': 'Invalid session_id'})

    # Add the user's prompt to the chat history managed by ChatManager
    CHATS[session_id].add_user_message(prompt)

    # Return a success response
    return jsonify({'success': True, 'message': ''})


@bp.route('/chatLLM/responseLLM')
def responseLLM():
    '''
    Handles GET requests to /chatLLM/responseLLM.
    Retrieves the session ID from query parameters, validates it,
    fetches the last user message from the chat history,
    and returns a streamed response using Server-Sent Events (SSE).
    '''

    # Get the session_id from query parameters
    session_id = request.args.get('session_id')

    # Validate the session_id
    if not session_id or session_id not in CHATS:
        return jsonify({'success': False, 'message': 'Invalid session_id'})

    # Retrieve the last message sent by the user in this session
    prompt = CHATS[session_id].get_last_user_message()
    
    # Return a streaming response with mimetype for Server-Sent Events (SSE)
    return Response(event_stream(session_id, prompt), mimetype='text/event-stream')


@bp.route('/chatLLM/uploadChats', methods=['POST'])
def get_chats():
    '''
    Reads the stored chat sessions from a JSON file,
    sorts them by timestamp (most recent first),
    and returns a list of session IDs in JSON format.
    '''

    # Read the chat file content
    with open(config.CHATS_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    # If the file is empty, return an empty list with success status
    if not content:
        return jsonify({'success': False, 'message': 'No chat sessions found.'})

    # Load the JSON content into a dictionary
    data = json.loads(content)

    # Prepare a list of tuples (session_id, timestamp)
    sessions_with_timestamps = []
    for session_id, chat in data.items():
        timestamp = chat.get('timestamp')
        if timestamp:
            try:
                # Parse the ISO format timestamp
                dt = datetime.fromisoformat(timestamp)
            except ValueError:
                # Fallback to minimal date if timestamp format is invalid
                dt = datetime.min
        else:
            # Fallback to minimal date if timestamp is missing
            dt = datetime.min

        sessions_with_timestamps.append((session_id, dt))

    # Sort sessions by timestamp in ascending order
    sorted_sessions = sorted(sessions_with_timestamps, key=lambda x: x[1])

    # Return the sorted session IDs with a success message
    return jsonify({'success': True, 'message': sorted_sessions})


@bp.route('/chatLLM/getChat', methods=['POST'])
def get_single_chat():
    '''
    Handles POST request to retrieve a single chat session by session_id.
    The session_id is expected in the JSON body of the request.
    Loads the chat from file, initializes the ChatManager instance,
    and returns the chat data as JSON.
    '''

    # Parse JSON data from the request body
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        # Return error if session_id is missing
        return jsonify({'success': False, 'message': 'Missing session_id'})

    # Load all chats from the configured file
    with open(config.CHATS_FILE, 'r', encoding='utf-8') as f:
        all_chats = json.load(f)

    # Get the specific chat data by session_id
    chat = all_chats.get(session_id)

    if chat:
        # Initialize ChatManager for this session with loaded history
        CHATS[session_id] = ChatManager(
            config.SUMMARIZER_MODEL,
            State.START,
            config.MAX_TURNS,
            chat.get('user', []),
            chat.get('assistantAI', []),
            chat.get('topic', '')
        )
        # Return the chat data to the client
        return jsonify({'success': True, 'message': chat})

    else:
        # Return 404 if chat not found
        return jsonify({'success': False, 'message': 'Chat not found'})


@bp.route('/chatLLM/cleanChats', methods=['POST'])
def clean_chats():
    '''
    Handles POST request to /chatLLM/cleanChats.
    Clears the in-memory CHATS dictionary and overwrites the chat file on disk,
    effectively removing all saved chat sessions.
    '''

    global CHATS
    CHATS = {}  # Reset the in-memory chat session store

    try:
        # Overwrite the chat file with an empty JSON object
        with open(config.CHATS_FILE, 'w', encoding='utf-8') as f:
            f.write('{}')  # Keeps JSON format consistent

        # Return success response
        return jsonify({'success': True, 'message': 'Chats cleaned successfully.'})
    
    except Exception:
        # Return error response with exception message
        return jsonify({'success': False, 'message': 'Failed to clean chats.'})


def event_stream(session_id, prompt, retry=False):
    '''
    Depending on the current state of the conversation between the user and the AI assistant, 
    we perform different actions.
    '''

    # If the conversation hasn't started yet (receiving the user's first message),
    # we check whether the user has already asked a specific question or just greeted.
    if CHATS[session_id].get_chat_state() == State.START:
        evaluation = proactiveLLM.evaluate_init_msg(prompt, config.MAIN_MODEL)

        if "INITIAL" in evaluation:
            suggest_topic_sentence = random.choice(config.SUGGEST_TOPIC_SENTENCES)
            yield f"data: {suggest_topic_sentence}\n\n"
            CHATS[session_id].set_chat_state(State.CHOOSING)
            CHATS[session_id].add_assistant_message(suggest_topic_sentence, session_id, config.CHATS_FILE)
            return
        elif "QUESTION" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            CHATS[session_id].set_chat_topic('')
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, config.MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, config.CHATS_FILE)
        else:
            if not retry:
                yield from event_stream(session_id, prompt, retry=True)
            else:
                fallback_msg = "Sorry, I'm not sure how to respond. Could you please rephrase your message?"
                yield f"data: {fallback_msg}\n\n"
                CHATS[session_id].add_assistant_message(fallback_msg, session_id, config.CHATS_FILE)
            return

    # If the user is in the decision-making phase, we check whether they are asking the assistant
    # to suggest some topics to talk about, or if they are specifying a topic themselves.
    elif CHATS[session_id].get_chat_state() == State.CHOOSING:
        evaluation = proactiveLLM.evaluate_type_topic(prompt, config.MAIN_MODEL)

        if "LLM_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(config.ACTIVITIES)
            if topic:
                CHATS[session_id].set_chat_state(State.TOPIC)
                CHATS[session_id].set_chat_topic(topic)
                yield f"data: {topic_question}\n\n"
                CHATS[session_id].add_assistant_message(topic_question, session_id, config.CHATS_FILE)
                return
            else:
                fallback_message = "I think I've run out of ideas for now but I'd love to hear from you! Is there anything you'd like to talk about?"
                CHATS[session_id].set_chat_state(State.CONVERSATION)
                CHATS[session_id].set_chat_topic('')
                yield f"data: {fallback_message}\n\n"
                CHATS[session_id].add_assistant_message(fallback_message, session_id, config.CHATS_FILE)
                return
        elif "USER_TOPIC" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            CHATS[session_id].set_chat_topic('')
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, config.MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, config.CHATS_FILE)
            return
        else:
            if not retry:
                yield from event_stream(session_id, prompt, retry=True)
            else:
                fallback_msg = "Sorry, I'm not sure how to respond. Could you please rephrase your message?"
                yield f"data: {fallback_msg}\n\n"
                CHATS[session_id].add_assistant_message(fallback_msg, session_id, config.CHATS_FILE)
            return

    # In the case where a TOPIC has been suggested to the user, we need to check whether the user agrees with the topic or not.
    # For example, they might say they don't enjoy talking about that subject.
    elif CHATS[session_id].get_chat_state() == State.TOPIC:
        evaluation = proactiveLLM.evaluate_choose_topic(prompt, CHATS[session_id].get_chat_topic(), config.MAIN_MODEL)

        if "CONTINUE_TOPIC" in evaluation:
            CHATS[session_id].set_chat_state(State.CONVERSATION)
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, config.MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, config.CHATS_FILE)
            return
        elif "CHANGE_TOPIC" in evaluation:
            topic, topic_question = proactiveLLM.find_the_topic(config.ACTIVITIES)
            if topic:
                CHATS[session_id].set_chat_state(State.TOPIC)
                CHATS[session_id].set_chat_topic(topic)
                yield f"data: {topic_question}\n\n"
                CHATS[session_id].add_assistant_message(topic_question, session_id, config.CHATS_FILE)
                return
            else:
                fallback_message = "I think I've run out of ideas for now but I'd love to hear from you! Is there anything you'd like to talk about?"
                CHATS[session_id].set_chat_state(State.CONVERSATION)
                CHATS[session_id].set_chat_topic('')
                yield f"data: {fallback_message}\n\n"
                CHATS[session_id].add_assistant_message(fallback_message, session_id, config.CHATS_FILE)
                return
        else:
            if not retry:
                yield from event_stream(session_id, prompt, retry=True)
            else:
                fallback_msg = "Sorry, I'm not sure how to respond. Could you please rephrase your message?"
                yield f"data: {fallback_msg}\n\n"
                CHATS[session_id].add_assistant_message(fallback_msg, session_id, config.CHATS_FILE)
            return

    # In the case where we are in the middle of a conversation, 
    # it may happen that the user asks a completely off-topic question, 
    # so this situation must be handled accordingly.
    elif CHATS[session_id].get_chat_state() == State.CONVERSATION:
        recent_messages = CHATS[session_id].get_recent_messages()
        evaluation = proactiveLLM.evaluate_general_msg(prompt, CHATS[session_id].get_chat_topic(), recent_messages, config.MAIN_MODEL)

        if "CONTINUE_TOPIC" in evaluation:
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, config.MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, config.CHATS_FILE)
        elif "NEW_QUESTION" in evaluation:
            CHATS[session_id].set_chat_topic('')
            ollama_prompt = conversation_llm(prompt, session_id)

            full_response = ''
            for chunk in ollama.query_ollama_streaming(ollama_prompt, config.MAIN_MODEL):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            CHATS[session_id].add_assistant_message(full_response, session_id, config.CHATS_FILE)
        else:
            if not retry:
                yield from event_stream(session_id, prompt, retry=True)
            else:
                fallback_msg = "Sorry, I'm not sure how to respond. Could you please rephrase your message?"
                yield f"data: {fallback_msg}\n\n"
                CHATS[session_id].add_assistant_message(fallback_msg, session_id, config.CHATS_FILE)
            return



def conversation_llm(input, session_id):

    prompt = config.INITIAL_PROMPT

    # ----- RAG ------ #
    relevant_chunks = ""
    try:
        relevant_chunks = rag.get_relevant_chunks(prompt)

        if relevant_chunks:
            prompt += (
                f"\nThese are some pieces of information you can base your response on, and the information refers to the person you are talking to:\n"
                f"{relevant_chunks}"
            )

        utils.append_server_log("Successfully retrieved relevant chunks from RAG")
    except Exception as e:
        utils.append_server_log(f"Error retrieving chunks: {e}")

    # ----- SHORT TERM MEMORY -----#
    recent_messages = CHATS[session_id].get_recent_messages()

    if recent_messages:
        prompt += (
            f"\nHere is the conversation so far with the user:\n"
            f"{recent_messages}"
        )

    # ----- FINAL PROMPT ------ #
    prompt += (
        f"\nHere is the user's latest message that you need to reply to:\n"
        f"{input}"
    )

    utils.append_conversation_log(f"Final PROMPT:\n{prompt}\n\n")

    return prompt



    
def generate_session_id():
    '''
    Generates a unique session ID using UUID4.
    Ensures the ID does not already exist in the CHATS dictionary,
    avoiding any potential collision with existing chat sessions.
    '''

    session_id = str(uuid.uuid4())

    while session_id in CHATS:
        session_id = str(uuid.uuid4())
    
    return session_id





'''# elif "CHANGE_TOPIC" in evaluation:
        #     topic, topic_question = proactiveLLM.find_the_topic(ACTIVITIES)
        #     if topic:
        #         CHATS[session_id].set_chat_topic(topic)
        #         CHATS[session_id].set_chat_state(State.TOPIC)
        #         yield f"data: {topic_question}\n\n"
        #         return
        #     else:
        #         # TODO no more topic
        #         return
        # elif "END" in evaluation:
        #     yield f"data: Goodbye! It was nice chatting with you. Take care!\n\n"
        #     return'''