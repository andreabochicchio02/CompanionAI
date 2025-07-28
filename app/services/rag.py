from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from app.services.utils import append_log

# --- RAG config ---
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
COLLECTION_NAME = "document_chunks"
DOCUMENT_PATH = "document.txt"
TOP_K = 3
MIN_SCORE = 0.1

qdrant_client = None

# Al momento queste variabili non sono usate
#DB_PATH = "qdrant_data"
#EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
#MAX_TOKENS = 500


def initialize_db():
    """
    Initializes the Qdrant database in memory and populates it with chunks from the document.
    """
    global qdrant_client
    try:
        # Prima, prova ad usare il client in-memory (nessun file di lock)
        append_log("Attempting to create in-memory Qdrant client...")
        qdrant_client = QdrantClient(":memory:")
        append_log("Using in-memory Qdrant client")

        # Crea la collezione e riempila
        chunk_list = load_chunks(DOCUMENT_PATH)
        embeddings = compute_embeddings(EMBEDDING_MODEL, chunk_list)

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
        append_log(f"Successfully populated in-memory Qdrant with {len(points)} chunks")
    except FileNotFoundError:
        append_log(f"Error: Document file '{DOCUMENT_PATH}' not found.")
        qdrant_client = None
    except Exception as e:
        append_log(f"Failed to initialize Qdrant client in memory: {e}")
        append_log("Falling back to no RAG mode")
        qdrant_client = None


def load_chunks(file_path):
    """Loads chunks from a text file, splitting by double newlines.
    :param file_path: Path to the text file containing chunks
    :return: List of text chunks
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]

#! potrebbe essere da modificare in base al modello di embedding utilizzato
def compute_embeddings(model, chunk_list):
    """ Computes embeddings for a list of text chunks using the specified model.
    :param model: The embedding model to use (e.g., SentenceTransformer)
    """
    #return model.encode(chunk_list)['dense_vecs'] #bgem
    return model.encode(chunk_list) # sentence-transformers

def init_qdrant(embeddings, chunk_list, path, collection_name):
    """ Initializes the Qdrant client and creates a collection with the provided embeddings and chunks.
    :param embeddings: List of embeddings for the chunks
    :param chunk_list: List of text chunks corresponding to the embeddings
    :param path: Path to the Qdrant database
    """
    import os
    # Assicuriamoci che la directory esista
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        
    try:
        qdrant_client = QdrantClient(path=path)
        # Usa la nuova logica consigliata da Qdrant
        if not qdrant_client.collection_exists(collection_name=collection_name):
            print(f"Creating new collection: {collection_name}")
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
            )
        else:
            print(f"Collection {collection_name} already exists. Recreating...")
            qdrant_client.delete_collection(collection_name=collection_name)
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
            )
    except Exception as e:
        print(f"Error initializing Qdrant: {e}")
        raise
    points = [
        PointStruct(id=i, vector=embedding, payload={"chunk": chunk})
        for i, (embedding, chunk) in enumerate(zip(embeddings, chunk_list))
    ]
    qdrant_client.upsert(collection_name=collection_name, points=points)
    return qdrant_client

def search_chunks(qdrant_client, collection_name, query_embedding, top_k, min_score):
    """Searches for relevant chunks in the Qdrant collection based on the query embedding.
    :param qdrant_client: The Qdrant client instance
    :param collection_name: Name of the collection to search in
    :param query_embedding: The embedding of the query to search for
    :param top_k: Number of top results to return
    """
    search_result = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
    )
    selected_chunks = []
    selected_scores = []
    for result in search_result:
        if result.score > min_score:
            selected_chunks.append(result.payload["chunk"])
            selected_scores.append(result.score)
        if len(selected_chunks) == top_k:
            break
    return selected_chunks, selected_scores


# def create_db(embedding_model, file_path, max_tokens, embedding_model_name, collection_name, db_path):
#     chunk_list = load_chunks(file_path)
#     embeddings = compute_embeddings(embedding_model, chunk_list)
#     qdrant_client = init_qdrant(embeddings, chunk_list, db_path, collection_name)
#     return qdrant_client


def get_relevant_chunks(query):
    """Retrieves relevant chunks from the Qdrant collection based on the query.
    :param qdrant_client: The Qdrant client instance
    :param collection_name: Name of the collection to search in
    :param embedding_model: The embedding model to use for the query
    """
    
    print("Sono qui")
    query_embedding = EMBEDDING_MODEL.encode([query])[0]
    
    selected_chunks, selected_scores = search_chunks(qdrant_client, COLLECTION_NAME, query_embedding, TOP_K, MIN_SCORE)

    # Migliorato il prompt del RAG per estrarre meglio le informazioni
    if not selected_chunks:
        return ""
    else:
        formatted_chunks = []
        for i, (chunk, score) in enumerate(zip(selected_chunks, selected_scores)):
            formatted_chunks.append(f"[DOCUMENT EXCERPT {i+1} (relevance: {score:.2f})]:\n{chunk}\n")
        return "\n".join(formatted_chunks)