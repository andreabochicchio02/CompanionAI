import app.services.ollama as ollama
import app.services.utils as utils
import app.services.rag as rag
import app.services.config as config

import random
import json

def evaluate_init_msg(user_input, model):
    prompt = (  
                f"Determine whether the user's message is just a greeting to start a conversation or a question that requires a response. \n"
                f"Respond only with:\n"
                f"INITIAL — if it is a simple greeting\n"
                f"QUESTION — if it is a question or a message introducing a topic the user wants to discuss.\n"
                f"EVENTS — If the user explicitly asks about any events or appointments they have already scheduled for a specific period (e.g., events in August, events next week, events on August 15)\n"
                f"Do not include anything else in your reply, only INITIAL, EVENTS or QUESTION.\n"

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
                f"EVENTS — If the user explicitly asks about any events or appointments they have already scheduled for a specific period (e.g., events in August, events next week, events on August 15)\n"
                f"Do not include anything else in your reply, only LLM_TOPIC, EVENTS or USER_TOPIC.\n"

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


def evaluate_general_msg(user_input, short_memory, model):
    prompt = (
        "Based on the user's message and the context of the ongoing conversation, determine what the user intends to do next.\n"
        "Respond only with one of the following options\n"
        "CONTINUE_TOPIC — If the user is continuing the current topic, expanding on it, replying to a question, or asking a related follow-up.\n"
        "NEW_QUESTION — if the user asks a new, open-ended question that is unrelated to the current topic.\n"
        "EVENTS — If the user explicitly asks about any events or appointments they have already scheduled for a specific period (e.g., events in August, events next week, events on August 15)\n"
        "Do not include anything else in your reply, only CONTINUE_TOPIC, EVENTS, or NEW_QUESTION\n\n"
    )

    if short_memory:
        prompt += f"Here is the conversation so far with the user: {short_memory}\n"

    prompt += f"User message: {user_input}"

    answer = ollama.query_ollama_no_stream(prompt, model).strip().upper()
    utils.append_conversation_log(f"We have to check if: CONTINUE_TOPIC, EVENTS, or NEW_QUESTION.\n\nPrompt:\n{prompt.strip()}.\n\nEvaluation:\n{answer.strip()}\n\n")
    return answer


# ----- Session-scoped topics helpers ----- #
def build_topics_pool(base_activities):
    """
    Build a session-scoped topics pool combining predefined activities and
    additional suggestions derived from RAG memory. This is computed once per
    session and then reused.

    Returns a list of dicts: {"activity": str, "selected": bool}
    """
    # 1) Start with a shallow copy of predefined activities
    pool = []
    for a in base_activities:
        # Normalize each entry to expected schema
        label = a["activity"] if isinstance(a, dict) else str(a)
        pool.append({"activity": label, "selected": False})

    # 2) Augment with user-personalized topics from memory (best-effort)
    try:
        relevant_memory = rag.get_relevant_memory("Some interests, likes, hobbies, plans, past experiences about the user")
        if relevant_memory:
            prompt = (
                f"From the user's personal memory below, extract up to 5 concise and concrete conversation topics.\n"
                f"Prefer interests, likes, hobbies, plans, and past experiences, but do not repeat similar or identical ones.\n"
                f"Return them as very short, natural-sounding questions that can start a conversation.\n"
                f"Respond ONLY with a JSON array of strings, e.g. [\"Can you tell me about your children?\", \"What kind of music do you enjoy?\", \"Do you follow any sports?\"].\n\n"
                f"User memory:\n{relevant_memory}\n")
            
            raw = ollama.query_ollama_no_stream(prompt, config.MAIN_MODEL)

            try:
                topics = json.loads(raw)
                if isinstance(topics, list):
                    for t in topics[:5]:
                        if not isinstance(t, str):
                            continue

                        label = t.strip()
                        if not label:
                            continue
                        
                        if any(label.lower() == e["activity"].lower() for e in pool):
                            continue
                        
                        pool.append({"activity": label, "selected": False})
            except Exception:
                pass
    except Exception as e:
        utils.append_conversation_log(f"RAG build_topics_pool error: {e}\n")

    return pool


def choose_topic_from_pool(topics_pool):
    """
    Chooses an unselected topic from the pool, marks it selected, and returns
    (topic_label, question). If pool exhausted, returns (None, None).
    """
    if not topics_pool:
        return None, None
    unselected = [e for e in topics_pool if not e.get("selected")]
    if not unselected:
        return None, None
    entry = random.choice(unselected)
    entry["selected"] = True
    question = entry["activity"]
    return question