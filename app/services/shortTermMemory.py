import libraries.ollama as ollama
import threading
import re, os, json
import datetime

class ChatManager:
    def __init__(self, summarizer_model, state, max_turns=6, user_history=None, assistant_history=None, topic=''):
        self.model = summarizer_model
        self.max_turns = max_turns

        self.chat = {
            'user': user_history if user_history is not None else [],
            'assistantAI': assistant_history if assistant_history is not None else [],
            'topic': topic,
            'state': state
        }

        self.summary = ""
        self.summary_result = ""

        self.num_last_messages = 0
        self.summary_lock = threading.Lock()
        self.is_summarizing = False

    def add_user_message(self, user_message):
        self.chat['user'].append(user_message)

    def add_assistant_message(self, assistant_message, session_id, file_path):
        self.chat['assistantAI'].append(assistant_message)
        self.num_last_messages += 1
        self.save_to_file(session_id, file_path)
        self.check_to_summarize()

    def get_last_user_message(self):
        return self.chat['user'][-1]
    
    def set_chat_state(self, state):
        self.chat['state'] = state

    def set_chat_topic(self, topic):
        self.chat['topic'] = topic

    def get_chat_topic(self):
        return self.chat['topic']
    
    def get_chat_state(self):
        return self.chat['state']

    def clean_text(self, text):
        text = text.replace('\n', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def summarize_history_async(self, history_snapshot, current_summary):
        if self.is_summarizing:
            return
        self.is_summarizing = True

        def worker():
            try:
                text_to_summarize = f"{current_summary}\n\n" if current_summary else ""

                for user, assistant in zip(history_snapshot['user'], history_snapshot['assistantAI']):
                    text_to_summarize += f"User: {user}\nAssistant: {assistant}\n"
                text_to_summarize += "\n"

                summarizing_prompt = (
                    "Summarize concisely and precisely the following conversation including all key facts:\n\n"
                    f"{text_to_summarize.strip()}\n\nSummary:"
                )

                new_summary = ollama.query_ollama_no_stream(summarizing_prompt, model=self.model)

                with self.summary_lock:
                    self.summary_result = new_summary.strip()

            finally:
                self.is_summarizing = False

        threading.Thread(target=worker, daemon=True).start()

    def get_recent_messages(self):
        # Aggiorna il contesto con l’ultimo summary generato se disponibile
        if self.summary_lock.acquire(blocking=False):
            try:
                if self.summary_result and self.summary_result != self.summary:
                    self.summary = self.summary_result
            finally:
                self.summary_lock.release()

        return self.build_prompt()

    def build_prompt(self):
        prompt = ""

        if self.chat['user']:
            prompt += (
                "Note: You have access to a summarized context of the conversation as well as the last "
                f"{self.max_turns} exchanges between the user and assistant. "
                "Use this information to answer only if necessary.\n\n"
            )

        if self.summary:
            prompt += f"{self.summary}\n\n"

        for user, assistant in zip(self.chat['user'][-self.max_turns:], self.chat['assistantAI'][-self.max_turns:]):
            prompt += f"User: {user}\nAssistant: {assistant}\n"

        return prompt

    def check_to_summarize(self):
        if self.num_last_messages >= self.max_turns and not self.is_summarizing:
            recent_history = {
                'user': self.chat['user'][-self.max_turns:],
                'assistantAI': self.chat['assistantAI'][-self.max_turns:]
            }
            self.summarize_history_async(recent_history, self.summary)
            self.num_last_messages = 0

    def save_to_file(self, session_id, file_path):
        # Assicurati che la directory esista
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Carica il file se esiste, altrimenti inizializza un dizionario vuoto
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    all_chats = json.load(f)
                except json.JSONDecodeError:
                    all_chats = {}
        else:
            all_chats = {}

        # Salva o sovrascrive la chat per session_id
        all_chats[session_id] = {
            'user': self.chat['user'],
            'assistantAI': self.chat['assistantAI'],
            'topic': self.chat['topic'],
            'state': self.chat['state'].name,  # salva come stringa es: "START"
            'summary': self.summary,
            'timestamp': datetime.datetime.now().isoformat()
        }

        # Scrive il file aggiornato
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(all_chats, f, indent=4, ensure_ascii=False)