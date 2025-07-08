import requests
import json
import sys

def query_ollama_no_stream(prompt, model):
    """
    Send a prompt to Ollama API and get the full response without streaming.
    Returns the full generated text as a string.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to Ollama. Is it running?")
        return ""
    except Exception as e:
        print(f"Unexpected error: {e}")
        return ""
    
def query_ollama_streaming(prompt, model):
    """
    Send a prompt to Ollama API and stream the response in real-time.
    Prints the output as it is received and returns the full text.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True
    }
    print("\nAnswer: ", end="")
    full_response = ""
    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        sys.stdout.write(chunk['response'])
                        sys.stdout.flush()
                        full_response += chunk['response']
                    if chunk.get('done', False):
                        print()
                        break
        return full_response.strip()
    except requests.exceptions.ConnectionError:
        print("\nError: Cannot connect to Ollama. Is it running?")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

def preload_model(model_name):
    """
    Send an empty prompt to the model just to preload it into memory.
    This function doesn't do anything useful except warming up the model.
    """
    try:
        prompt = ""
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"[DEBUG] Model '{model_name}' preloaded successfully.")
    except Exception as e:
        print(f"[DEBUG] Failed to preload model '{model_name}': {e}")