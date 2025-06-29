import libraries.ollama as ollama
import libraries.textSpeech as textSpeech

import random

def evaluate_response_relevance(question, user_response, current_topic, model):
    """
    Evaluate if the user's response is relevant to the current topic and question.
    Returns a dictionary with suggested action.
    """
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

    answer = ollama.query_ollama_no_stream(prompt, model)
    
    # Simple parsing of the response
    if "CONTINUE_TOPIC" in answer:
        return {"action": "CONTINUE_TOPIC", "reason": "User wants to continue"}
    elif "CHANGE_TOPIC" in answer:
        return {"action": "CHANGE_TOPIC", "reason": "User wants to change topic"}
    elif "END_CONVERSATION" in answer:
        return {"action": "END_CONVERSATION", "reason": "User wants to stop"}
    else:
        return {"action": "CONTINUE_TOPIC", "reason": "Unclear response, defaulting to continue"}

def find_the_topic(activities, model, text_to_speech, speech_to_text):
    remaining_activities = activities.copy()
    while True:
        if remaining_activities:
            activity = random.choice(remaining_activities)

            print(f"\nAssistant (Answer about topic): Would you like to {activity.lower()}?\n\nYou: ", end="")
            if text_to_speech:
                textSpeech.text_to_speech_locally(f"Would you like to {activity.lower()}?")
            else: 
                if speech_to_text:
                    print("\nUser (Speak now...): ")
                    user_input = textSpeech.speech_to_text_locally()
                    print(user_input)    
                else:
                    user_input = input("").strip()
            
            # Use evaluate_response_relevance to determine if user wants this activity
            evaluation = evaluate_response_relevance(f"Would you like to {activity.lower()}?", user_input, activity, model)
            
            if evaluation['action'] == "CONTINUE_TOPIC":
                remaining_activities.remove(activity)
                prompt = f"Let's have a conversation about this topic: {activity}. Start with a question for the user. I want only the question, nothing else."
                return activity, prompt
            elif evaluation['action'] == "END_CONVERSATION":
                return False, "Okay, Bye Bye!"
            else:  # CHANGE_TOPIC or other
                remaining_activities.remove(activity)
                continue
        else:
            # No more predefined activities
            print("No more predefined activities")
            return False, "No more predefined activities"


'''
TODO: 
We could first ask the user if they want to talk about something specific, otherwise we start suggesting activities
Limited user experience: add conversational memory so it can be continuous (SHORT-TERM MEMORY) - actually conversation_history already provides some minimal context
Activities are static (I made an array: activities): we could ask questions based on information we have about the user (RAG) + same static activities
'''