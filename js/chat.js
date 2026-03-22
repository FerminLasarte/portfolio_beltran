/**
 * chat.js — Briones Chatbot Widget
 * Vanilla JS · Gemini AI via FastAPI
 */

const CHAT_API_URL = 'https://printed-berna-ferminlasarte-809f4608.koyeb.app/api/chat';

// Conversation history kept on the client; sent with each request so the
// model has context. Capped at 20 messages (10 exchanges) to control tokens.
let chatHistory = [];
let isOpen      = false;
let isSending   = false;

// ── DOM refs (resolved after DOMContentLoaded) ────────────────────────────

let fabBtn, chatWindow, chatMessages, chatInput, sendBtn, closeBtn, inputWrapper;

// ── Open / Close ─────────────────────────────────────────────────────────────

function openChat() {
  isOpen = true;
  chatWindow.classList.remove('chat-closed');
  chatWindow.classList.add('chat-open');
  fabBtn.setAttribute('aria-label', window.bb_t('chat.close_aria'));
  fabBtn.querySelector('.fab-icon-open').classList.add('hidden');
  fabBtn.querySelector('.fab-icon-close').classList.remove('hidden');
  // Stop pulsing ring once user interacts
  fabBtn.querySelector('.fab-ring')?.classList.remove('animate-ping');
  setTimeout(() => chatInput.focus(), 350);
}

function closeChat() {
  isOpen = false;
  chatWindow.classList.remove('chat-open');
  chatWindow.classList.add('chat-closed');
  fabBtn.setAttribute('aria-label', window.bb_t('chat.open_aria'));
  fabBtn.querySelector('.fab-icon-open').classList.remove('hidden');
  fabBtn.querySelector('.fab-icon-close').classList.add('hidden');
}

function toggleChat() {
  isOpen ? closeChat() : openChat();
}

// ── Message rendering ─────────────────────────────────────────────────────────

/**
 * Convert basic markdown to HTML so the bot can use **bold** and line breaks.
 * Intentionally minimal — no XSS risk since we never set raw user input as HTML.
 */
function formatText(raw) {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

function appendMessage(role, text) {
  const isUser = role === 'user';

  const wrapper = document.createElement('div');
  wrapper.className = `chat-msg flex ${isUser ? 'justify-end' : 'justify-start'}`;

  const bubble = document.createElement('div');
  bubble.className = isUser ? 'chat-bubble-user' : 'chat-bubble-bot';
  bubble.innerHTML = formatText(text);

  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
}

function showTypingIndicator() {
  const wrapper = document.createElement('div');
  wrapper.id = 'chat-typing';
  wrapper.className = 'chat-msg flex justify-start';
  wrapper.innerHTML = `
    <div class="chat-bubble-bot" style="padding: 0.75rem 1rem;">
      <div class="flex items-center gap-1.5">
        <span class="typing-dot" style="animation-delay:0s;"></span>
        <span class="typing-dot" style="animation-delay:0.18s;"></span>
        <span class="typing-dot" style="animation-delay:0.36s;"></span>
      </div>
    </div>
  `;
  chatMessages.appendChild(wrapper);
  scrollToBottom();
}

function removeTypingIndicator() {
  document.getElementById('chat-typing')?.remove();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Send logic ────────────────────────────────────────────────────────────────

function setSendState(sending) {
  isSending = sending;
  sendBtn.disabled = sending || chatInput.value.trim() === '';
  chatInput.disabled = sending;
  if (sending) {
    inputWrapper.style.opacity = '0.65';
  } else {
    inputWrapper.style.opacity = '1';
    chatInput.focus();
  }
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || isSending) return;

  chatInput.value = '';
  sendBtn.disabled = true;
  setSendState(true);

  // Render user bubble immediately
  appendMessage('user', text);

  // Optimistically push to history; we'll push the model reply on success
  chatHistory.push({ role: 'user', text });

  // Trim history to last 20 messages (10 exchanges) before sending
  const historyToSend = chatHistory.slice(-20, -1); // exclude the message just added

  showTypingIndicator();

  try {
    const res = await fetch(CHAT_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: historyToSend,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    removeTypingIndicator();

    appendMessage('model', data.response);
    chatHistory.push({ role: 'model', text: data.response });

    // Hard cap on stored history
    if (chatHistory.length > 20) {
      chatHistory = chatHistory.slice(-20);
    }

  } catch (err) {
    removeTypingIndicator();

    const isNetworkError = err instanceof TypeError;
    const fallback = isNetworkError
      ? window.bb_t('chat.error_network')
      : window.bb_t('chat.error_generic');

    appendMessage('model', fallback);
    // Remove the optimistic user entry from history since we couldn't process it
    chatHistory.pop();

    console.error('[Briones Chat]', err);
  } finally {
    setSendState(false);
  }
}

// ── Quick-reply chips ─────────────────────────────────────────────────────────

function getQuickReplies() {
  return [
    window.bb_t('chat.quick1'),
    window.bb_t('chat.quick2'),
    window.bb_t('chat.quick3'),
    window.bb_t('chat.quick4'),
  ];
}

function renderQuickReplies() {
  // Remove existing chips if any (e.g. on language change)
  document.getElementById('chat-quick-replies')?.remove();

  const container = document.createElement('div');
  container.id = 'chat-quick-replies';
  container.className = 'flex flex-wrap gap-2 px-4 pb-3';

  getQuickReplies().forEach((label) => {
    const chip = document.createElement('button');
    chip.className = 'chat-chip';
    chip.textContent = label;
    chip.addEventListener('click', () => {
      container.remove();
      chatInput.value = label;
      sendMessage();
    });
    container.appendChild(chip);
  });

  chatMessages.after(container);
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  fabBtn       = document.getElementById('chat-fab');
  chatWindow   = document.getElementById('chat-window');
  chatMessages = document.getElementById('chat-messages');
  chatInput    = document.getElementById('chat-input');
  sendBtn      = document.getElementById('chat-send');
  closeBtn     = document.getElementById('chat-close');
  inputWrapper = document.getElementById('chat-input-wrapper');

  if (!fabBtn || !chatWindow) return; // widget not present on this page

  // Events
  fabBtn.addEventListener('click', toggleChat);
  closeBtn.addEventListener('click', closeChat);
  sendBtn.addEventListener('click', sendMessage);

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Enable/disable send button reactively
  chatInput.addEventListener('input', () => {
    sendBtn.disabled = chatInput.value.trim() === '' || isSending;
  });

  /*
   * Mobile keyboard fix
   * ───────────────────────────────────────────────────
   * When the virtual keyboard opens on iOS/Android it
   * shrinks the visual viewport. Combined with the dvh-
   * based window height in CSS, the window resizes
   * automatically. We also scroll messages to the bottom
   * so the last message stays visible above the input.
   *
   * A 350ms delay matches the average keyboard animation
   * duration on both platforms.
   * ───────────────────────────────────────────────────
   */
  chatInput.addEventListener('focus', () => {
    if (window.innerWidth < 640) {
      setTimeout(() => {
        scrollToBottom();
        // Scroll the input wrapper into view inside the fixed panel
        chatInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 350);
    }
  });

  // Render quick reply chips
  renderQuickReplies();

  // Re-render chips when language changes (only if chat was not yet used)
  window.addEventListener('langchange', () => {
    if (document.getElementById('chat-quick-replies')) {
      renderQuickReplies();
    }
  });
});
