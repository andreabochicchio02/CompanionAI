import app.services.config as config
import app.services.utils as utils

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, PointIdsList
 
import os, json, hashlib
import time # monitoring file changes

qdrant_client = None

def initialize_db():
    """
    Initializes or updates the Qdrant database incrementally based on file changes.
    """
    global qdrant_client
    try:
        db_path = config.QDRANT_DB_PATH
        utils.append_server_log(f"Attempting to create Qdrant client at path: {db_path}")
        qdrant_client = QdrantClient(path=db_path)
        utils.append_server_log(f"Using Qdrant client at path: {db_path}")

        file_paths = config.DOCUMENT_PATHS

        # Controlla se la collezione esiste, se no creala
        if not qdrant_client.collection_exists(collection_name=config.COLLECTION_NAME):
            utils.append_server_log(f"Collection {config.COLLECTION_NAME} does not exist. Creating it...")
            # Crea la collezione con dimensioni corrette
            embedding_dim = config.EMBEDDING_MODEL.get_sentence_embedding_dimension()
            qdrant_client.create_collection(
                collection_name=config.COLLECTION_NAME,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )

        # Controlla se ci sono file modificati
        if have_files_changed(file_paths):
            utils.append_server_log("Documents have changed. Updating database...")
            
            for file_path in file_paths:
                if has_file_changed(file_path):
                    utils.append_server_log(f"File {file_path} has changed. Updating related chunks...")

                    # Carica i nuovi chunk e calcola gli embeddings
                    chunk_list = load_chunks(file_path)
                    embeddings = compute_embeddings(config.EMBEDDING_MODEL, chunk_list)

                    # Usa ID deterministici basati su file e indice per evitare duplicati
                    points = [
                        PointStruct(
                            id=hash(f"{file_path}_{i}") % (2**31),  # ID deterministico
                            vector=embedding,
                            payload={"chunk": chunk, "file": file_path, "chunk_id": i}
                        )
                        for i, (embedding, chunk) in enumerate(zip(embeddings, chunk_list))
                    ]
                    # Upsert sostituisce automaticamente i punti con gli stessi ID
                    qdrant_client.upsert(collection_name=config.COLLECTION_NAME, points=points)
                    utils.append_server_log(f"Updated {len(points)} chunks for file {file_path}")
        else:
            utils.append_server_log("No changes detected in documents. Skipping update.")

        # Salva gli hash dei file
        save_file_hash(file_paths)
        
    except FileNotFoundError as e:
        utils.append_server_log(f"Error: {e}")
        qdrant_client = None
    except Exception as e:
        utils.append_server_log(f"Failed to initialize Qdrant client: {e}")
        qdrant_client = None

# def reset_collection():
#     """
#     Deletes and recreates the Qdrant collection.
#     """
#     global qdrant_client
#     try:
#         if qdrant_client.collection_exists(collection_name=config.COLLECTION_NAME):
#             utils.append_server_log(f"Deleting collection: {config.COLLECTION_NAME}")
#             qdrant_client.delete_collection(collection_name=config.COLLECTION_NAME)
        
#         utils.append_server_log(f"Recreating collection: {config.COLLECTION_NAME}")
#         qdrant_client.create_collection(
#             collection_name=config.COLLECTION_NAME,
#             vectors_config=VectorParams(size=config.EMBEDDING_DIM, distance=Distance.COSINE),
#         )
#     except Exception as e:
#         utils.append_server_log(f"Failed to reset collection: {e}")


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

# def init_qdrant(embeddings, chunk_list, path, collection_name):
#     """ Initializes the Qdrant client and creates a collection with the provided embeddings and chunks.
#     :param embeddings: List of embeddings for the chunks
#     :param chunk_list: List of text chunks corresponding to the embeddings
#     :param path: Path to the Qdrant database
#     """
#     import os
#     # Assicuriamoci che la directory esista
#     if not os.path.exists(path):
#         os.makedirs(path, exist_ok=True)
        
#     try:
#         qdrant_client = QdrantClient(path=path)
#         # Usa la nuova logica consigliata da Qdrant
#         if not qdrant_client.collection_exists(collection_name=collection_name):
#             print(f"Creating new collection: {collection_name}")
#             qdrant_client.create_collection(
#                 collection_name=collection_name,
#                 vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
#             )
#         else:
#             print(f"Collection {collection_name} already exists. Recreating...")
#             qdrant_client.delete_collection(collection_name=collection_name)
#             qdrant_client.create_collection(
#                 collection_name=collection_name,
#                 vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
#             )
#     except Exception as e:
#         print(f"Error initializing Qdrant: {e}")
#         raise
#     points = [
#         PointStruct(id=i, vector=embedding, payload={"chunk": chunk})
#         for i, (embedding, chunk) in enumerate(zip(embeddings, chunk_list))
#     ]
#     qdrant_client.upsert(collection_name=collection_name, points=points)
#     return qdrant_client

def search_chunks(qdrant_client, collection_name, query_embedding, top_k, min_score):
    """Searches for relevant chunks in the Qdrant collection based on the query embedding."""
    search_result = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k * 2,  # Recupera più risultati per filtrare
        with_payload=True,
    )
    filtered_results = [
        result for result in search_result if result.score > min_score
    ]
    sorted_results = sorted(filtered_results, key=lambda x: x.score, reverse=True)
    
    # Restituisci chunk e scores separatamente
    chunks = [result.payload["chunk"] for result in sorted_results[:top_k]]
    scores = [result.score for result in sorted_results[:top_k]]
    return chunks, scores


def get_relevant_chunks(query):
    """Retrieves relevant chunks from the Qdrant collection based on the query."""
    try:
        if not qdrant_client:
            utils.append_server_log("Qdrant client not available, returning empty chunks")
            return ""
            
        query_embedding = config.EMBEDDING_MODEL.encode([query])[0]
        
        selected_chunks, selected_scores = search_chunks(qdrant_client, config.COLLECTION_NAME, query_embedding, config.TOP_K, config.MIN_SCORE)

        # Migliorato il prompt del RAG per estrarre meglio le informazioni
        if not selected_chunks:
            return ""
        else:
            formatted_chunks = []
            for i, (chunk, score) in enumerate(zip(selected_chunks, selected_scores)):
                formatted_chunks.append(f"[DOCUMENT EXCERPT {i+1} (relevance: {score:.2f})]:\n{chunk}\n")
            return "\n".join(formatted_chunks)
    except Exception as e:
        utils.append_server_log(f"Error retrieving chunks: {e}")
        return ""
    
#----- DETECT CHANGES IN FILES---------

def has_file_changed(file_path, hash_store_path="file_hashes.json"):
    """Verifica se un singolo file è stato modificato confrontando il suo hash con quello salvato."""
    try:
        with open(hash_store_path, 'r', encoding='utf-8') as f:
            hashes = json.load(f)
    except FileNotFoundError:
        return True  # Se il file di hash non esiste, considera il file come modificato

    current_hash = calculate_file_hash(file_path)
    saved_hash = hashes.get(file_path)
    return current_hash != saved_hash  # Restituisce True se l'hash è diverso
    
def have_files_changed(file_paths, hash_store_path="file_hashes.json"):
    """Verifica se uno o più file sono stati modificati confrontando i loro hash con quelli salvati."""
    try:
        with open(hash_store_path, 'r', encoding='utf-8') as f:
            hashes = json.load(f)
    except FileNotFoundError:
        return True  # Se il file di hash non esiste, considera i file come modificati

    for file_path in file_paths:
        current_hash = calculate_file_hash(file_path)
        saved_hash = hashes.get(file_path)
        if current_hash != saved_hash:
            return True  # Almeno un file è stato modificato

    return False  # Nessun file è stato modificato

def calculate_file_hash(file_path):
    """Calculate the SHA256 hash of a file in order to detect changes."""
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        return hashlib.sha256(file_data).hexdigest()
    except FileNotFoundError:
        return None
    
def save_file_hash(file_paths, hash_store_path="file_hashes.json"):
    """Salva gli hash di più file in un file JSON."""
    try:
        if not os.path.exists(hash_store_path):
            hashes = {}
        else:
            with open(hash_store_path, 'r', encoding='utf-8') as f:
                hashes = json.load(f)

        for file_path in file_paths:
            hash_value = calculate_file_hash(file_path)
            hashes[file_path] = hash_value

        with open(hash_store_path, 'w', encoding='utf-8') as f:
            json.dump(hashes, f, indent=4)
    except Exception as e:
        print(f"Error saving file hashes: {e}")

#! al momento non usato perchè thread disattivato, vedi app.py
def monitor_file_changes(interval=60):
    """Monitora periodicamente i file per rilevare modifiche."""
    while True:
        try:
            file_paths = config.DOCUMENT_PATHS  # Lista di file da monitorare
            if have_files_changed(file_paths):
                utils.append_server_log("Detected changes in documents. Updating database...")
                initialize_db()  # Aggiorna il database
            else:
                utils.append_server_log("No changes detected in documents.")
        except Exception as e:
            utils.append_server_log(f"Error during file monitoring: {e}")
        time.sleep(interval)  # Intervallo di controllo (es. ogni 60 secondi)

