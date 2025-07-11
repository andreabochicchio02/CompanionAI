document.addEventListener('DOMContentLoaded', () => {
    let textArea = document.getElementById('textarea');
    let form = document.getElementById('form');

    textArea.addEventListener('input', () => textAreaResize(textArea));

    form.addEventListener('submit', (event) => submitButton(event));
});

async function submitButton(event){
    event.preventDefault();

    let textArea = document.getElementById('textarea');
    let subTile = document.getElementById('subTitle');
    let chatArea = document.getElementById('chatArea');
    let messageArea = document.getElementById('messages');
    let container = document.getElementById('container');
    
    const text = textArea.value.trim(); // trim()-> remove whitespace from the beginning and end of the input text.

    if (text !== "") {
        subTile.style.display = 'none'
        messageArea.style.display = 'flex'
        messageArea.style.height = '85%'
        messageArea.style.marginTop = '5px'
        container.style.marginTop = '5px'
        container.style.marginBottom = '5px'
        chatArea.style.justifyContent = 'normal'
        textArea.value = '';
        textAreaResize(textArea);
        addMessage(text, 'sent', 0);

        first_token = true;

        fetch('/chatLLM/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: text })
        })
        .then(res => res.json())
        .then(data => {
            const sessionId = data.session_id;
            const evtSource = new EventSource('/chatLLM/responseLLM?session=' + encodeURIComponent(sessionId));

            evtSource.onmessage = (e) => {
                if(first_token){
                    addMessage(e.data, 'received', sessionId);
                }
                else{
                    const message = document.getElementById('' + sessionId);
                    message.textContent = message.textContent + e.data;
                }

                first_token = false;
            }
            evtSource.onerror = (e) => {
                console.error("EventSource failed:", e);
                evtSource.close();
            };
        });
    }
}

function sendPrompt() {
    const prompt = document.getElementById('prompt').value;
    document.getElementById('output').textContent = ''; // clear previous response

    const evtSource = new EventSource('/chatLLM/responseLLM?prompt=' + encodeURIComponent(prompt));

    evtSource.onmessage = (e) => {
    document.getElementById('output').textContent += e.data;
    };

    evtSource.onerror = (e) => {
    console.error("EventSource failed:", e);
    evtSource.close();
    };
}

function textAreaResize(textArea){
    textArea.style.height = 'auto';
    textArea.style.height = (textArea.scrollHeight) + 'px';
}

function resetTextAreaPosition() {
    const container = document.querySelector('.container');
    container.style.transform = 'translateY(0)';
}

function addMessage(text, type, sessionId) {
    const messages = document.getElementById('messages');
    const message = document.createElement('div');
    message.classList.add('message', type);
    message.textContent = text;
    if(type == 'received'){
        message.id = '' + sessionId;
    }
    messages.append(message);
    return;
}