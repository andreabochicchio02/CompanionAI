import requests
import json
import sys
import random

activities = [
    "Talk about the past",
    "Talk about what you ate today",
    "Talk about your children",
    "Talk about music",
    "Talk about sports"
]

def query_ollama_streaming(prompt, model="llama3.2:3b"):
    # Endpoint Ollama per la generazione di testo
    url = "http://localhost:11434/api/generate"
    
    # Configurazione della richiesta
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True 
    }
    
    # print("Question:", prompt)
    print("\nAnswer:")
    
    try:
        # Esegui la richiesta in streaming
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()  # Verifica eventuali errori HTTP
            
            # Processa la risposta in streaming riga per riga
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    
                    if 'response' in chunk:
                        sys.stdout.write(chunk['response'])
                        sys.stdout.flush()
    
    except requests.exceptions.ConnectionError:
        print("Error: unable to connect to the Ollama server.")
        print("Ensure Ollama is running with the command 'ollama serve'.")
    except Exception as e:
        print(f"An error occurred: {e}")

def is_affirmative_response(user_response, model="llama3.2:3b"):

    url = "http://localhost:11434/api/generate"
    prompt = (
        f"The user responded: '{user_response}'. "
        "Does this response indicate they want to participate in the proposed activity? "
        "Answer only with 'YES' or 'NO'."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        answer = data.get('response', '').strip().upper()
        return answer.startswith("YES")
    except Exception as e:
        print(f"Error determining response: {e}")
        return False

def wants_to_continue(user_response, model="llama3.2:3b"):
    """
    Use the LLM to determine if the user wants to continue the conversation.
    Returns True if they want to continue, False otherwise.
    """
    url = "http://localhost:11434/api/generate"
    prompt = (
        f"The user said: '{user_response}'. "
        "Do they want to continue talking? Answer only with 'YES' or 'NO'."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        answer = data.get('response', '').strip().upper()
        return answer.startswith("YES")
    except Exception as e:
        print(f"Error determining response: {e}")
        return False

def evaluate_response_relevance(question, user_response, current_topic, model="llama3.2:3b"):
    """
    Evaluate if the user's response is relevant to the current topic and question.
    Returns a dictionary with suggested action.
    """
    url = "http://localhost:11434/api/generate"
    prompt = (
        f"Question: '{question}'\n"
        f"Topic: '{current_topic}'\n"
        f"User response: '{user_response}'\n\n"
        f"Based on the user's response, do they want to:\n"
        f"1. CONTINUE_TOPIC - continue talking about this topic\n"
        f"2. CHANGE_TOPIC - talk about something else\n"
        f"3. END_CONVERSATION - stop the conversation\n\n"
        f"Answer with only: CONTINUE_TOPIC, CHANGE_TOPIC, or END_CONVERSATION"
    )
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        answer = data.get('response', '').strip().upper()
        
        # Simple parsing of the response
        if "CONTINUE_TOPIC" in answer:
            return {"action": "CONTINUE_TOPIC", "reason": "User wants to continue"}
        elif "CHANGE_TOPIC" in answer:
            return {"action": "CHANGE_TOPIC", "reason": "User wants to change topic"}
        elif "END_CONVERSATION" in answer:
            return {"action": "END_CONVERSATION", "reason": "User wants to stop"}
        else:
            return {"action": "CONTINUE_TOPIC", "reason": "Unclear response, defaulting to continue"}
                
    except Exception as e:
        print(f"Error evaluating response relevance: {e}")
        return {"action": "CONTINUE_TOPIC", "reason": "Error occurred, defaulting to continue"}

if __name__ == "__main__":
    remaining_activities = activities.copy()
    conversation_history = []
    current_activity = None
    current_prompt = None
    
    
    while True:
        # If we don't have a current activity, suggest one
        if current_activity is None:
            if remaining_activities:
                activity = random.choice(remaining_activities)
                user_input = input(f"\nAnswer about topic:\nWould you like to {activity.lower()}? \nYou:\n").strip()
                
                # Use evaluate_response_relevance to determine if user wants this activity
                evaluation = evaluate_response_relevance(f"Would you like to {activity.lower()}?", user_input, activity)
                
                if evaluation['action'] == "CONTINUE_TOPIC":
                    current_activity = activity
                    remaining_activities.remove(activity)
                    current_prompt = f"Let's have a conversation about this topic: {activity}. Start with a question for the user. I want only the question, nothing else."
                elif evaluation['action'] == "END_CONVERSATION":
                    break
                else:  # CHANGE_TOPIC or other
                    remaining_activities.remove(activity)
                    continue
            else:
                # No more predefined activities
                print("No more predefined activities")
                break
        
        # Generate response and get user reply
        query_ollama_streaming(current_prompt)
        user_reply = input("\nYou: \n")
        
        # Evaluate response relevance
        evaluation = evaluate_response_relevance(current_prompt, user_reply, current_activity)
        print(f"\n[Debug: Action: {evaluation['action']}, Reason: {evaluation['reason']}]")
        
        if evaluation['action'] == "END_CONVERSATION":
            break
        elif evaluation['action'] == "CHANGE_TOPIC":
            current_activity = None
            conversation_history = []
            current_prompt = None
        elif evaluation['action'] == "CONTINUE_TOPIC":
            # Add to conversation history for context
            conversation_history.append({"question": current_prompt, "response": user_reply})
            
            # Limit history to last 3 exchanges to avoid context overflow
            if len(conversation_history) > 3:
                conversation_history = conversation_history[-3:]
                
            # Build context from conversation history
            context = ""
            if conversation_history:
                context = "Previous conversation context:\n"
                for i, exchange in enumerate(conversation_history[:-1], 1):  # Exclude the last one as it's the current
                    context += f"Exchange {i}: Q: {exchange['question']} | A: {exchange['response']}\n"
                context += "\n"
                
            # Continue the conversation with the user's response and history context
            current_prompt = f"{context}The user responded: '{user_reply}'. Continue the conversation about '{current_activity}' with a new question or comment. Keep the conversation engaging and natural."



'''
TODO: 
We could first ask the user if they want to talk about something specific, otherwise we start suggesting activities
Limited user experience: add conversational memory so it can be continuous (SHORT-TERM MEMORY) - actually conversation_history already provides some minimal context
Activities are static (I made an array: activities): we could ask questions based on information we have about the user (RAG) + same static activities
'''
