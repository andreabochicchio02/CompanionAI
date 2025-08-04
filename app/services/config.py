from enum import Enum, auto
from sentence_transformers import SentenceTransformer

EVENTS_PATH = "app/events.json"

SERVER_LOG = "app/services/server_log.txt"
CONVERSATION_LOG_FOLD = "app/services/conversation_log.txt"

CHATS_FILE = 'app/chats.json'

MAIN_MODEL = "llama3.2:3b"
SUMMARIZER_MODEL = "gemma3:1b"

# ----- RAG ----- #
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L12-v2")
#EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")
DOCUMENT_PATHS = ["app/document.txt"] #* elenco dei file
TOP_K = 3
MIN_SCORE = 0.2

QDRANT_DB_PATH = "app/qdrant_storage"

# ----- SHORT TERM MEMORY ----- #
MAX_TURNS = 5

# ----- PROACTIVE LLM ----- #
ACTIVITIES = [
    {"activity": "talk about the past", "selected": False},
    {"activity": "talk about what you ate today", "selected": False},
    {"activity": "talk about your children", "selected": False},
    {"activity": "talk about music", "selected": False},
    {"activity": "talk about sports", "selected": False}
]

SUGGEST_TOPIC_SENTENCES = [
    "Hello! I'm your companion. Would you like to ask me something specific, or would you prefer me to suggest a topic for our conversation?",
    "Hey there! I'm ready to chat. Do you want to ask something specific, or should I propose some conversation ideas?",
    "Hello! I'm at your service. Would you prefer to ask me something directly, or would you like me to offer some conversation starters?",
    "Hey! I'm your companion. Do you want to dive into a specific question, or shall I bring up some ideas to chat about?"
]

class State(Enum):
    START = auto()
    CHOOSING = auto()
    TOPIC = auto()
    CONVERSATION = auto()

# ----- PROMPTS ----- #

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