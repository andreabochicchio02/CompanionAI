import { observer, addThinkingDots, removeThinkingDots } from './thinking-dots.js';

let SESSION_ID = 0
let TEXTAREACENTERED = true;
let ENABLE_TTS = false;

document.addEventListener('DOMContentLoaded', async () => {
    const textArea = document.getElementById('textarea');
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');
    const ttsToggle = document.getElementById('tts-toggle');
    const newChat = document.getElementById('new-chat');
    const cleanHistoryBtn = document.getElementById('clear-history-btn');

    textArea.addEventListener('input', () => textAreaResize());

    sendButton.addEventListener('click', (event) => handleClickSendButton(event));
    micButton.addEventListener('click', (event) => handleClickMic(event));

    ttsToggle.addEventListener('change', (event) => {ENABLE_TTS = event.target.checked;});
    
    newChat.addEventListener('click', (event) => createNewChat(event));

    cleanHistoryBtn.addEventListener('click', (event) => cleanHistory(event));

    textArea.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            handleClickSendButton(event);
        }
    });

    await createSessionKey();
    
    await uploadHistoryChats();

    // Start observing message container for changes (e.g. to stop animation)
    observer.observe(document.getElementById('messages'), { childList: true });
});


/**
 * Sends a POST request to the backend to start a new chat session.
 * If successful, assigns the session ID to the global variable SESSION_ID.
 * Logs an error message to the console if the request fails or the server returns an error.
 */
async function createSessionKey() {
    try {
        const response = await fetch('/chatLLM/newSessionID', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            console.error('Failed to fetch chat sessions, status:', response.status);
            return;
        }

        const data = await response.json();

        // If the server responded with success, store the session ID
        if (data.success) {
            SESSION_ID = data.message; // 'message' contains the session ID
            const sessionID_paragraf = document.getElementById('session-id');
            sessionID_paragraf.textContent = 'Session ID: ' + SESSION_ID;
        } else {
            console.error('Failed to create session:', data.message);
        }

    } catch (error) {
        // Handle fetch or parsing errors
        console.error('Error creating session:', error);
    }
}

/**
 * Sends a user message to the backend LLM service and handles the streamed response.
 * It disables input buttons, displays the user's message, shows a "thinking" indicator,
 * then listens for server-sent events to progressively display the assistant's response.
 * Enables buttons and optionally triggers TTS when the response ends or errors.
 * @param {string} text - The user input message to send.
 */
async function sendMessageToLLM(text) {
    if (TEXTAREACENTERED) {
        moveDownTextArea();
        createChatButton(SESSION_ID, new Date().toLocaleString(), true);
    }

    // Disable input buttons while waiting for the response
    disableSendButtons();

    // Display the user's message immediately
    addMessage(text, 'user');

    // Clear the input textarea
    document.getElementById('textarea').value = '';

    // Show thinking dots animation
    addThinkingDots();

    try {
        // Send the user prompt to the backend API
        const response = await fetch('/chatLLM/sendPrompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: text,
                sessionId: SESSION_ID
            })
        });

        if (!response.ok) {
            console.error('Failed to fetch chat sessions, status:', response.status);
            return;
        }

        const result = await response.json();

        // If the backend reports failure, log error and stop
        if (!result.success) {
            console.error('Prompt submission failed:', result.message);
            removeThinkingDots();
            return;
        }

        // Start receiving streamed assistant response via EventSource
        const evtSource = new EventSource('/chatLLM/responseLLM?session_id=' + encodeURIComponent(SESSION_ID));

        let first_token = true;

        // Handle each chunk of streamed data from the server
        evtSource.onmessage = (e) => {
            if (!e.data) return;  // Ignore empty messages

            if (first_token) {
                removeThinkingDots();
                addMessage(e.data, 'assistantAI');  // Show the first token as a new message
                first_token = false;
            } else {
                // Append subsequent tokens to the last message element
                const lastMessage = document.getElementById('messages').lastElementChild;
                if (lastMessage) {
                    lastMessage.textContent += e.data;
                }
            }
        };

        // Handle errors or stream closure
        evtSource.onerror = (e) => {
            removeThinkingDots();
            if (ENABLE_TTS) {
                const last = document.getElementById('messages').lastElementChild;
                if (last) textToSpeech(last.textContent);
            }
            activateSendButtons();
            evtSource.close();
        };

    } catch (error) {
        // Remove thinking indicator and log fetch error
        removeThinkingDots();
        console.error("Prompt request failed:", error);
    }
}

/**
 * Fetches the list of chat sessions from the backend,
 * then populates the #chat-list container with buttons labeled by their timestamp.
 * Clicking a button loads the corresponding chat session.
 */
async function uploadHistoryChats() {
    try {
        // Request the list of session IDs and timestamps from the backend
        const response = await fetch('/chatLLM/uploadChats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            console.error('Failed to fetch chat sessions, status:', response.status);
            return;
        }

        const data = await response.json();

        if (!data.success) {
            return;
        }

        // data.message is an array of [sessionId, timestamp] tuples
        const sessions = data.message;

        const container = document.getElementById('chat-list');
        container.innerHTML = '';   // Clear previous buttons if any

        // Create a button for each session, labeled by formatted timestamp
        sessions.forEach(([sessionId, timestamp]) => {
            createChatButton(sessionId, formatDate(timestamp), false);
        });

    } catch (error) {
        console.error('Error fetching or parsing session IDs:', error);
    }
}


/**
 * Loads the chat history for the given session ID,
 * highlights the corresponding chat button,
 * and displays the chat messages in the UI.
 * @param {string} sessionId - The ID of the chat session to load.
 */
async function loadChat(sessionId) {
    // Reset all chat list buttons to default state
    resetChatListButtons();

    // Highlight and disable the active chat button
    const activeButton = document.getElementById(sessionId);
    if (activeButton) {
        activeButton.style.backgroundColor = 'lightgrey';
        activeButton.disabled = true;
    }

    try {
        // Send a POST request to fetch the chat data for the given session ID
        const response = await fetch('/chatLLM/getChat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                session_id: sessionId 
            })
        });

        if (!response.ok) {
            console.error('Failed to fetch chat session, status:', response.status);
            return;
        }

        const data = await response.json();

        // Check if the backend returned a success status
        if (!data.success) {
            console.error('Failed to load chat:', data.message);
            return;
        }

        cleanChatArea();
        if(TEXTAREACENTERED){
            moveDownTextArea();
        }

        // Extract user and assistant messages from the response
        const userMessages = data.message.user;
        const assistantMessages = data.message.assistantAI;

        // Determine the number of messages to display based on the longer array
        const maxLength = Math.max(userMessages.length, assistantMessages.length);

        // Loop through and add each message to the chat UI in the correct order
        for (let i = 0; i < maxLength; i++) {
            if (userMessages[i]) {
                addMessage(userMessages[i], 'user');       // Add user message
            }
            if (assistantMessages[i]) {
                addMessage(assistantMessages[i], 'assistantAI');  // Add assistant response
            }
        }
    } catch (error) {
        console.error('Error loading chat session:', error);
    }
}

/**
 * Handles the creation of a new chat session.
 * Prevents the default form/button behavior,
 * clears the current chat area,
 * adjusts the textarea position,
 * resets the chat list buttons,
 * and creates a new session key asynchronously.
 * @param {Event} event - The event triggered by user interaction.
 */
async function createNewChat(event) {
    event.preventDefault();

    cleanChatArea();       // Clear chat messages and UI elements

    moveUpTextArea();      // Adjust textarea position (e.g., move it up)

    resetChatListButtons(); // Reset styles and states of chat session buttons

    await createSessionKey(); // Generate and set a new session ID asynchronously
}


/**
 * Sends a POST request to clean all stored chat sessions,
 * then clears the chat list UI and resets the chat input area.
 * @param {Event} event - The event triggered by user interaction.
 */
async function cleanHistory(event) {
    event.preventDefault();

    try {
        const res = await fetch('/chatLLM/cleanChats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await res.json();

        if (!data.success) {
            console.error('Failed to clean chats:', data.message);
            return;
        }

        // Clear the chat list container in the UI
        const chatList = document.getElementById('chat-list');
        if (chatList) {
            chatList.innerHTML = '';
        }

        await createSessionKey();

        cleanChatArea();       // Clear the current chat messages (if defined)
        moveUpTextArea();  // Adjust textarea position after clearing
    } catch (error) {
        console.error('Error cleaning chat history:', error);
    }
}


/**
 * Clears all chat messages from the chat area in the UI.
 */
function cleanChatArea() {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = '';
}


/**
 * Handles the send button click event.
 * Prevents the default form submission behavior,
 * retrieves and trims the input text,
 * and sends the message if the input is not empty.
 * 
 * @param {Event} event - The click event object.
 */
function handleClickSendButton(event) {
    event.preventDefault();

    const textArea = document.getElementById('textarea');
    const text = textArea.value.trim(); // Remove whitespace from both ends of the input text

    if (text === "") {
        return; // Do nothing if input is empty
    }

    sendMessageToLLM(text);    
}


/**
 * Handles the microphone button click event to start speech recognition.
 * Uses the Web Speech API to capture spoken words and sends the transcript as a message.
 * 
 * @param {Event} event - The click event object.
 */
function handleClickMic(event) {
    event.preventDefault();

    // Get the SpeechRecognition interface depending on the browser
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    // Alert user if speech recognition is not supported
    if (!SpeechRecognition) {
        alert("Sorry, your browser does not support speech recognition.");
        return;
    }

    // Create a new SpeechRecognition instance
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';          // Set recognition language
    recognition.interimResults = false;  // Only return final results
    recognition.maxAlternatives = 1;     // Return only the top result

    recognition.start(); // Start listening for speech input

    // When speech is recognized, extract transcript and send as message
    recognition.addEventListener('result', (event) => {
        const transcript = event.results[0][0].transcript;
        sendMessageToLLM(transcript);
    });

    // Stop recognition when speech input ends
    recognition.addEventListener('speechend', () => {
        recognition.stop();
    });

    // Handle recognition errors
    recognition.addEventListener('error', (event) => {
        alert("Voice recognition error!");
        console.error("Recognition error:", event.error);
    });
}


/**
 * Moves and styles the text area and related elements to a centered, compact layout.
 */
function moveUpTextArea() {
    const textArea = document.getElementById('textarea');
    const subTile = document.getElementById('subTitle');
    const messageArea = document.getElementById('messages');
    const container = document.getElementById('container');
    const chatArea = document.getElementById('chatArea');

    subTile.style.display = 'block';
    messageArea.style.display = 'none';
    container.style.marginTop = '30px';
    container.style.marginBottom = '0px';
    chatArea.style.justifyContent = 'center'
    textArea.value = '';

    TEXTAREACENTERED = true;

    textAreaResize();
}

/**
 * Resets the text area and related elements to their default layout and styles, expanding the message area.
 */
function moveDownTextArea() {
    const textArea = document.getElementById('textarea');
    const subTile = document.getElementById('subTitle');
    const chatArea = document.getElementById('chatArea');
    const messageArea = document.getElementById('messages');
    const container = document.getElementById('container');

    subTile.style.display = 'none';
    messageArea.style.display = 'flex';
    messageArea.style.height = '80%';
    messageArea.style.marginTop = '5px';
    container.style.marginTop = '5px';
    container.style.marginBottom = '5px';
    chatArea.style.justifyContent = 'normal';
    textArea.value = '';

    TEXTAREACENTERED = false;

    textAreaResize();
}

/**
 * Disables both the send button and the microphone button to prevent user input.
 */
function disableSendButtons(){
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');

    sendButton.disabled = true;
    micButton.disabled = true;
}

/**
 * Enables both the send button and the microphone button to allow user input.
 */
function activateSendButtons(){
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');

    sendButton.disabled = false;
    micButton.disabled = false;
}

/**
 * Automatically adjusts the height of the textarea to fit its content,
 * preventing scrollbars and improving user experience while typing.
 */
function textAreaResize(){
    const textArea = document.getElementById('textarea');
    textArea.style.height = 'auto';
    textArea.style.height = (textArea.scrollHeight) + 'px';
}

/**
 * Adds a chat message to the messages container.
 * The message is styled with a class based on the sender type:
 * 'user' for messages sent by the user,
 * 'assistantAI' for messages sent by the AI assistant.
 * @param {string} text - The message text to display.
 * @param {string} type - The sender type ('user' or 'assistantAI').
 */
function addMessage(text, type) {
    const messages = document.getElementById('messages');
    const message = document.createElement('div');
    message.classList.add('message', type);  // Apply class based on sender type
    message.textContent = text;
    messages.append(message);
}

/**
 * Converts the given text to speech using the Web Speech API.
 * Configures language, speed, pitch, and volume before speaking.
 * @param {string} text - The text to be spoken aloud.
 */
function textToSpeech(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1;       // Normal speaking speed
    utterance.pitch = 1;      // Normal pitch
    utterance.volume = 1;     // Maximum volume

    speechSynthesis.speak(utterance);
}

/**
 * Creates and inserts a chat session button into the chat list.
 * The button is labeled with the current SESSION_ID and triggers loading of the chat when clicked.
 */
function createChatButton(session_id, date, activate) {
    const container = document.getElementById('chat-list');

    const button = document.createElement('button');
    button.id = session_id;
    button.textContent = date;
    button.className = 'chat-item';

    if(activate){
        button.style.backgroundColor = 'lightgrey';
        button.disabled = true;
    }
    else{
        button.style.backgroundColor = '';
        button.disabled = false;
    }

    // Set up the click event to load the chat
    button.addEventListener('click', () => {
        loadChat(session_id);  // Function that loads the chat content
    });

    // Insert the new button at the top of the chat list
    container.insertBefore(button, container.firstChild);
}

/**
 * Formats an ISO datetime string into a human-readable short date and time.
 * Returns 'Unknown Date' if the input is falsy or a default empty date string.
 * 
 * @param {string} date - The ISO datetime string to format.
 * @returns {string} - Formatted date and time string or 'Unknown Date' if invalid.
 */
function formatDate(date) {
    if (!date || date === '0001-01-01T00:00:00') return 'Unknown Date';
    const d = new Date(date);
    return d.toLocaleString(undefined, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}


/**
 * Clears all highlights and enables all buttons within the chat list container.
 * It resets the background color and enables any disabled buttons.
 */
function resetChatListButtons() {
    const container = document.getElementById('chat-list');
    const children = container.children;  // HTMLCollection of all child elements

    for (const child of children) {
        child.style.backgroundColor = '';  // Remove background highlight
        child.disabled = false;             // Enable the button if it is disableable (e.g., <button>)
    }
}