document.addEventListener('DOMContentLoaded', function () {
    var btnGenerate = document.getElementById('btn-generate-ai');
    var btnOpenChat = document.getElementById('btn-open-chat');
    var btnCloseChat = document.getElementById('btn-close-ai');
    var aiPanel = document.getElementById('ai-panel');
    var chatMessages = document.getElementById('ai-chat-messages');
    var chatInput = document.getElementById('ai-chat-input');
    var btnSendChat = document.getElementById('btn-send-chat');

    if (!btnGenerate) return;

    var chatHistory = [];
    var aiAssistUrl = document.getElementById('ai-assist-url').value;

    function getCsrfToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function getTitle() {
        var el = document.getElementById('id_title');
        return el ? el.value : '';
    }

    function getContent() {
        var el = document.getElementById('id_content');
        return el ? el.value : '';
    }

    function getPostType() {
        var el = document.getElementById('ai-post-type');
        return el ? el.value : '';
    }

    // ── Génération de brouillon ──────────────────────────────────────────────

    btnGenerate.addEventListener('click', function () {
        var title = getTitle().trim();
        if (!title) {
            alert('Veuillez saisir un titre avant de générer le contenu.');
            return;
        }

        btnGenerate.disabled = true;
        btnGenerate.textContent = 'Génération en cours…';

        fetch(aiAssistUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                action: 'generate',
                title: title,
                post_type: getPostType(),
            }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.content) {
                    document.getElementById('id_content').value = data.content;
                } else {
                    alert('Erreur : ' + (data.error || 'Réponse inattendue'));
                }
            })
            .catch(function () {
                alert('Erreur lors de la génération. Vérifiez la clé API Mistral.');
            })
            .finally(function () {
                btnGenerate.disabled = false;
                btnGenerate.textContent = '✨ Générer avec l\'IA';
            });
    });

    // ── Panneau de chat ──────────────────────────────────────────────────────

    btnOpenChat.addEventListener('click', function () {
        aiPanel.classList.add('open');
        chatInput.focus();
    });

    btnCloseChat.addEventListener('click', function () {
        aiPanel.classList.remove('open');
    });

    function appendMessage(role, text) {
        var div = document.createElement('div');
        div.className = 'ai-msg ai-msg-' + role;

        var bubble = document.createElement('div');
        bubble.className = 'ai-bubble';
        bubble.textContent = text;
        div.appendChild(bubble);

        if (role === 'assistant') {
            var copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.className = 'ai-copy-btn';
            copyBtn.textContent = 'Copier dans l\'article';
            copyBtn.addEventListener('click', function () {
                var contentEl = document.getElementById('id_content');
                if (contentEl) {
                    contentEl.value = text;
                    copyBtn.textContent = 'Copié !';
                    setTimeout(function () { copyBtn.textContent = 'Copier dans l\'article'; }, 2000);
                }
            });
            div.appendChild(copyBtn);
        }

        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return div;
    }

    function appendTyping() {
        var div = document.createElement('div');
        div.className = 'ai-msg ai-msg-assistant ai-typing';
        div.innerHTML = '<div class="ai-bubble"><span class="ai-dot"></span><span class="ai-dot"></span><span class="ai-dot"></span></div>';
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return div;
    }

    function sendMessage() {
        var message = chatInput.value.trim();
        if (!message) return;

        chatInput.value = '';
        chatHistory.push({ role: 'user', content: message });
        appendMessage('user', message);

        var typingEl = appendTyping();
        btnSendChat.disabled = true;

        fetch(aiAssistUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                action: 'chat',
                messages: chatHistory,
                current_content: getContent(),
            }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                typingEl.remove();
                if (data.reply) {
                    chatHistory.push({ role: 'assistant', content: data.reply });
                    appendMessage('assistant', data.reply);
                } else {
                    appendMessage('assistant', 'Erreur : ' + (data.error || 'Réponse inattendue'));
                }
            })
            .catch(function () {
                typingEl.remove();
                appendMessage('assistant', 'Erreur de connexion. Réessayez.');
            })
            .finally(function () {
                btnSendChat.disabled = false;
                chatInput.focus();
            });
    }

    btnSendChat.addEventListener('click', sendMessage);

    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});
