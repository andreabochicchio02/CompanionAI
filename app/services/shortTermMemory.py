import libraries.ollama as ollama

import threading
import re

NUM_LAST_MESS = 0

# Conversation history as list of (user_input, assistant_response) tuples
history = {'user': [], 'assistantAI': []}
# Current summarized context of the conversation
summary = ""

# Lock to safely update the shared summary across threads
summary_lock = threading.Lock()
# Shared dictionary to hold the latest summary value
summary_result = ""

# Flag to avoid multiple simultaneous summarizations
is_summarizing = False


def summarize_history_async(history_snapshot, current_summary, model):
    global is_summarizing
    if is_summarizing:
        return
    is_summarizing = True

    def worker():
        global is_summarizing, summary_result
        try:
            print("\n[DEBUG] Starting conversation summarization...")
            text_to_summarize = ""
            if current_summary:
                text_to_summarize += f"{current_summary}\n\n"
            
            for user, assistant in zip(history_snapshot['user'], history_snapshot['assistantAI']):
                text_to_summarize += f"User: {user}\nAssistant: {assistant}\n"
            text_to_summarize += "\n"

            summarizing_prompt = (
                f"Summarize concisely and precisely the following conversation including all key facts:\n\n"
                f"{text_to_summarize.strip()}\n\nSummary:"
            )
            new_summary = ollama.query_ollama_no_stream(summarizing_prompt, model=model)
            with summary_lock:
                summary_result = new_summary.strip()
        finally:
            is_summarizing = False
            print("\n[DEBUG] Summarization completed and ready.")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def clean_text(text):
        text = text.replace('\n', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def summary_messages(current_summary, history, max_turns):
    prompt = ""

    if len(history['user']) > 0:
        prompt += (
            "Note: You have access to a summarized context of the conversation as well as the last "
            f"{max_turns} exchanges between the user and assistant. "
            "Use this information to answer only if necessary.\n\n"
        )

    if current_summary:
        prompt += f"{current_summary}\n\n"

    for user, assistant in zip(history['user'][-max_turns:], history['assistantAI'][-max_turns:]):
        clean_user = clean_text(user)
        clean_assistant = clean_text(assistant)
        prompt += f"User: {clean_user}\nAssistant: {clean_assistant}\n"
        
    return prompt

def get_recent_messages(max_turns):
    global summary
    if summary_lock.acquire(blocking=False):
        try:
            if summary_result and summary_result != summary:
                summary = summary_result
        finally:
            summary_lock.release()
    
    return summary_messages(summary, history, max_turns)

def update_history(user_input, response, max_turns, summarizer_model):
    global NUM_LAST_MESS
    history['user'].append(user_input)
    history['assistantAI'].append(response)
    NUM_LAST_MESS += 1
    if (NUM_LAST_MESS >= max_turns) and not is_summarizing:
        recent_history = {
            'user': history['user'][-max_turns:],
            'assistantAI': history['assistantAI'][-max_turns:]
        }
        summarize_history_async(recent_history, summary, summarizer_model)
        NUM_LAST_MESS = 0

def clean_history():
    global NUM_LAST_MESS, history, summary, summary_result

    NUM_LAST_MESS = 0
    history = {'user': [], 'assistantAI': []}
    summary = ""
    summary_result = ""