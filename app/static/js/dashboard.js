document.addEventListener('DOMContentLoaded', async () => {
    const closePopupBtn = document.getElementById('close-btn');
    const closePersonalInfoPopupBtn = document.getElementById('close-personal-info-btn');
    const closeEventPopupBtn = document.getElementById('close-event-popup-btn');
    const newEventBtn = document.getElementById('new-event-btn');
    const personalInfoBtn = document.getElementById('personal-info-btn');
    const showEventPopupBtn = document.getElementById('show-event-popup-btn');

    closePopupBtn.addEventListener('click', (event) => closeChatPopup(event));
    closePersonalInfoPopupBtn.addEventListener('click', (event) => closePersonalInfoPopup(event));
    closeEventPopupBtn.addEventListener('click', (event) => closeEventPopup(event));

    newEventBtn.addEventListener('click', (event) => {addNewEvent(event);});

    personalInfoBtn.addEventListener('click', showPersonalInfoPopUp);
    showEventPopupBtn.addEventListener('click', showEventPopup);

    await renderEvents();
    
    await uploadHistoryChats();
});

function showEventPopup(){
    document.getElementById('overlay').classList.remove('hidden');
    document.getElementById('add-event-popup').classList.remove('hidden');
}

function closeEventPopup(event){
    event.preventDefault();
    document.getElementById('overlay').classList.add('hidden');
    document.getElementById('add-event-popup').classList.add('hidden');
}

function closePersonalInfoPopup(event){
    event.preventDefault();
    document.getElementById('overlay').classList.add('hidden');
    document.getElementById('personal-info-popup').classList.add('hidden');
}

function showPersonalInfoPopUp(){
    document.getElementById('overlay').classList.remove('hidden');
    document.getElementById('personal-info-popup').classList.remove('hidden');
}

async function addNewEvent(event) {
    event.preventDefault();

    const title = document.getElementById('title').value;
    const date = document.getElementById('date').value;
    const note = document.getElementById('note').value;
    const frequency = document.getElementById('recurrence').value;
    const recurrenceEnd = document.getElementById('recurrence-end').value;

    const newEvent = {
        title,
        date,
        note,
        recurrence: frequency ? { frequency, end: recurrenceEnd || null } : null
    };

    try {
        const response = await fetch('/dashboard/addNewEvent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(newEvent)
        });

        const data = await response.json();

        if (!data.success) {
            console.error('Server error:', data.message);
            return;
        }

        console.log('Event added successfully:', data.message);
        renderEvents();

    } catch (error) {
        console.error('Fetch error:', error);
    }
}

function addEventToList(event, index) {
    const eventsOutput = document.getElementById('events-output');

    const div = document.createElement('div');
    div.className = 'event-item';

    const content = document.createElement('div');
    content.className = 'event-content';
    content.innerHTML = '<strong>' + event.title + '</strong><br>' + new Date(event.date).toLocaleString() + '<br>' + '<em>' + event.note + '</em>';

    if (event.recurrence) {
        const freq = event.recurrence.frequency;
        const endDate = event.recurrence.end ? new Date(event.recurrence.end).toLocaleDateString() : 'no end';

        const recurrenceInfo = '<br><span class="event-recurrence">Repeats every ' + freq +
        (event.recurrence.days_of_week ? ' (' + event.recurrence.days_of_week.join(', ') + ')' : '') + ' until ' + endDate + '</span>';

        content.innerHTML += recurrenceInfo;
    }

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-btn';
    deleteBtn.textContent = '🗑️';
    deleteBtn.title = 'Delete event';
    deleteBtn.addEventListener('click', () => {
        deleteEvent(index);
    });

    div.appendChild(content);
    div.appendChild(deleteBtn);
    eventsOutput.appendChild(div);
}

async function renderEvents() {
    const eventsOutput = document.getElementById('events-output');
    eventsOutput.innerHTML = '';

    try {
        const response = await fetch('/dashboard/getEvents', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!data.success) {
            console.error('Error from server:', data.message);  
            return;
        }

        const events = data.message;
        const sorted = [...events].sort(function (a, b) {return new Date(a.date) - new Date(b.date);});

        sorted.forEach((event, index) => {
            addEventToList(event, index);
        });

    } catch (error) {
        console.error('Fetch error:', error);
    }
}


function deleteEvent(index) {
  if (confirm('Are you sure you want to delete this event?')) {
    rawEvents.splice(index, 1);
    renderEvents();
  }
}

/**
 * Fetches the list of chat sessions from the backend,
 * then populates the #chat-list container with buttons labeled by their timestamp.
 * Clicking a button loads the corresponding chat session.
 */
export async function uploadHistoryChats() {
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

        console.log(data);

        const userMessages = data.message.user;
        const assistantMessages = data.message.assistantAI;
        const maxLength = Math.max(userMessages.length, assistantMessages.length);

        const popupMessages = document.getElementById('messages');
        popupMessages.innerHTML = ''; // Reset

        for (let i = 0; i < maxLength; i++) {
            if (userMessages[i]) {
                addMessage(userMessages[i], 'user');
            }
            if (assistantMessages[i]) {
                addMessage(assistantMessages[i], 'assistantAI');
            }
        }

        document.getElementById('overlay').classList.remove('hidden');
        document.getElementById('chat-popup').classList.remove('hidden');

    } catch (error) {
        console.error('Error loading chat session:', error);
    }
}

function closeChatPopup(event) {
    event.preventDefault();
    resetChatListButtons();
    document.getElementById('overlay').classList.add('hidden');
    document.getElementById('chat-popup').classList.add('hidden');
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
    message.style.whiteSpace = "pre-line";
    messages.append(message);
}