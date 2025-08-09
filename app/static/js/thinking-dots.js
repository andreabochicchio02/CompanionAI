// Create a MutationObserver to detect when the "thinking-dots" element is removed
// and stop its animation interval to prevent memory leaks
export const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.removedNodes.forEach((node) => {
            if (node.id === 'thinking-dots' && node._dotsInterval) {
                clearInterval(node._dotsInterval); // Stop animation interval
            }
        });
    });
});

/**
 * Adds a "thinking..." message with animated dots to the chat interface.
 * This simulates the assistant processing a response.
 */
export function addThinkingDots() {
    const messages = document.getElementById('messages');
    const thinking = document.createElement('div');
    thinking.classList.add('thinking');
    thinking.id = 'thinking-dots';
    thinking.textContent = 'I am thinking';
    messages.append(thinking);
    animateDots(thinking);
}

/**
 * Removes the "thinking..." message from the chat interface.
 */
export function removeThinkingDots() {
    const thinking = document.getElementById('thinking-dots');
    if (thinking) thinking.remove();
}

/**
 * Animates the dots in the "I am thinking..." message, adding 1 to 3 dots in a loop.
 * @param {HTMLElement} element - The DOM element to animate.
 */
function animateDots(element) {
    let dots = 0;
    element._dotsInterval = setInterval(() => {
        dots = (dots + 1) % 4; // Cycle through 0 to 3 dots
        element.textContent = 'I am thinking' + '.'.repeat(dots);
    }, 500);
    element._dotsCount = dots; // Store current dot count (optional)
}