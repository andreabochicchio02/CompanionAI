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
        addMessage(text, 'sent');

        setTimeout(() => {
            addMessage("Echo: " + text, 'received');
        }, 1000);
    }
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
}