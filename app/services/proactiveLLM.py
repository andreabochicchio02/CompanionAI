import app.services.ollama as ollama
import app.services.utilis as utilis

import random

def evaluate_init_msg(user_input, model):
    prompt = (  
                f"Determine whether the user's message is just a greeting to start a conversation or a question that requires a response. \n"
                f"Respond only with:\n"
                f"INITIAL — if it is a simple greeting or conversation starter.\n"
                f"QUESTION — if it is a question or a message introducing a topic the user wants to discuss.\n"
                f"Do not include anything else in your reply, only INITIAL or QUESTION.\n"

                f"User message: {user_input}"
            )

    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utilis.append_log(f"User Response: {user_input}. Evaluation: {answer}")
    return answer


def evaluate_type_topic(user_input, model):
    prompt = ( 
                f"Determine whether the user is asking you to suggest a topic to talk about, or if the user is proposing a topic themselves. \n"
                f"Respond only with:\n"
                f"LLM_TOPIC — if the user is asking for a suggestion about what to talk about.\n"
                f"USER_TOPIC — If they introduce a topic they want to discuss or ask a question. \n"
                f"Do not include anything else in your reply, only LLM_TOPIC or USER_TOPIC.\n"

                f"User message: {user_input}"
            )

    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utilis.append_log(f"User Response: {user_input}. Evaluation: {answer}")
    return answer


def evaluate_choose_topic(user_input, topic, model):
    prompt = ( 
                f"Determine whether the user is wants to continue the conversation, or if they want to talk about something else.\n"
                f"The user might say yes, express interest, or simply start responding with something related to the topic — all of these mean they want to continue.\n"
                f"Respond only with:\n"
                f"CONTINUE_TOPIC — if the user is fine with the suggested topic and either agrees explicitly or begins discussing something related to it.\n"
                f"CHANGE_TOPIC — If the user asks you to suggest another topic to talk about.\n"
                f"Do not include anything else in your reply, only CONTINUE_TOPIC or CHANGE_TOPIC.\n"

                f"Topic proposed: {topic}\n"

                f"User message: {user_input}"
            )

    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utilis.append_log(f"User Response: {user_input}. Evaluation: {answer}")
    return answer


def evaluate_general_msg(user_input, topic, short_memory, model):
    prompt = ( 
                f"Based on the user's message and the context of the ongoing conversation, determine what the user intends to do next.\n"
                f"Respond only with one of the following options\n"
                f"CONTINUE_TOPIC — If the user is continuing the current topic, expanding on it, replying to a question, or asking a related follow-up.\n"
                f"CHANGE_TOPIC — If the user explicitly asks you to suggest a new topic to talk about.\n"
                f"END — if the user wants to end or close the conversation.\n"
                f"NEW_QUESTION — if the user asks a new, open-ended question that is unrelated to the current topic.\n"
                f"Do not include anything else in your reply, only CONTINUE_TOPIC, CHANGE_TOPIC, END or NEW_QUESTION\n"

                f"Current topic: {topic}\n"

                f"Here is the conversation so far with the user: {short_memory}\n"

                f"User message: {user_input}"
            )

    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utilis.append_log(f"User Response: {user_input}. Evaluation: {answer}")
    return answer


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




'''
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
    utilis.append_log(f"Context: {context}. User Response: {user_response}. Evaluation: {answer}")
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
'''