import json
from enum import Enum, auto
from sentence_transformers import SentenceTransformer

# ----- PATHS ----- #
EVENTS_PATH = "app/resources/events.json"
SERVER_LOG = "app/log/server_log.txt"
MEMORY_LOG = "app/log/memory_log.txt"
CONVERSATION_LOG_FOLD = "app/log/conversation_log.txt"
CHATS_FILE = 'app/resources/chats.json'
DOCUMENT_PATHS = ["app/resources/personal_info.txt"]
QDRANT_DB_PATH = "app/qdrant_storage"
DOCUMENTS_COLLECTION_NAME = "documents"
MEMORY_COLLECTION_NAME = "memory"

CONFIG_PATH = "app/services/config.json"

# ----- LOAD GENERAL CONFIG ----- #
def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()

USER_RELIABLE = config.get("USER_RELIABLE", True)
MAIN_MODEL = config.get("MAIN_MODEL")
SUMMARIZER_MODEL = config.get("SUMMARIZER_MODEL")
TOP_K = config.get("TOP_K", 3)
MIN_SCORE = config.get("MIN_SCORE", 0.2)
MAX_TURNS = config.get("MAX_TURNS", 5)
SUGGEST_TOPIC_SENTENCES = config.get("SUGGEST_TOPIC_SENTENCES", [])
INITIAL_PROMPT = config.get("INITIAL_PROMPT", "")

# ----- RAG EMBEDDING MODEL ----- #
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L12-v2")

# ----- STATE MACHINE ----- #
class State(Enum):
    START = auto()
    CHOOSING = auto()
    TOPIC = auto()
    CONVERSATION = auto()

# ----- FUNCTION TO UPDATE USER_RELIABLE ----- #
def set_user_reliable(value: bool):
    global config, USER_RELIABLE
    config["USER_RELIABLE"] = value
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    USER_RELIABLE = value


ACTIVITIES = [
    {"activity": "Can you tell me something interesting from your past?", "selected": False},
    {"activity": "What did you eat today?", "selected": False},
    {"activity": "Can you tell me about your children?", "selected": False},
    {"activity": "What kind of music do you enjoy?", "selected": False},
    {"activity": "Do you follow any sports?", "selected": False}
]