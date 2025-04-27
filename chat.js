let chats = {};
let currentChatId = null;
let recognition;
let isListening = false;

window.onload = function () {
    const saved = localStorage.getItem('ollama_chats');
    if (saved) {
        chats = JSON.parse(saved);
        const ids = Object.keys(chats);
        if (ids.length > 0) {
            currentChatId = ids[0];
            populateChatList();
            loadChat();
        }
    }

    const darkMode = localStorage.getItem('dark_mode');
    if (darkMode === 'true') {
        document.body.classList.add('dark');
    }

    const promptInput = document.getElementById('prompt');
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendPrompt();
        }
    });

    // Setup voice recognition
    if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
        recognition.continuous = true; // <<< 🔥 KEEPS LISTENING
        recognition.interimResults = true; // <<< 🔥 Show live text
        recognition.lang = 'en-US';
    
        recognition.onresult = (event) => {
            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                }
            }
            document.getElementById('prompt').value = finalTranscript;
        };
    
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            stopListening();
        };
    
        recognition.onend = () => {
            isListening = false;
            updateMicButton();
        };
    }
    
};

async function sendPrompt() {
    const promptInput = document.getElementById('prompt');
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    if (!currentChatId || !chats[currentChatId]) {
        newChat();
        showToast("✨ New chat started!");
    }

    addMessage(prompt, 'user');
    chats[currentChatId].messages.push({ text: prompt, sender: 'user' });
    chats[currentChatId].updated = new Date().toISOString();
    saveChats();

    promptInput.value = '';

    const loadingId = "loading-" + Date.now();
    addLoadingMessage(loadingId);

    try {
        const res = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });

        const data = await res.json();
        const botReply = data.response;

        removeLoadingMessage(loadingId);
        addMessage(botReply, 'bot');
        speak(botReply);

        chats[currentChatId].messages.push({ text: botReply, sender: 'bot' });
        chats[currentChatId].updated = new Date().toISOString();
        saveChats();

        if (chats[currentChatId].messages.length === 2) {
            generateChatTitle(currentChatId);
        }
    } catch (error) {
        console.error('Error fetching bot reply:', error);
        removeLoadingMessage(loadingId);
        addMessage("❌ Error connecting to server.", 'bot');
    }
}

async function generateChatTitle(chatId) {
    const conversation = chats[chatId].messages
        .map(msg => `${msg.sender === 'user' ? "User:" : "Bot:"} ${msg.text}`)
        .join("\n");

    try {
        const res = await fetch('http://localhost:8000/title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversation })
        });
        const data = await res.json();

        const title = data.response.trim().replace(/^"|"$/g, '');

        if (title) {
            chats[chatId].name = title;
            chats[chatId].updated = new Date().toISOString();
            saveChats();
            populateChatList();
        }
    } catch (error) {
        console.error('Error generating title:', error);
    }
}

function addMessage(text, sender) {
    const chatContainer = document.getElementById('chat-container');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    const formattedText = text
        .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
        .replace(/\*(.+?)\*/g, '<i>$1</i>')
        .replace(/\n/g, '<br>');

    messageDiv.innerHTML = formattedText;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addLoadingMessage(id) {
    const chatContainer = document.getElementById('chat-container');
    const loadingDiv = document.createElement('div');
    loadingDiv.classList.add('message', 'bot', 'loading');
    loadingDiv.setAttribute('id', id);
    loadingDiv.innerHTML = `<span class="dot"></span><span class="dot"></span><span class="dot"></span>`;
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeLoadingMessage(id) {
    const loadingDiv = document.getElementById(id);
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

function saveChats() {
    localStorage.setItem('ollama_chats', JSON.stringify(chats));
}

function loadChat() {
    const chatContainer = document.getElementById('chat-container');
    chatContainer.innerHTML = '';

    if (!currentChatId || !chats[currentChatId] || chats[currentChatId].messages.length === 0) {
        const greeting = document.createElement('div');
        greeting.classList.add('message', 'bot');
        greeting.innerHTML = "👋 Hello, I am Zeus.";
        chatContainer.appendChild(greeting);
        return;
    }

    chats[currentChatId].messages.forEach(msg => addMessage(msg.text, msg.sender));
}

function populateChatList() {
    const chatList = document.getElementById('chat-list');
    chatList.innerHTML = '';

    for (let id in chats) {
        const chatWrapper = document.createElement('div');
        chatWrapper.classList.add('chat-entry');

        const chatDiv = document.createElement('div');
        chatDiv.classList.add('chat-name');
        chatDiv.textContent = chats[id].name || `Chat ${id.slice(-5)}`;
        chatDiv.dataset.chatId = id;

        chatDiv.onclick = function () {
            currentChatId = this.dataset.chatId;
            loadChat();
            highlightActiveChat();
        };

        chatDiv.ondblclick = function (e) {
            e.stopPropagation();
            const input = document.createElement('input');
            input.type = 'text';
            input.value = chats[id].name || '';
            input.classList.add('chat-rename-input');
            chatDiv.replaceWith(input);
            input.focus();

            input.onblur = saveRename;
            input.onkeydown = function (e) {
                if (e.key === 'Enter') saveRename();
            };

            function saveRename() {
                const newName = input.value.trim();
                if (newName) {
                    chats[id].name = newName;
                    chats[id].updated = new Date().toISOString();
                    saveChats();
                    populateChatList();
                } else {
                    populateChatList();
                }
            }
        };

        const deleteBtn = document.createElement('button');
        deleteBtn.classList.add('delete-btn');
        deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
        deleteBtn.onclick = function (e) {
            e.stopPropagation();
            deleteChat(id);
        };

        chatWrapper.appendChild(chatDiv);
        chatWrapper.appendChild(deleteBtn);
        chatList.appendChild(chatWrapper);
    }

    highlightActiveChat();
}

function highlightActiveChat() {
    const chatList = document.getElementById('chat-list').children;
    for (let chat of chatList) {
        if (chat.querySelector('.chat-name').dataset.chatId === currentChatId) {
            chat.classList.add('active-chat');
        } else {
            chat.classList.remove('active-chat');
        }
    }
}

function newChat() {
    const newId = Date.now().toString();
    chats[newId] = {
        name: "New Chat",
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        messages: []
    };
    currentChatId = newId;
    saveChats();
    populateChatList();
    loadChat();
}

function deleteCurrentChat() {
    if (!currentChatId) return;
    if (!confirm('Are you sure you want to delete this chat?')) return;
    delete chats[currentChatId];
    saveChats();
    const ids = Object.keys(chats);
    currentChatId = ids.length > 0 ? ids[0] : null;
    populateChatList();
    loadChat();
}

function deleteChat(chatId) {
    delete chats[chatId];
    saveChats();
    const ids = Object.keys(chats);
    currentChatId = ids.length > 0 ? ids[0] : null;
    populateChatList();
    loadChat();
}

function showToast(message) {
    const toastContainer = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// 🎙️ MIC functions
function startListening() {
    if (!recognition) return;
    if (isListening) {
        recognition.stop();
        isListening = false;
    } else {
        recognition.start();
        isListening = true;
    }
    updateMicButton();
}

function updateMicButton() {
    const micBtn = document.getElementById('mic-btn');
    micBtn.innerText = isListening ? "🛑" : "🎙️";
}

// 🔈 Text to Speech
// function speak(text) {
//     const utterance = new SpeechSynthesisUtterance(text);
//     utterance.lang = 'en-US';
//     utterance.rate = 1.0;
//     speechSynthesis.speak(utterance);
// }
// if ('webkitSpeechRecognition' in window) {
//     recognition = new webkitSpeechRecognition();
//     recognition.continuous = true; // <<< 🔥 KEEPS LISTENING
//     recognition.interimResults = true; // <<< 🔥 Show live text
//     recognition.lang = 'en-US';

//     recognition.onresult = (event) => {
//         let finalTranscript = '';
//         for (let i = event.resultIndex; i < event.results.length; ++i) {
//             const transcript = event.results[i][0].transcript;
//             if (event.results[i].isFinal) {
//                 finalTranscript += transcript;
//             }
//         }
//         document.getElementById('prompt').value = finalTranscript;
//     };

//     recognition.onerror = (event) => {
//         console.error('Speech recognition error:', event.error);
//         stopListening();
//     };

//     recognition.onend = () => {
//         isListening = false;
//         updateMicButton();
//     };
// }
