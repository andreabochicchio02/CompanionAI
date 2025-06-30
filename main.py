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
        print("\nWrite a free-form question, or press Enter to let the system choose a topic for you.")
        if SPEECH_TO_TEXT:
            print("\nUser (Speak now...): ")
            user_input = textSpeech.speech_to_text_locally()
            print(user_input)
        else:
            user_input = input("\nUser: ").strip()

        if user_input.lower() == "exit":
            print("Chat ended.")
            break

        if not user_input:
            # Nessuna preferenza: il sistema propone un topic
            current_activity, prompt = proactiveLLM.find_the_topic(ACTIVITIES, MAIN_MODEL, TEXT_TO_SPEECH, SPEECH_TO_TEXT)
            if not current_activity:
                print(prompt)
                break
            response = ollama.query_ollama_streaming(prompt, MAIN_MODEL)
            if TEXT_TO_SPEECH:
                textSpeech.text_to_speech_locally(response)
            print(response)
            continue

        # Se l'utente ha scritto una domanda, controlla la similarità con i chunk del documento
        relevant_chunks = rag.get_relevant_chunks(qdrant_client, COLLECTION_NAME, EMBEDDING_MODEL, user_input, TOP_K, MIN_SCORE)
        if relevant_chunks.strip():
            # Usa RAG: costruisci il prompt con il contesto
            prompt = (
                INITIAL_PROMPT + "\n\n"
                + relevant_chunks
                + shortTermMemory.get_recent_messages(MAX_TURNS)
                + f"User: {user_input}\nAssistant:\n"
            )
            response = ollama.query_ollama_streaming(prompt, MAIN_MODEL)
        else:
            # Nessun chunk rilevante: domanda generica a Ollama
            prompt = (
                INITIAL_PROMPT + "\n\n"
                + shortTermMemory.get_recent_messages(MAX_TURNS)
                + f"User: {user_input}\nAssistant:\n"
            )
            response = ollama.query_ollama_streaming(prompt, MAIN_MODEL)

        if TEXT_TO_SPEECH:
            textSpeech.text_to_speech_locally(response)
        print(response)

        # Aggiorna la memoria breve
        shortTermMemory.update_history(user_input, response, MAX_TURNS, SUMMARIZER_MODEL)

if __name__ == "__main__":
    main()