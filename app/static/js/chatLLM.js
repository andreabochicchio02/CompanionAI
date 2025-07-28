let SESSION_KEY = 0
let N_MESSAGES = 0
let ENABLE_TTS = false;

// Create a MutationObserver to watch for DOM changes
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        // Loop through all nodes that were removed from the DOM
        mutation.removedNodes.forEach((node) => {
            // If the removed node is the 'thinking-dots' element and has an active interval
            if (node.id === 'thinking-dots' && node._dotsInterval) {
                // Stop the dot animation interval when the element is removed
                clearInterval(node._dotsInterval);
            }
        });
    });
}); 

document.addEventListener('DOMContentLoaded', async () => {
    const textArea = document.getElementById('textarea');
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');
    const ttsToggle = document.querySelector('.tts-toggle');
    const newChat = document.getElementById('new-chat');

    // Handle "New Chat" button click
    newChat.addEventListener('click', (event) => createNewChat(event));

    // Automatically resize the message input box as the user types
    textArea.addEventListener('input', () => textAreaResize());

    // Handle message sending based on which button was clicked
    sendButton.addEventListener('click', (event) => handleClickSendButton(event));
    micButton.addEventListener('click', (event) => handleClickMic(event));

    // Send message on Enter key, insert line break on Shift+Enter
    textArea.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            handleClickSendButton(event);
        }
    });

    // Handle the toggle to enable or disable TTS (Text-to-Speech)
    ttsToggle.addEventListener('change', (event) => {ENABLE_TTS = event.target.checked;});

    // Get the session key and automatically start the chat
    SESSION_KEY = await createSessionKey();

    // Start observing message container for changes (e.g. to stop animation)
    observer.observe(document.getElementById('messages'), { childList: true });

    await uploadHistoryChats();
});

async function uploadHistoryChats() {
    try {
        // Richiesta al backend per ottenere la lista dei session ID
        const response = await fetch('/chatLLM/uploadChats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Errore HTTP! Status: ${response.status}`);
        }

        const sessionIds = await response.json();  // È un array ora

        const container = document.getElementById('chat-list');
        if (!container) {
            console.error("Contenitore #chat-list non trovato nel DOM");
            return;
        }

        // Pulisce il contenitore prima di aggiungere nuovi bottoni (opzionale)
        container.innerHTML = '';

        // Crea un bottone per ogni session ID
        sessionIds.forEach(sessionId => {
            const button = document.createElement('button');
            button.id = sessionId;
            button.textContent = sessionId;
            button.className = 'chat-item';
            button.addEventListener('click', () => {
                loadChat(sessionId);  // Funzione che carica i dettagli della chat
            });
            container.appendChild(button);
        });
    } catch (error) {
        console.error('Errore nel recupero o parsing dei session ID:', error);
    }
}

async function loadChat(sessionId) {
    // Rimuovi evidenziazioni e abilita tutti i bottoni
    const container = document.getElementById('chat-list');
    const children = container.children;  // HTMLCollection di tutti i figli

    for (const child of children) {
        child.style.backgroundColor = '';  // rimuovi sfondo
        child.disabled = false;             // abilita se è un elemento disabilitabile (es. button)
    }

    // Evidenzia e disabilita il bottone cliccato
    const activeButton = document.getElementById(sessionId);
    if (activeButton) {
        activeButton.style.backgroundColor = 'lightgrey';
        activeButton.disabled = true;
    }

    try {
        const response = await fetch(`/chatLLM/getChat/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Errore HTTP! Status: ${response.status}`);
        }

        const chat = await response.json();

        if (!chat || !chat.user || !chat.assistantAI) {
            console.warn('Chat non valida o incompleta:', chat);
            return;
        }

        // Pulisci l'interfaccia chat (se vuoi)
        clearChat(); // questa è opzionale, solo se esiste
        moveDownTextArea();

        const userMessages = chat.user;
        const assistantMessages = chat.assistantAI;

        const maxLength = Math.max(userMessages.length, assistantMessages.length);

        N_MESSAGES = maxLength;

        for (let i = 0; i < maxLength; i++) {
            if (userMessages[i]) {
                addMessage(userMessages[i], 'sent');      // messaggio utente
            }
            if (assistantMessages[i]) {
                addMessage(assistantMessages[i], 'received');  // risposta AI
            }
        }
    } catch (error) {
        console.error('Errore nel caricamento della chat:', error);
    }
}

function clearChat(){
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = '';
}

async function createNewChat(event){
    event.preventDefault();

    N_MESSAGES = 0;

    clearChat();

    moveUpTextArea();

    const container = document.getElementById('chat-list');
    const children = container.children;  // HTMLCollection di tutti i figli

    for (const child of children) {
        child.style.backgroundColor = '';  // rimuovi sfondo
        child.disabled = false;             // abilita se è un elemento disabilitabile (es. button)
    }

    const res = await fetch('/chatLLM/newChat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();

    SESSION_KEY = data.session_id;
}

async function createSessionKey() {
    const res = await fetch('/chatLLM/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    return data.session_id;
}

function handleClickSendButton(event){
    event.preventDefault();

    const textArea = document.getElementById('textarea');
    const text = textArea.value.trim(); // trim() -> remove whitespace from the beginning and end of the input text.

    if(text == ""){
        return;
    }

    sendMessageToLLM(text);    
}

function handleClickMic(event) {
    event.preventDefault();

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Sorry, your browser does not support speech recognition.");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.start();

    recognition.addEventListener('result', (event) => {
        const transcript = event.results[0][0].transcript;
        console.log("You said:", transcript);
        sendMessageToLLM(transcript);
    });

    recognition.addEventListener('speechend', () => {
        recognition.stop();
    });

    recognition.addEventListener('error', (event) => {
        alert("Voice recognition error!")
        console.error("Recognition error:", event.error);
    });
}

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

    textAreaResize();
}

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

    textAreaResize();
}

async function sendMessageToLLM(text) {
    if(N_MESSAGES == 0){
        moveDownTextArea();
        N_MESSAGES++;

        const container = document.getElementById('chat-list');
        
        const button = document.createElement('button');
        button.id = SESSION_KEY;
        button.textContent = SESSION_KEY;
        button.className = 'chat-item';
        button.style.backgroundColor = 'lightgrey';
        button.style.disabled = true;
        button.addEventListener('click', () => {
            loadChat(SESSION_KEY);  // Funzione che carica i dettagli della chat
        });
        container.insertBefore(button, container.firstChild);
    }

    disableSendButtons();

    addMessage(text, 'sent');

    // Pulisce la text area dopo l'invio del messaggio
    const textArea = document.getElementById('textarea');
    textArea.value = '';

    // Aggiungi puntini di ragionamento
    addThinkingDots();

    fetch('/chatLLM/sendPrompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, sessionId: SESSION_KEY })
    })
    .then(() => {
        // EventSource ESTABLISHES A PERMANENT ONE-WAY CONNECTION (SERVER - CLIENT) WHERE THE SERVER CAN SEND EVENTS AS THEY BECOME AVAILABLE.
        // PERFECT FOR CHAT WITH PROGRESSIVE RESPONSE, DATA STREAMING
        const evtSource = new EventSource('/chatLLM/responseLLM?session_id=' + encodeURIComponent(SESSION_KEY));

        let first_token = true;

        evtSource.onmessage = (e) => {
            if (!e.data) return;  // salta se non arriva nulla
            if (first_token) {
                removeThinkingDots();
                addMessage(e.data, 'received');
                first_token = false;
            } else {
                const lastMessage = document.getElementById('messages').lastElementChild;
                if (lastMessage) {
                    lastMessage.textContent += e.data;
                }
            }
        };

        evtSource.onerror = (e) => {
            removeThinkingDots();
            if(ENABLE_TTS){
                textToSpeech(document.getElementById('messages').lastElementChild.textContent);
            }
            activateSendButtons();
            console.error("EventSource failed:", e);
            evtSource.close();
        };
    })
    .catch(err => {
        removeThinkingDots();
        console.error("Fetch failed:", err);
    });
}

// Aggiunge un messaggio "sta pensando..." con puntini animati
function addThinkingDots() {
    const messages = document.getElementById('messages');
    const thinking = document.createElement('div');
    thinking.classList.add('message', 'thinking', 'received'); // aggiunta classe received
    thinking.id = 'thinking-dots';
    thinking.textContent = 'I am thinking';
    messages.append(thinking);
    animateDots(thinking);
}

// Rimuove il messaggio "sta pensando..."
function removeThinkingDots() {
    const thinking = document.getElementById('thinking-dots');
    if (thinking) thinking.remove();
}

// Anima i puntini dopo "sta pensando"
function animateDots(element) {
    let dots = 0;
    element._dotsInterval = setInterval(() => {
        dots = (dots + 1) % 4;
        element.textContent = 'I am thinking' + '.'.repeat(dots);
    }, 500);
    element._dotsCount = dots;
}



function disableSendButtons(){
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');

    sendButton.disabled = true;
    micButton.disabled = true;
}

function activateSendButtons(){
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');

    sendButton.disabled = false;
    micButton.disabled = false;
}

function textAreaResize(){
    const textArea = document.getElementById('textarea');
    textArea.style.height = 'auto';
    textArea.style.height = (textArea.scrollHeight) + 'px';
}

function resetTextAreaPosition() {
    const container = document.querySelector('.container');
    container.style.transform = 'translateY(0)';
}

function addMessage(text, type) {
    const messages = document.getElementById('messages');
    const message = document.createElement('div');
    message.classList.add('message', type);
    message.textContent = text;
    messages.append(message);
}

function textToSpeech(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1;       // speed (1 = normal)
    utterance.pitch = 1;      // pitch (1 = normal)
    utterance.volume = 1;     // volume (0 to 1)

    speechSynthesis.speak(utterance);
}