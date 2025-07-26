let SESSION_KEY = 0
let N_MESSAGES = 0
let ENABLE_TTS = false;

document.addEventListener('DOMContentLoaded', async () => {
    const textArea = document.getElementById('textarea');
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');
    const ttsToggle = document.querySelector('.tts-toggle');
    const form = document.getElementById('form');

    textArea.addEventListener('input', () => textAreaResize());

    sendButton.addEventListener('click', (event) => handleClickButton(event));
    micButton.addEventListener('click', (event) => handleClickMic(event));
    ttsToggle.addEventListener('change', (event) => handleTTSToggle(event));

    // Invio con Enter, a capo con Shift+Enter
    textArea.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessageToLLM(textArea.value.trim());
        }
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        sendMessageToLLM(textArea.value.trim());
    });

    // Cancella la cronologia della memoria della chat
    await fetch('/chatLLM/clearMemory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });

    // Ottieni la chiave di sessione e poi avvia la chat automaticamente
    SESSION_KEY = await createSessionKey();
    
    // Mostra subito la UI come se avessimo già inviato un messaggio
    moveDownTextArea();
    N_MESSAGES++;
});

function handleTTSToggle(event) {
    ENABLE_TTS = event.target.checked;
}

async function createSessionKey() {
    const res = await fetch('/chatLLM/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    return data.session_id;
}

function handleClickButton(event){
    event.preventDefault();

    const textArea = document.getElementById('textarea');
    const text = textArea.value.trim(); // trim()-> remove whitespace from the beginning and end of the input text.

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

// Ferma l'animazione dei puntini quando l'elemento viene rimosso
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.removedNodes.forEach((node) => {
            if (node.id === 'thinking-dots' && node._dotsInterval) {
                clearInterval(node._dotsInterval);
            }
        });
    });
});
observer.observe(document.getElementById('messages'), { childList: true });

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