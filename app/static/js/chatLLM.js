SESSION_KEY = 0

document.addEventListener('DOMContentLoaded', async () => {
    let textArea = document.getElementById('textarea');
    let form = document.getElementById('form');

    textArea.addEventListener('input', () => textAreaResize(textArea));

    form.addEventListener('submit', (event) => submitButton(event));

    SESSION_KEY = await createSessionKey();
});

async function createSessionKey() {
    const res = await fetch('/chatLLM/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    return data.session_id;
}

function moveDownTextArea() {
    const textArea = document.getElementById('textarea');
    const subTile = document.getElementById('subTitle');
    const chatArea = document.getElementById('chatArea');
    const messageArea = document.getElementById('messages');
    const container = document.getElementById('container');

    subTile.style.display = 'none'
    messageArea.style.display = 'flex'
    messageArea.style.height = '85%'
    messageArea.style.marginTop = '5px'
    container.style.marginTop = '5px'
    container.style.marginBottom = '5px'
    chatArea.style.justifyContent = 'normal'
    textArea.value = '';

    textAreaResize(textArea);
}

async function submitButton(event){
    event.preventDefault();

    const textArea = document.getElementById('textarea');
    const text = textArea.value.trim(); // trim()-> remove whitespace from the beginning and end of the input text.

    if(text == ""){
        return;
    }

    moveDownTextArea();
    disableSendButtons();

    addMessage(text, 'sent');

    first_token = true;

    console.log(SESSION_KEY)

    fetch('/chatLLM/sendPrompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, sessionId: SESSION_KEY })
    })
    .then(() => {
        const evtSource = new EventSource('/chatLLM/responseLLM?session_id=' + encodeURIComponent(SESSION_KEY));

        let first_token = true;

        evtSource.onmessage = (e) => {
            if (!e.data) return;  // salta se non arriva nulla
            if (first_token) {
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
            console.error("EventSource failed:", e);
            evtSource.close();
        };
    })
    .catch(err => {
        console.error("Fetch failed:", err);
    });

    activateSendButtons();
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

function textAreaResize(textArea){
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
    return;
}