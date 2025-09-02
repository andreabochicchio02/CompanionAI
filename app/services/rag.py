import app.services.config as config
import app.services.utils as utils
import app.services.ollama as ollama

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import time
 
import os, json, hashlib

qdrant_client = None

def deterministic_id(file_path: str, i: int) -> int:
    """
    Genera un ID deterministico a 64 bit a partire dal file path e dall'indice del chunk.
    Così gli stessi chunk avranno sempre lo stesso ID, anche tra sessioni diverse.
    """
    key = f"{file_path}_{i}".encode("utf-8")
    return int.from_bytes(hashlib.md5(key).digest()[:8], "big")

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

        # Main collection for files
        if not qdrant_client.collection_exists(collection_name=config.DOCUMENTS_COLLECTION_NAME):
            utils.append_server_log(f"Collection {config.DOCUMENTS_COLLECTION_NAME} does not exist. Creating it...")
            
            embedding_dim = config.EMBEDDING_MODEL.get_sentence_embedding_dimension()
            
            qdrant_client.create_collection(
                collection_name=config.DOCUMENTS_COLLECTION_NAME,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )

        # memory collection for relevant information
        if not qdrant_client.collection_exists(collection_name=config.MEMORY_COLLECTION_NAME):
            utils.append_server_log(f"Collection {config.MEMORY_COLLECTION_NAME} does not exist. Creating it...")
            embedding_dim = config.EMBEDDING_MODEL.get_sentence_embedding_dimension()
            qdrant_client.create_collection(
                collection_name=config.MEMORY_COLLECTION_NAME,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )

        # Check if files have changed
        if have_files_changed(file_paths): # fast check
            utils.append_server_log("Documents have changed. Updating database...")
            
            for file_path in file_paths:
                if has_file_changed(file_path): # detailed check
                    utils.append_server_log(f"File {file_path} has changed. Updating related chunks...")

                    chunk_list = load_chunks(file_path)
                    embeddings = compute_embeddings(config.EMBEDDING_MODEL, chunk_list)

                    # Use deterministic IDs based on file and index to avoid duplicates
                    points = [
                        PointStruct(
                            id=deterministic_id(file_path, i),
                            vector=embedding,
                            payload={"chunk": chunk, "file": file_path, "chunk_id": i}
                        )
                        for i, (embedding, chunk) in enumerate(zip(embeddings, chunk_list))
                    ]
                    # Upsert substitutes points with the same IDs automatically
                    qdrant_client.upsert(collection_name=config.DOCUMENTS_COLLECTION_NAME, points=points, wait=True)
                    utils.append_server_log(f"Updated {len(points)} chunks for file {file_path}")
        else:
            utils.append_server_log("No changes detected in documents. Skipping update.")

        update_file_hashes()
        
    except FileNotFoundError as e:
        utils.append_server_log(f"Error: {e}")
        qdrant_client = None
    except Exception as e:
        utils.append_server_log(f"Failed to initialize Qdrant client: {e}")
        qdrant_client = None


def create_structured_info(input_file="app/resources/personal_info.txt", output_file="app/resources/structured_info.txt"):
    """
    Reads paragraphs from input_file, sends them to the LLM for structuring,
    and saves the structured output into a text file.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        raw_paragraphs = content.strip().split('\n\n\n')
        paragraphs = []

        for p in raw_paragraphs:
            lines = p.strip().split('\n', 1)
            title = lines[0].strip()
            body = lines[1].strip()
            paragraphs.append({
                "title": title,
                "content": body
            })
    except Exception as e:
        raise RuntimeError(f"Error while reading the file {input_file}: {e}")

    structured_results = []

    for idx, p in enumerate(paragraphs, 1):
        title = p["title"]
        content = p["content"]

        prompt = f"""
            Create a structured summary that extracts the fundamental concepts from the following text.
            Rules:
            - Each entry must be a key-value pair in the form "- Key: Value".
            - Output must contain ONLY structured information, no explanations or commentary.

            Example:
            Full Name: Jonathan Andrews
            Date of Birth: 16 February 1955
            Birth Place: Bath, England

            Here is the text: {content}

            Return ONLY structured information as simple key-value pairs.
        """

        response_text = ollama.query_ollama_no_stream(prompt, config.MAIN_MODEL)
        structured_results.append(f"### {title}\n{response_text}\n")


    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(structured_results))

    return output_file



def load_chunks(file_path):
    """Loads chunks from a text file, splitting by double newlines.
    :param file_path: Path to the text file containing chunks
    :return: List of text chunks
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]

def compute_embeddings(model, chunk_list):
    """ Computes embeddings for a list of text chunks using the specified model.
    :param model: The embedding model to use (e.g., SentenceTransformer)
    """
    return model.encode(chunk_list) # sentence-transformers

def search_chunks(qdrant_client, collection_name, query_embedding, top_k, min_score):
    """Searches for relevant chunks in the Qdrant collection based on the query embedding."""
    search_result = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k * 2,
        with_payload=True,
    )
    filtered_results = [
        result for result in search_result if result.score > min_score
    ]
    sorted_results = sorted(filtered_results, key=lambda x: x.score, reverse=True)
    
    if collection_name == config.MEMORY_COLLECTION_NAME:
        chunks = [result.payload.get("rewrited_info", str(result.payload)) for result in sorted_results[:top_k]]
    else:
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
        
        selected_chunks, selected_scores = search_chunks(qdrant_client, config.DOCUMENTS_COLLECTION_NAME, query_embedding, config.TOP_K, config.MIN_SCORE)

        # Migliorato il prompt del RAG per estrarre meglio le informazioni
        if not selected_chunks:
            return ""
        else:
            formatted_chunks = []
            for i, (chunk, score) in enumerate(zip(selected_chunks, selected_scores)):
                formatted_chunks.append(f"[(relevance: {score:.2f})]:\n{chunk}\n")
            return "\n".join(formatted_chunks)
    except Exception as e:
        utils.append_server_log(f"Error retrieving chunks: {e}")
        return ""

def get_relevant_memory(query):
    """Retrieves relevant chunks from the Qdrant collection based on the query."""
    try:
        if not qdrant_client:
            utils.append_server_log("Qdrant client not available, returning empty chunks")
            return ""
            
        query_embedding = config.EMBEDDING_MODEL.encode([query])[0]
        
        # Recupera anche i payload completi per formattazione avanzata
        search_result = qdrant_client.search(
            collection_name=config.MEMORY_COLLECTION_NAME,
            query_vector=query_embedding,
            limit=config.TOP_K * 2,
            with_payload=True,
        )
        filtered_results = [r for r in search_result if r.score > config.MIN_SCORE]
        sorted_results = sorted(filtered_results, key=lambda x: x.score, reverse=True)
        seen = set()
        formatted_chunks = []
        count = 0
        for result in sorted_results:
            payload = result.payload
            
            text = payload.get("rewrited_info", str(payload))
            if text in seen:
                continue
            seen.add(text)
            count += 1

            formatted_chunks.append(f"[Memory EXCERPT {count} (relevance: {result.score:.2f})]:\n{text}\n")
            if count >= config.TOP_K:
                break
        if not formatted_chunks:
            return ""
        return "\n".join(formatted_chunks)
    except Exception as e:
        utils.append_server_log(f"Error retrieving memory: {e}")
        return ""
    
#----- DETECT CHANGES IN FILES---------

def has_file_changed(file_path, hash_store_path="app/log/file_hashes.json"):
    """Check if a file has changed by comparing its current hash with the saved hash."""
    try:
        with open(hash_store_path, 'r', encoding='utf-8') as f:
            hashes = json.load(f)
    except FileNotFoundError:
        return True  # if the hash file doesn't exist, consider the file changed

    current_hash = calculate_file_hash(file_path)
    saved_hash = hashes.get(file_path)
    return current_hash != saved_hash  # Return True if the file has changed
    
def have_files_changed(file_paths, hash_store_path="app/log/file_hashes.json"):
    """Check if one or more files have changed by comparing their hashes with the saved hashes."""
    try:
        with open(hash_store_path, 'r', encoding='utf-8') as f:
            hashes = json.load(f)
    except FileNotFoundError:
        return True

    for file_path in file_paths:
        current_hash = calculate_file_hash(file_path)
        saved_hash = hashes.get(file_path)
        if current_hash != saved_hash:
            return True  # if any file has changed

    return False  # if no files have changed

def calculate_file_hash(file_path):
    """Calculate the SHA256 hash of a file in order to detect changes."""
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        return hashlib.sha256(file_data).hexdigest()
    except FileNotFoundError:
        return None
    
def save_file_hash(file_paths, hash_store_path="app/log/file_hashes.json"):
    """Save the hashes of the specified files to a JSON file."""
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

def update_file_hashes():
    """
    Aggiorna i file_hashes.json con i nuovi hash dei file.
    """
    save_file_hash(config.DOCUMENT_PATHS)
    utils.append_server_log("File hashes updated for personal_info.txt and structured_info.txt")
