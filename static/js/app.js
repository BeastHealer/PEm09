const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('input');
const btnSend = document.getElementById('btn-send');
const btnReset = document.getElementById('btn-reset');
const btnStats = document.getElementById('btn-stats');
const btnRecord = document.getElementById('btn-record');
const modeSelect = document.getElementById('mode-select');
const voiceSelect = document.getElementById('voice-select');
const imageInput = document.getElementById('image-input');
const docInput = document.getElementById('doc-input');
const typingEl = document.getElementById('typing');
const statusEl = document.getElementById('status');
const modal = document.getElementById('modal');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const modalClose = document.getElementById('modal-close');

let isBusy = false;
let mediaRecorder = null;
let audioChunks = [];

function getSupportedMimeType() {
    const types = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
    ];
    return types.find((t) => MediaRecorder.isTypeSupported(t)) || '';
}

function setBusy(busy) {
    isBusy = busy;
    btnSend.disabled = busy;
    statusEl.textContent = busy ? 'Думаю…' : 'Готов';
    statusEl.classList.toggle('busy', busy);
    typingEl.classList.toggle('hidden', !busy);
}

function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role, content, extras = {}) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    if (extras.label) {
        const label = document.createElement('div');
        label.className = 'label';
        label.textContent = extras.label;
        bubble.appendChild(label);
    }

    const text = document.createElement('span');
    text.textContent = content;
    bubble.appendChild(text);

    if (extras.imageUrl) {
        const img = document.createElement('img');
        img.src = extras.imageUrl;
        img.alt = extras.revisedPrompt || 'Generated image';
        bubble.appendChild(img);
    }

    if (extras.audioUrl) {
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.src = extras.audioUrl;
        bubble.appendChild(audio);
    }

    div.appendChild(bubble);
    messagesEl.appendChild(div);
    scrollToBottom();
}

function showModal(title, body) {
    modalTitle.textContent = title;
    modalBody.textContent = body;
    modal.classList.remove('hidden');
}

modalClose.addEventListener('click', () => modal.classList.add('hidden'));
modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.add('hidden');
});

async function api(url, options = {}) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Ошибка запроса');
    return data;
}

async function updateSettings() {
    await api('/api/settings', {
        method: 'POST',
        body: JSON.stringify({
            mode: modeSelect.value,
            voice: voiceSelect.value,
        }),
    });
}

modeSelect.addEventListener('change', updateSettings);
voiceSelect.addEventListener('change', updateSettings);

async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || isBusy) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    addMessage('user', text);
    setBusy(true);

    try {
        const data = await api('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ message: text }),
        });

        addMessage('assistant', data.text, {
            imageUrl: data.image_url,
            revisedPrompt: data.revised_prompt,
            audioUrl: data.audio_url,
        });
    } catch (err) {
        addMessage('assistant', `❌ ${err.message}`);
    } finally {
        setBusy(false);
    }
}

btnSend.addEventListener('click', sendMessage);

inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
});

btnReset.addEventListener('click', async () => {
    try {
        await api('/api/reset', { method: 'POST' });
        messagesEl.innerHTML = '';
        addMessage('assistant', 'История очищена. Чем могу помочь?');
    } catch (err) {
        showModal('Ошибка', err.message);
    }
});

btnStats.addEventListener('click', async () => {
    try {
        const data = await api('/api/stats');
        if (data.error) {
            showModal('Статистика RAG', data.error);
            return;
        }
        const text = `Фрагментов в индексе: ${data.total_documents || 0}\nИсточники: FAQ.pdf, course.txt, RTFM.docx`;
        showModal('Статистика RAG', text);
    } catch (err) {
        showModal('Ошибка', err.message);
    }
});

imageInput.addEventListener('change', async () => {
    const file = imageInput.files[0];
    if (!file || isBusy) return;

    const caption = prompt('Вопрос к изображению (необязательно):') || '';
    addMessage('user', caption ? `📷 ${caption}` : '📷 [изображение]');
    setBusy(true);

    const form = new FormData();
    form.append('image', file);
    if (caption) form.append('caption', caption);

    try {
        const res = await fetch('/api/image/analyze', { method: 'POST', body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Ошибка');
        addMessage('assistant', data.text);
    } catch (err) {
        addMessage('assistant', `❌ ${err.message}`);
    } finally {
        setBusy(false);
        imageInput.value = '';
    }
});

docInput.addEventListener('change', async () => {
    const file = docInput.files[0];
    if (!file) return;

    addMessage('user', `📄 Загружаю: ${file.name}`);
    setBusy(true);

    const form = new FormData();
    form.append('document', file);

    try {
        const res = await fetch('/api/documents', { method: 'POST', body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Ошибка');
        addMessage('assistant', `✅ ${data.message}`);
        modeSelect.value = 'rag';
        await updateSettings();
    } catch (err) {
        addMessage('assistant', `❌ ${err.message}`);
    } finally {
        setBusy(false);
        docInput.value = '';
    }
});

btnRecord.addEventListener('click', async () => {
    if (isBusy) return;

    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        const mimeType = getSupportedMimeType();
        mediaRecorder = mimeType
            ? new MediaRecorder(stream, { mimeType })
            : new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };
        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach((t) => t.stop());
            btnRecord.classList.remove('recording');

            if (audioChunks.length === 0) {
                showModal('Запись', 'Запись пуста. Удерживайте кнопку 🎤 и говорите, затем нажмите снова для остановки.');
                return;
            }

            const mimeType = mediaRecorder.mimeType || 'audio/webm';
            const ext = mimeType.includes('ogg') ? 'ogg' : 'webm';
            const blob = new Blob(audioChunks, { type: mimeType });
            addMessage('user', '🎤 [голосовое сообщение]');
            setBusy(true);

            const form = new FormData();
            form.append('audio', blob, `recording.${ext}`);

            try {
                const res = await fetch('/api/voice', { method: 'POST', body: form });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Ошибка');

                if (data.transcription) {
                    addMessage('assistant', `Распознано: «${data.transcription}»`, { label: 'Whisper' });
                }
                addMessage('assistant', data.text, {
                    imageUrl: data.image_url,
                    audioUrl: data.audio_url,
                });
            } catch (err) {
                addMessage('assistant', `❌ ${err.message}`);
            } finally {
                setBusy(false);
            }
        };

        mediaRecorder.start(250);
        btnRecord.classList.add('recording');
        btnRecord.title = 'Нажмите ещё раз, чтобы остановить запись';
    } catch (err) {
        showModal('Микрофон', 'Не удалось получить доступ к микрофону. Разрешите доступ в браузере.');
    }
});
