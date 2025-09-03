// Event listener for DOMContentLoaded
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

    personalInfoBtn.addEventListener('click', (event) => {showPersonalInfoPopUp(event);});
    showEventPopupBtn.addEventListener('click', showEventPopup);

    await renderEvents();
    
    await uploadHistoryChats();
});

/**
 * Shows the event creation popup.
 */
function showEventPopup(){
    document.getElementById('overlay').classList.remove('hidden');
    document.getElementById('add-event-popup').classList.remove('hidden');
}

/**
 * Closes the event creation popup.
 * @param {*} event 
 */
function closeEventPopup(event){
    event.preventDefault();
    document.getElementById('overlay').classList.add('hidden');
    document.getElementById('add-event-popup').classList.add('hidden');
}

/**
 * Closes the personal information popup.
 * @param {*} event 
 */
function closePersonalInfoPopup(event){
    event.preventDefault();
    document.getElementById('overlay').classList.add('hidden');
    document.getElementById('personal-info-popup').classList.add('hidden');
}

/**
 * Shows the personal information popup.
 * @param {*} event 
 */
async function showPersonalInfoPopUp(event){
    event.preventDefault();

    document.getElementById('overlay').classList.remove('hidden');
    document.getElementById('personal-info-popup').classList.remove('hidden');

    try {
        const response = await fetch('/dashboard/getParagraphs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if(!data.success){
            console.error('Errore nella risposta:', data.message);
            return;
        }

        const form = document.getElementById('bio-form');
        form.innerHTML = '';

        const label = document.createElement("label");
        label.className = "toggle-container";

        const mainText = document.createElement("span");
        mainText.textContent = "User is reliable?";

        const input = document.createElement("input");
        input.type = "checkbox";
        input.className = "reliable-toggle";
        input.id = "reliable-toggle";
        input.checked = data.userReliable;

        const spanSlider = document.createElement("span");
        spanSlider.className = "slider";

        label.appendChild(mainText);
        label.appendChild(input);
        label.appendChild(spanSlider);
        form.appendChild(label);
        
        data.message.forEach(paragraph => {
            const title = paragraph.title;
            const content = paragraph.content;

            const id = title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');

            const label = document.createElement('label');
            label.setAttribute('for', id);
            label.textContent = title;

            const textarea = document.createElement('textarea');
            textarea.id = id;
            textarea.className = 'personal-info-label';
            textarea.value = content;

            form.appendChild(label);
            form.appendChild(textarea);
        });

        const addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.id = 'add-paragraph-btn';
        addButton.textContent = '➕ Add Paragraph';

        addButton.addEventListener('click', () => {
            const newTitle = prompt('Enter the title of the new paragraph:');
            if (newTitle && newTitle.trim() !== '') {
                const title = newTitle;

                const id = title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');

                const label = document.createElement('label');
                label.setAttribute('for', id);
                label.textContent = title;

                const textarea = document.createElement('textarea');
                textarea.id = id;
                textarea.className = 'personal-info-label';

                form.insertBefore(label, addButton);
                form.insertBefore(textarea, addButton);
            }
        });

        form.append(addButton);

        const button = document.createElement('button');
        button.type = 'click';
        button.id = 'submit-personal-info-btn';
        button.textContent = 'Submit Biography Info';
        button.addEventListener('click', (event) => {sendNewBio(event);})
        form.appendChild(button);

    } catch (error) {
        console.error('Errore durante la fetch:', error);
    }
}

/**
 * Sends the new biography information to the server.
 * @param {*} event 
 */
async function sendNewBio(event) {
    event.preventDefault();

    const form = document.getElementById('bio-form');
    const submitButton = document.getElementById('submit-personal-info-btn');

    submitButton.disabled = true;
    submitButton.textContent = 'Processing...';

    const labels = form.querySelectorAll('label[for]');
    const paragraphs = [];

    labels.forEach(label => {
        const textarea = form.querySelector('#' + label.getAttribute('for'));
        if (textarea) {
            paragraphs.push({
                title: label.textContent.trim(),
                content: textarea.value.trim().replace(/(\r?\n){2,}/g, '\n')
            });
        }
    });

    const reliableToggle = document.getElementById('reliable-toggle');
    const isReliable = reliableToggle ? reliableToggle.checked : false;

    try {
        const response = await fetch('/dashboard/saveParagraphs', {
            method: 'POST',
            headers: {
            'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                "paragraphs": paragraphs,
                "reliable": isReliable
            })
        });

        const data = await response.json();

        if (data.success) {
            submitButton.textContent = '✅ Saved!';
            submitButton.style.backgroundColor = '#4CAF50';
            setTimeout(() => {
                closePersonalInfoPopup(event);
            }, 1500);
            //alert('Biography saved successfully!');
        } else {
            alert('Error saving biography: ' + data.message);
            submitButton.disabled = false;
            submitButton.textContent = 'Submit Biography Info';
            submitButton.style.backgroundColor = '';
        }

    } catch (error) {
        console.error('Submission error:', error);
        alert('An error occurred during submission.');
        submitButton.disabled = false;
        submitButton.textContent = 'Submit Biography Info';
        submitButton.style.backgroundColor = '';
    }
}

/**
 * Adds a new event to the calendar.
 * @param {*} event 
 */
async function addNewEvent(event) {
    event.preventDefault();

    const title = document.getElementById('title').value.trim();
    const date = document.getElementById('date').value;         // required 
    const time = document.getElementById('time').value;         // optional
    const note = document.getElementById('note').value.trim();
    const frequency = document.getElementById('recurrence').value;
    const recurrenceEnd = document.getElementById('recurrence-end').value;

    if (!title) {
        alert("To add a new event, you must enter the event title!");
        return;
    }

    if (!date) {
        alert("To add a new event, you must enter the date!");
        return;
    }

    let dateToSave;
    if (time) {
        dateToSave = `${date}T${time}:00`;
    } else {
        dateToSave = date;
    }

    const selectedDate = new Date(dateToSave);
    const now = new Date();
    if (selectedDate < now) {
        alert('The selected date and time must be in the future.');
        return;
    }

    const newEvent = {
        title,
        date: dateToSave,
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

        renderEvents();
        closeEventPopup(event);
        
        document.getElementById('event-form').reset();

    } catch (error) {
        console.error('Fetch error:', error);
    }
}

/**
 * Adds an event to the list of events.
 * @param {*} event 
 * @param {*} index 
 */
function addEventToList(event, index) {
    const eventsOutput = document.getElementById('events-output');

    const div = document.createElement('div');
    div.className = 'event-item';

    const dateObj = new Date(event.date);
    const hasTime = event.date.includes('T');
    const formattedDate = hasTime ? 
            dateObj.toLocaleString()        // show date and time
            : dateObj.toLocaleDateString(); // show only date

    const content = document.createElement('div');
    content.className = 'event-content';
    content.innerHTML = '<strong>' + event.title + '</strong><br>' + formattedDate + (event.note ? '<br><em>' + event.note + '</em>' : '');
    
    if (event.recurrence) {
        const freq = event.recurrence.frequency;
        const end = event.recurrence.end;
        let recurrenceText = '';
    
        if (end) {
            const endDate = new Date(end).toLocaleDateString();
            recurrenceText = `Repeats ${freq} until ${endDate}`;
        } else {
            recurrenceText = `Repeats ${freq}`;
        }
    
        const recurrenceInfo = `<br><span class="event-recurrence">${recurrenceText}</span>`;
        content.innerHTML += recurrenceInfo;
    }

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-btn';
    deleteBtn.id = event.id;
    deleteBtn.textContent = '🗑';
    deleteBtn.title = 'Delete event';
    deleteBtn.addEventListener('click', (event) => {
        deleteEvent(event.target);
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

/**
 * Deletes an event from the calendar.
 * @param {*} button 
 */
async function deleteEvent(button) {
    const eventId = button.id;

    if (confirm('Are you sure you want to delete this event?')) {
        try {
            const response = await fetch('/dashboard/deleteEvent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ id: eventId })
            });

            if (response.ok) {
                renderEvents();
            } else {
                console.error('Failed to delete event. Status:', response.status);
            }
        } catch (error) {
            console.error('Network or server error:', error);
        }
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