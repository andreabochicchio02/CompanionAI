import libraries.rag as rag
import libraries.ollama as ollama
import libraries.textSpeech as textSpeech
import libraries.proactiveLLM as proactiveLLM
import libraries.shortTermMemory as shortTermMemory

from sentence_transformers import SentenceTransformer
from datetime import datetime

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

ACTIVITIES = [
    "Talk about the past",
    "Talk about what you ate today",
    "Talk about your children",
    "Talk about music",
    "Talk about sports"
]

TEXT_TO_SPEECH = False

SPEECH_TO_TEXT = False

MAIN_MODEL = "llama3.2:3b"

SUMMARIZER_MODEL = "gemma3:1b"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

COLLECTION_NAME = "document_chunks"
DOCUMENT_PATH = "document.txt"
DB_PATH = "qdrant_data"

# RAG
TOP_K = 3
MIN_SCORE = 0.4
MAX_TOKENS = 500

# SHORT-TERM-MEMORY
MAX_TURNS = 10

def main():
    current_activity = None

    qdrant_client = rag.create_db(EMBEDDING_MODEL, DOCUMENT_PATH, MAX_TOKENS, EMBEDDING_MODEL_NAME, COLLECTION_NAME, DB_PATH)

    ollama.preload_model(model_name=MAIN_MODEL)
    ollama.preload_model(model_name=SUMMARIZER_MODEL)

    # DEBUG
    with open("log.txt", "w") as f:
        f.write("")

    print("\nChat with Ollama is active! (type 'exit' to quit)")
    
    while True:
        # If we don't have a current activity, suggest one
        if current_activity is None:
            current_activity, prompt = proactiveLLM.find_the_topic(ACTIVITIES, MAIN_MODEL, TEXT_TO_SPEECH, SPEECH_TO_TEXT)
            if not current_activity:
                print(prompt)
                break

        # Generate response and get user reply
        response = ollama.query_ollama_streaming(prompt, MAIN_MODEL)    # If current_activity was None: prompt = "Let's have a conversation about this topic: ..."

        if TEXT_TO_SPEECH:
            textSpeech.text_to_speech_locally(response)

        user_input = f"I would like to {current_activity}"
        shortTermMemory.update_history(user_input, response, MAX_TURNS, SUMMARIZER_MODEL)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(
                f"[{timestamp}]\n"
                f"********** USER INPUT **********:\n{user_input}\n\n"
                f"********** FULL PROMPT **********:\n{prompt}\n"
                f"{'='*40}\n\n"
            )
        
        user_input = ""

        if SPEECH_TO_TEXT:
            print("\nUser (Speak now...): ")
            user_input = textSpeech.speech_to_text_locally()
            print(user_input)
        else:
            user_input = input("\nUser: ")

        if user_input.lower() == "exit" or not user_input:
            print("Chat ended.")
            break
        
        # Evaluate response relevance
        evaluation = proactiveLLM.evaluate_response_relevance(prompt, user_input, current_activity, MAIN_MODEL)
        print(f"\n[Debug: Action: {evaluation['action']}, Reason: {evaluation['reason']}]")
        
        if evaluation['action'] == "END_CONVERSATION":
            break
        elif evaluation['action'] == "CHANGE_TOPIC":
            current_activity = None
            shortTermMemory.clean_history()
        elif evaluation['action'] == "CONTINUE_TOPIC":
            prompt = INITIAL_PROMPT + "\n\n"

            prompt += rag.get_relevant_chunks(qdrant_client, COLLECTION_NAME, EMBEDDING_MODEL, user_input, TOP_K, MIN_SCORE)

            prompt += shortTermMemory.get_recent_messages(MAX_TURNS)

            prompt += (
                f"User: {user_input}\n"
                "Assistant:\n"
                f"Continue the conversation about '{current_activity}' with a new question or comment. Keep the conversation engaging and natural."
            )
        

if __name__ == "__main__":
    main()