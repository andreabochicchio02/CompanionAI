import app.services.utils as utils
import app.services.ollama as ollama
import threading
import os
import json
import datetime
from zoneinfo import ZoneInfo

class ChatManager:
    def __init__(self, summarizer_model, state, max_turns=6, user_history=None, assistant_history=None, topic='', topics_pool=None):
        """
        Initializes the ChatManager.

        Args:
            summarizer_model (str): The model name used for summarization.
            state (Enum or str): Current state of the chat.
            max_turns (int): Number of recent turns to track for summarization.
            user_history (list, optional): List of past user messages.
            assistant_history (list, optional): List of past assistant messages.
            topic (str): Topic of the conversation.
        """
        self.model = summarizer_model
        self.max_turns = max_turns

        self.chat = {
            'user': user_history if user_history is not None else [],
            'assistantAI': assistant_history if assistant_history is not None else [],
            'topic': topic,
            'state': state,
            'topics_pool': topics_pool if topics_pool is not None else []
        }

        self.summary = ""
        self.summary_result = ""
        self.num_last_messages = 0
        self.summary_lock = threading.Lock()
        self.is_summarizing = False

    def add_user_message(self, user_message, session_id, file_path):
        """Appends a user message to the chat history."""
        self.chat['user'].append(user_message)
        self.save_to_file(session_id, file_path)
        utils.append_conversation_log("-----------------------------------------------------------------------\n")
        utils.append_conversation_log(f"USER send:\n{user_message.strip()}\n\n")

    def add_assistant_message(self, assistant_message, session_id, file_path):
        """
        Appends an assistant message, triggers save and possible summarization.

        Args:
            assistant_message (str): The assistant's reply.
            session_id (str): Unique identifier for the chat session.
            file_path (str): File path to save the chat history.
        """
        self.chat['assistantAI'].append(assistant_message)
        self.num_last_messages += 1
        self.save_to_file(session_id, file_path)
        self.check_to_summarize()
        utils.append_conversation_log(f"ASSISTANT AI send to USER:\n{assistant_message.strip()}\n\n\n")

    def get_last_user_message(self):
        """Returns the most recent user message."""
        return self.chat['user'][-1]
    
    def set_chat_state(self, state):
        """Sets the current chat state."""
        self.chat['state'] = state

    def get_chat_state(self):
        """Returns the current chat state."""
        return self.chat['state']
    
    def set_chat_topic(self, topic):
        """Sets the current conversation topic."""
        self.chat['topic'] = topic

    def get_chat_topic(self):
        """Returns the current conversation topic."""
        return self.chat['topic']

    def get_topics_pool(self):
        """Returns the session-scoped topics pool (list of dicts)."""
        return self.chat.get('topics_pool', [])

    def set_topics_pool(self, topics_pool):
        """Sets the session-scoped topics pool."""
        self.chat['topics_pool'] = topics_pool or []

    def summarize_history_async(self, history_snapshot, current_summary):
        """
        Starts asynchronous summarization of the chat history.

        Args:
            history_snapshot (dict): Contains 'user' and 'assistantAI' lists.
            current_summary (str): The current summary string to prepend.
        """
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
        """
        Returns the updated prompt context with summary and recent conversation.

        Returns:
            str: Combined summary and recent message prompt.
        """
        # Update the summary with the latest one if available
        if self.summary_lock.acquire(blocking=False):
            try:
                if self.summary_result and self.summary_result != self.summary:
                    self.summary = self.summary_result
            finally:
                self.summary_lock.release()

        return self.build_prompt()

    def build_prompt(self):
        """
        Constructs the prompt using summary and last few chat exchanges.

        Returns:
            str: The final prompt to be sent to the assistant model.
        """
        prompt = ""

        if self.chat['assistantAI'] or self.summary:
            prompt += (
                "Note: You have access to a summarized context of the conversation as well as the last "
                f"{self.max_turns} exchanges between the user and assistant. "
                "Use this information to answer only if necessary.\n"
            )

        if self.summary:
            prompt += f"{self.summary}\n\n"

        for user, assistant in zip(self.chat['user'][-self.max_turns:], self.chat['assistantAI'][-self.max_turns:]):
            prompt += f"User: {user}\nAssistant: {assistant}\n\n"

        return prompt

    def check_to_summarize(self):
        """
        Checks whether the number of new exchanges has reached the threshold,
        and if so, triggers the summarization asynchronously.
        """
        if self.num_last_messages >= self.max_turns and not self.is_summarizing:
            recent_history = {
                'user': self.chat['user'][-self.max_turns:],
                'assistantAI': self.chat['assistantAI'][-self.max_turns:]
            }
            self.summarize_history_async(recent_history, self.summary)
            self.num_last_messages = 0

    def save_to_file(self, session_id, file_path):
        """
        Saves the current chat session to a JSON file.

        Args:
            session_id (str): The unique identifier for the session.
            file_path (str): The path to the JSON file for storing chat history.
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Load existing data if file exists
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    all_chats = json.load(f)
                except json.JSONDecodeError:
                    all_chats = {}
        else:
            all_chats = {}

        # Store or update chat session
        all_chats[session_id] = {
            'user': self.chat['user'],
            'assistantAI': self.chat['assistantAI'],
            'topic': self.chat['topic'],
            'state': self.chat['state'].name if hasattr(self.chat['state'], 'name') else str(self.chat['state']),
            'summary': self.summary,
            'timestamp': datetime.datetime.now(ZoneInfo("Europe/Rome")).isoformat()
        }

        # Save updated data back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(all_chats, f, indent=4, ensure_ascii=False)
