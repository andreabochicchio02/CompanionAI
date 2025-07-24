import libraries.ollama as ollama
import libraries.textSpeech as textSpeech
import app.services.utilis as utilis

import random

def find_the_topic(activities, text_to_speech=False, speech_to_text=False):
    """
    Suggest a topic from predefined activities for web interface.
    Returns the first available topic without user interaction for web usage.
    """
    # Per l'interfaccia web, proponi semplicemente il primo topic disponibile
    activity = random.choice(activities)
    question = f"Would you like to {activity.lower()}?"
    return activity, question

def suggest_new_topic(activities, model, current_topic=None, asked_topics=None):
    """
    Suggest a new topic from predefined activities, excluding current topic and already asked topics.
    """
    available_activities = activities.copy()
    if current_topic and current_topic in available_activities:
        available_activities.remove(current_topic)
    if asked_topics:
        available_activities = [a for a in available_activities if a not in asked_topics]
    
    if not available_activities:
        return False, "No more predefined activities"
    
    activity = random.choice(available_activities)
    question = f"Would you like to {activity.lower()}?"
    return activity, question

def evaluate_user_message(recent_messages, user_response, model):
    """
    Valuta la risposta dell'utente nel contesto dei messaggi recenti e determina se vuole:
    - terminare la conversazione (END_CONVERSATION)
    - ricevere un suggerimento di argomento (SUGGEST_TOPIC)
    - ricevere una risposta a una domanda aperta (OWN_QUESTION)
    Restituisce una stringa: "END_CONVERSATION", "SUGGEST_TOPIC" o "OWN_QUESTION"
    """
    context = recent_messages.strip() if recent_messages else ""
    prompt = (
        f"Conversation so far:\n{context}\n\n"
        f"User response: '{user_response}'\n\n"
        f"Decide between these four options based on the user's response and the conversation context:\n"
        f"1. END_CONVERSATION: if they want to end the conversation (examples: 'bye', 'I have to go', 'enough', 'stop', 'goodbye', 'end').\n"
        f"2. SUGGEST_TOPIC: if they ask for a suggestion about what to talk about (examples: 'suggest a topic', 'what can we talk about?', 'I don't know what to talk about', 'give me an idea', 'change topic', 'another one', 'something else').\n"
        f"3. OWN_QUESTION: if they ask an open question or something specific (examples: 'What is the capital of Italy?', 'Tell me about the weather', 'What do you know about John?', 'who', 'what', 'when', 'where', 'why', 'how').\n"
        f"If the user's message contains a question mark (?) or starts with a question word (who, what, when, where, why, how), classify as OWN_QUESTION.\n"
        f"If the user simply says 'yes', 'ok', 'sure', 'let's talk about it', 'sounds good', and there is a topic suggested, classify as CONTINUE_TOPIC.\n"
        f"Reply with only one of the following words (in English): END_CONVERSATION, SUGGEST_TOPIC, OWN_QUESTION, CONTINUE_TOPIC"
    )
    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utilis.append_log(f"Evaluation: {answer}, User Response: {user_response}, Context: {context}")
    if "END_CONVERSATION" in answer:
        return "END_CONVERSATION"
    elif "SUGGEST_TOPIC" in answer:
        return "SUGGEST_TOPIC"
    elif "CONTINUE_TOPIC" in answer:
        return "CONTINUE_TOPIC"
    else:
        return "OWN_QUESTION"


def evaluate_topic_continuation(user_response, current_topic, model, recent_messages=None):
    """
    Quando l'utente ha un topic attivo, valuta se vuole continuare, cambiare o terminare.
    Usa opzionalmente recent_messages come contesto.
    """
    context = recent_messages.strip() if recent_messages else ""
    prompt = (
        f"Conversation so far:\n{context}\n\n"
        f"Current topic: '{current_topic}'\n"
        f"User response: '{user_response}'\n\n"
        f"Based on the user's response, do they want to:\n"
        f"1. CONTINUE_TOPIC - continue talking about the current topic (examples: 'yes', 'ok', 'sure', 'let's talk about it', 'sounds good').\n"
        f"2. CHANGE_TOPIC - talk about something else (examples: 'change topic', 'another one', 'something else').\n"
        f"3. END_CONVERSATION - stop the conversation (examples: 'bye', 'enough', 'stop', 'goodbye', 'end').\n"
        f"If the user's message contains a question mark (?) or starts with a question word (who, what, when, where, why, how), classify as CHANGE_TOPIC.\n"
        f"Reply with only one of the following words (in English): CONTINUE_TOPIC, CHANGE_TOPIC, END_CONVERSATION"
    )
    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utilis.append_log(f"Evaluation: {answer}, User Response: {user_response}, Current Topic: {current_topic}, Context: {context}")
    if "CONTINUE_TOPIC" in answer:
        return "CONTINUE_TOPIC"
    elif "CHANGE_TOPIC" in answer:
        return "CHANGE_TOPIC"
    elif "END_CONVERSATION" in answer:
        return "END_CONVERSATION"
    else:
        return "CONTINUE_TOPIC"  # Default
