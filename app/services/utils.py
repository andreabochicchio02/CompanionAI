from datetime import datetime

FILE_LOG = "app/services/log.txt"
FILE_COMPLETE_LOG = "app/services/logComplete.txt"

def append_log(message):
    """
    Appends a line to the specified text file with the current date and time followed by the given message.
    
    :param message: The message to write to the file
    :param filename: The name of the text file (default is 'log.txt')
    """
    # Get current date and time as a formatted string
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Open the file in append mode and write the timestamp and message
    with open(FILE_LOG, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}]\t{message}\n")


def append_log_complete(message):
    """
    Appends a line to the specified text file with the current date and time followed by the given message.
    
    :param message: The message to write to the file
    :param filename: The name of the text file (default is 'logComplete.txt')
    """
    with open(FILE_COMPLETE_LOG, "a", encoding="utf-8") as file:
        file.write(f"{message}\n\n\n")


def clear_log_file():
    """
    Clears all contents of the log file by opening it in write mode.
    This effectively empties the file, keeping the file itself (it won't be deleted).
    """
    with open(FILE_LOG, "w", encoding="utf-8") as file:
        pass  # Opening in write mode with no content truncates the file


def clear_log_complete_file():
    """
    Clears all contents of the log file by opening it in write mode.
    This effectively empties the file, keeping the file itself (it won't be deleted).
    """
    with open(FILE_COMPLETE_LOG, "w", encoding="utf-8") as file:
        pass  # Opening in write mode with no content truncates the file