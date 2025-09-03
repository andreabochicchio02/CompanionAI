import app.services.config as config
from datetime import datetime, time

def append_server_log(message):
    """ Appends a line to the server log with the current date and time followed by the given message."""

    # Get current date and time as a formatted string
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Open the file in append mode and write the timestamp and message
    with open(config.SERVER_LOG, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}]\t{message}\n")

def append_memory_log(message):
    """ Appends a line to the memory log with the current date and time followed by the given message."""

    # Get current date and time as a formatted string
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Open the file in append mode and write the timestamp and message
    with open(config.MEMORY_LOG, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}]\t{message}\n")

def clear_server_log():
    """
    Clears all contents of the log file by opening it in write mode.
    This effectively empties the file, keeping the file itself (it won't be deleted).
    """
    with open(config.SERVER_LOG, "w", encoding="utf-8") as file:
        pass  # Opening in write mode with no content truncates the file

def clear_memory_log():
    """ Clears all contents of the memory log file by opening it in write mode. """
    with open(config.MEMORY_LOG, "w", encoding="utf-8") as file:
        pass  # Opening in write mode with no content truncates the file

def append_conversation_log(message):
    """ Appends a line to the conversation log. """
    with open(config.CONVERSATION_LOG_FOLD, "a", encoding="utf-8") as file:
        file.write(message)

def clear_conversation_log():
    """ Clears all contents of the conversation log file by opening it in write mode. """
    with open(config.CONVERSATION_LOG_FOLD, "w", encoding="utf-8") as file:
        pass

def keep_event(event):
    """
    Determines if an event should be kept based on its date and recurrence.
    """
    now = datetime.now()
    date_str = event.get("date")
    recurrence = event.get("recurrence")

    if 'T' in date_str:
        event_date = datetime.fromisoformat(date_str)
    else:
        base_date = datetime.fromisoformat(date_str)
        event_date = datetime.combine(base_date.date(), time(23, 59, 59))

    if event_date >= now:
        return True

    if not recurrence:
        return False

    end_str = recurrence.get("end")
    if end_str:
        if 'T' in end_str:
            end_date = datetime.fromisoformat(end_str)
        else:
            base_end = datetime.fromisoformat(end_str)
            end_date = datetime.combine(base_end.date(), time(23, 59, 59))
        return end_date >= now

    return True
