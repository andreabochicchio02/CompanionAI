# METODO 1: SEMPLICE, MA NON SUPPORTA STRAMING, DIPENDE DALLA LIBRERIA OLLAMA, 
""" from ollama import chat
from ollama import ChatResponse

response: ChatResponse = chat(model='llama3.2:3b', messages=[
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
])
print(response['message']['content'])
# or access fields directly from the response object
print(response.message.content) """



# METODO 2: SEMPLICE, SUPPORTA STRAMING, MA DIPENDE DALLA LIBRERIA OLLAMA,
"""
from ollama import chat

stream = chat(
    model='llama3.2:3b',
    messages=[{'role': 'user', 'content': 'Why is the sky blue?'}],
    stream=True,
)

for chunk in stream:
  print(chunk['message']['content'], end='', flush=True)
  """


# METODO 3: PIENO CONTROLLO USANDO HTTP, MA DOBBIAMO NOI GESTIRE ERRORI ECC.. E NON INTERATTIVO
"""
import requests

resp = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2:3b",
        "prompt": "Why is the sky blue?",
        "stream": False       # disable streaming so we get one clean JSON object
    }
)

print(resp.json()["response"])
"""


# METODO 4: HTTP, STRAMING E CON GESTIONE ERRORI
import requests
import json
import sys

def query_ollama_streaming(prompt, model="llama3.2:3b"):

    # Endpoint Ollama per la generazione di testo
    url = "http://localhost:11434/api/generate"
    
    # Configurazione della richiesta
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True 
    }
    
    print("\nDomanda:", prompt)
    print("\nRisposta:")
    
    try:
        # Esegui la richiesta in streaming
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()  # Verifica eventuali errori HTTP
            
            # Processa la risposta in streaming riga per riga
            for line in response.iter_lines():
                if line:
                    # Decodifica la risposta JSON
                    chunk = json.loads(line)
                    
                    # Stampa il testo in streaming
                    if 'response' in chunk:
                        sys.stdout.write(chunk['response'])
                        sys.stdout.flush()
                    
                    # Controlla se è l'ultimo chunk
                    if chunk.get('done', False):
                        # Stampa statistiche finali
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

if __name__ == "__main__":
    # Verifica se il modello è già scaricato
    try:
        model_check = requests.get("http://localhost:11434/api/tags")
        models = json.loads(model_check.text)["models"]
        
        if not any(model["name"] == "llama3.2:3b" for model in models):
            print("Il modello llama3.2:3b non sembra essere scaricato.")
            print("Per scaricarlo esegui prima: ollama pull llama3.2:3b")
    except:
        print("Impossibile verificare i modelli disponibili.")
        print("Assicurati che Ollama sia in esecuzione.")
    
    # Richiedi l'input dell'utente
    prompt = input("Inserisci la tua domanda: ")
    
    # Esegui la query
    query_ollama_streaming(prompt)
