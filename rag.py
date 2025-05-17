import os
import requests
import json
import sys
import numpy as np

from langchain.text_splitter import CharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader

# Soglia di similarità sotto la quale non utilizziamo il contesto RAG
SIMILARITY_THRESHOLD = 1.1

def build_rag_index(document_path: str, index_path: str = "faiss_index"):
    # Carica il documento
    loader = TextLoader(document_path, encoding="utf-8")
    docs = loader.load()

    # Splitting in chunk per embeddings
    splitter = CharacterTextSplitter(chunk_size=50, chunk_overlap=20)
    chunks = splitter.split_documents(docs)

    # Embeddings locali
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

    # Costruzione indice FAISS
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(index_path)
    print(f"Index built and saved to '{index_path}'")

    return vector_store

def load_rag_index(index_path: str = "faiss_index"):
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_store = FAISS.load_local(
        index_path, embeddings, allow_dangerous_deserialization=True
    )
    return vector_store

def query_ollama_streaming(prompt: str, model: str = "llama3.2:3b"):
    """
    Query the local Ollama API in streaming mode e printa la risposta.
    """
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": True}

    print("\nDomanda:", prompt)
    print("\nRisposta:")

    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        sys.stdout.write(chunk['response'])
                        sys.stdout.flush()
                    if chunk.get('done', False):
                        print("\n\nStatistiche:")
                        if 'eval_count' in chunk:
                            print(f"Token generati: {chunk['eval_count']}")
                        if 'total_duration' in chunk:
                            print(f"Tempo totale: {chunk['total_duration']/1e9:.2f} secondi")
    except requests.exceptions.ConnectionError:
        print("Errore: impossibile connettersi al server Ollama.")
        print("Assicurati che Ollama sia in esecuzione con il comando 'ollama serve'.")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")

def ask_question(vector_store, question: str, model_name: str = "llama3.2:3b"):
    # 1) Embedding della domanda
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    q_emb = embeddings.embed_query(question)

    # 2) Ricerca nel FAISS index raw
    #    - D: array delle similarità (o distanze, a seconda di come è stato costruito)
    #    - I: array degli indici dei vettori/documents
    faiss_index = vector_store.index
    D, I = faiss_index.search(np.array([q_emb], dtype="float32"), k=3)

    # 3) Estrai documenti e scores
    #    vector_store.index_to_docstore_id: mappa indice FAISS → docstore_id
    #    vector_store.docstore._dict       : mappa docstore_id → Document
    docs_and_scores = []
    for score, idx in zip(D[0], I[0]):
        doc_id = vector_store.index_to_docstore_id[idx]
        doc = vector_store.docstore._dict[doc_id]
        docs_and_scores.append((doc, float(score)))

    # 4) Miglior score e branching
    best_score = max(score for _, score in docs_and_scores)

    print(f"\n\n\nSCOREEEEE: {best_score}\n\n\n\n")

    if best_score < SIMILARITY_THRESHOLD:
        # “LLM puro”
        prompt = f"Question: {question}\nAnswer:"
    else:
        # “RAG contestualizzato”
        relevant_texts = [doc.page_content for doc, _ in docs_and_scores]
        context = "\n---\n".join(relevant_texts)
        prompt = (
            f"Context (use only if it's helpful; otherwise, ignore it):\n"
            f"{context}\n\n"
            f"Question: {question}\n"
            f"Answer:"
        )

    # 5) Streaming risposta
    query_ollama_streaming(prompt, model_name)

if __name__ == "__main__":
    DOC_PATH = "document.txt"
    INDEX_PATH = "faiss_index"

    # Costruisci o carica l’indice
    if not os.path.exists(INDEX_PATH):
        vs = build_rag_index(DOC_PATH, INDEX_PATH)
    else:
        vs = load_rag_index(INDEX_PATH)

    # Verifica modelli disponibili
    try:
        model_check = requests.get("http://localhost:11434/api/tags")
        models = json.loads(model_check.text).get("models", [])
        if not any(m.get("name") == "llama3.2:3b" for m in models):
            print("Il modello llama3.2:3b non sembra essere scaricato. Esegui: ollama pull llama3.2:3b")
    except Exception:
        print("Impossibile verificare i modelli disponibili. Assicurati che Ollama sia in esecuzione.")

    # Loop interattivo
    while True:
        user_q = input("\nInserisci la tua domanda (o 'exit' per uscire): ")
        if user_q.lower() in ['exit', 'esci']:
            print("Uscita...")
            break
        ask_question(vs, user_q)
