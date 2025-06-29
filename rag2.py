from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from FlagEmbedding import BGEM3FlagModel
from sentence_transformers import SentenceTransformer
import requests

#! potrebbe essere da modificare in base al modello di embedding utilizzato
def load_chunks(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]

def compute_embeddings(model, chunk_list):
    #return model.encode(chunk_list)['dense_vecs'] #bgem
    return model.encode(chunk_list) # sentence-transformers

def init_qdrant(embeddings, chunk_list, path="qdrant_data", collection_name="document_chunks"):
    qdrant_client = QdrantClient(path=path)
    # Usa la nuova logica consigliata da Qdrant
    if not qdrant_client.collection_exists(collection_name=collection_name):
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
        )
    else:
        qdrant_client.delete_collection(collection_name=collection_name)
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
        )
    points = [
        PointStruct(id=i, vector=embedding, payload={"chunk": chunk})
        for i, (embedding, chunk) in enumerate(zip(embeddings, chunk_list))
    ]
    qdrant_client.upsert(collection_name=collection_name, points=points)
    return qdrant_client

def query_ollama(prompt, model="llama3.2:3b"):
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print("\nRisposta:\n", data.get("response", "Nessuna risposta"))
    except Exception as e:
        print("Errore nella richiesta a Ollama:", e)

def search_chunks(qdrant_client, collection_name, query_embedding, chunk_list, top_k=3, min_score=0.4):
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

def main():
    #model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    chunk_list = load_chunks('document.txt')
    embeddings = compute_embeddings(model, chunk_list)
    qdrant_client = init_qdrant(embeddings, chunk_list)
    collection_name = "document_chunks"
    while True:
        query = input("\nInserisci la tua domanda (o 'exit' per uscire): ")
        if query.lower() in ['exit', 'esci']:
            print("Uscita...")
            break
        #query_embedding = model.encode([query])['dense_vecs'][0] # bgem
        query_embedding = model.encode([query])[0] # sentence-transformers
        selected_chunks, selected_scores = search_chunks(qdrant_client, collection_name, query_embedding, chunk_list)
        print("\nChunk selezionati e similarità:")
        for i, (chunk, score) in enumerate(zip(selected_chunks, selected_scores), 1):
            print(f"{i}) Similarità: {score:.4f}\n{chunk}\n")
        if not selected_chunks:
            prompt = f"Domanda: {query}\nRisposta:"
        else:
            context = "\n---\n".join(selected_chunks)
            prompt = (
                f"Context (use only if it's helpful; otherwise, ignore it):\n"
                f"{context}\n\nDomanda: {query}\nRisposta:"
            )
        query_ollama(prompt)

if __name__ == "__main__":
    main()
