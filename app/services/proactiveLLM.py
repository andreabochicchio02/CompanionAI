import app.services.ollama as ollama
import app.services.utils as utils

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
    utils.append_conversation_log(f"We have to check if: INITIAL or QUESTION.\n\nPrompt:\n{prompt.strip()}.\n\nEvaluation:\n{answer.strip()}\n\n")
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
    utils.append_conversation_log(f"We have to check if: LLM_TOPIC or USER_TOPIC.\n\nPrompt:\n{prompt.strip()}.\n\nEvaluation:\n{answer.strip()}\n\n")
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
    utils.append_conversation_log(f"We have to check if: CONTINUE_TOPIC or CHANGE_TOPIC.\n\nPrompt:\n{prompt.strip()}.\n\nEvaluation:\n{answer.strip()}\n\n")
    return answer


def evaluate_general_msg(user_input, topic, short_memory, model):
    prompt = (
        "Based on the user's message and the context of the ongoing conversation, determine what the user intends to do next.\n"
        "Respond only with one of the following options\n"
        "CONTINUE_TOPIC — If the user is continuing the current topic, expanding on it, replying to a question, or asking a related follow-up.\n"
        # "END — if the user wants to end or close the conversation.\n"
        "NEW_QUESTION — if the user asks a new, open-ended question that is unrelated to the current topic.\n"
        "Do not include anything else in your reply, only CONTINUE_TOPIC or NEW_QUESTION\n\n"
    )

    if short_memory:
        prompt += f"Here is the conversation so far with the user: {short_memory}\n"

    prompt += f"User message: {user_input}"

    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utils.append_conversation_log(f"We have to check if: CONTINUE_TOPIC or NEW_QUESTION.\n\nPrompt:\n{prompt.strip()}.\n\nEvaluation:\n{answer.strip()}\n\n")
    return answer


def find_the_topic(activities):
    """
    Randomly selects an unselected activity from the list.
    Once selected, marks it as used (selected = True).
    If all activities have been selected, returns (None, None).
    """
    unselected = [a for a in activities if not a["selected"]]

    if not unselected:
        return None, None  # All topics already used

    activity_obj = random.choice(unselected)
    activity_obj["selected"] = True  # Mark as selected

    question = f"Would you like to {activity_obj['activity'].lower()}?"
    return activity_obj["activity"], question


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