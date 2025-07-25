from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from FlagEmbedding import BGEM3FlagModel
from transformers import AutoTokenizer

#! potrebbe essere da modificare in base al modello di embedding utilizzato
def load_chunks(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]

def compute_embeddings(model, chunk_list):
    #return model.encode(chunk_list)['dense_vecs'] #bgem
    return model.encode(chunk_list) # sentence-transformers

def init_qdrant(embeddings, chunk_list, path, collection_name):
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


def create_db(embedding_model, file_path, max_tokens, embedding_model_name, collection_name, db_path):
    chunk_list = load_chunks(file_path)
    embeddings = compute_embeddings(embedding_model, chunk_list)
    qdrant_client = init_qdrant(embeddings, chunk_list, db_path, collection_name)
    return qdrant_client


def get_relevant_chunks(qdrant_client, collection_name, embedding_model, query, top_k, min_score):
    
    query_embedding = embedding_model.encode([query])[0]
    
    selected_chunks, selected_scores = search_chunks(qdrant_client, collection_name, query_embedding, top_k, min_score)

    # Migliorato il prompt del RAG per estrarre meglio le informazioni
    if not selected_chunks:
        return ""
    else:
        formatted_chunks = []
        for i, (chunk, score) in enumerate(zip(selected_chunks, selected_scores)):
            formatted_chunks.append(f"[DOCUMENT EXCERPT {i+1} (relevance: {score:.2f})]:\n{chunk}\n")
        return "\n".join(formatted_chunks)

def format_rag_prompt(initial_prompt, relevant_chunks, recent_messages, user_prompt):
    """
    Format a complete prompt with RAG information for the LLM.
    
    Args:
        initial_prompt: Base system prompt
        relevant_chunks: Document chunks from RAG
        recent_messages: Recent conversation history
        user_prompt: Current user question
        
    Returns:
        Formatted prompt for the model
    """
    if relevant_chunks.strip():
        return (
            initial_prompt + "\n\n"
            + "IMPORTANT CONTEXT FROM DOCUMENT (use this information to answer accurately):\n" 
            + relevant_chunks
            + "\nRemember to incorporate the above document information in your response when relevant.\n"
            + recent_messages
            + f"User: {user_prompt}\n"
        )
    else:
        return (
            initial_prompt + "\n\n"
            + recent_messages
            + f"User: {user_prompt}\n"
        )