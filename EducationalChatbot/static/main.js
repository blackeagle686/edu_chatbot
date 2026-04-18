/* ── Wasla Master Main UI Logic ── */

(function () {
    /* ── Helpers ── */
    function now() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        return text.replace(/\n/g, '<br>');
    }

    async function previewDocument(url, title) {
        const modalTitle = document.querySelector('#docPreviewModalLabel span');
        if (modalTitle) modalTitle.textContent = title;

        const downloadBtn = document.getElementById('doc-preview-download-btn');
        if (downloadBtn) {
            downloadBtn.href = url;
            downloadBtn.download = title;
        }

        const contentDiv = document.getElementById('doc-preview-content');
        if (contentDiv) {
            contentDiv.innerHTML = '<div class="text-center py-5"><i class="fas fa-spinner fa-spin fa-2x text-warning"></i><p class="mt-2">Loading preview...</p></div>';
        }

        const modalEl = document.getElementById('docPreviewModal');
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();

            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error('File not found or network error');
                const text = await response.text();
                if (contentDiv) contentDiv.innerHTML = renderMarkdown(text);
            } catch (err) {
                if (contentDiv) contentDiv.innerHTML = `<div class="alert alert-danger">Failed to load document preview. <br>${err.message}</div>`;
            }
        }
    }

    /* ── Global Context ── */
    const config = {
        userRole: document.body.dataset.userRole || 'user'
    };

    /* ── DOM refs ── */
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const imageInput = document.getElementById('image-input');
    const chatMessages = document.getElementById('chat-messages');
    const imgPreviewC = document.getElementById('image-preview-container');
    const imgPreview = document.getElementById('image-preview');
    const removeBtn = document.getElementById('remove-image-btn');
    const sendBtn = document.getElementById('send-btn');
    const welcomeTime = document.getElementById('welcome-time');

    let selectedImage = null;

    /* ── Initialization ── */
    if (welcomeTime) welcomeTime.textContent = now();

    /* ── Image Handling ── */
    if (imageInput) {
        imageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            selectedImage = file;
            const reader = new FileReader();
            reader.onload = (ev) => {
                if (imgPreview) imgPreview.src = ev.target.result;
                if (imgPreviewC) imgPreviewC.style.display = 'flex';
            };
            reader.readAsDataURL(file);
        });
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', clearImage);
    }

    function clearImage() {
        selectedImage = null;
        if (imageInput) imageInput.value = '';
        if (imgPreviewC) imgPreviewC.style.display = 'none';
        if (imgPreview) imgPreview.src = '';
    }

    /* ── Document upload ── */
    const docInput = document.getElementById('doc-input');
    const docUploadTrigger = document.getElementById('doc-upload-trigger');

    if (docInput && docUploadTrigger) {
        docInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            docUploadTrigger.disabled = true;
            docUploadTrigger.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/upload_doc', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                if (data.status === 'success') {
                    appendMessage(`✅ Document **${file.name}** uploaded and ingested successfully!`, 'bot');
                } else {
                    appendMessage(`❌ Error uploading document: ${data.error || 'Upload failed'}`, 'bot');
                }
            } catch (err) {
                appendMessage(`❌ Connection error during document upload.`, 'bot');
                console.error(err);
            } finally {
                docUploadTrigger.disabled = false;
                docUploadTrigger.innerHTML = '<i class="fas fa-file-alt"></i>';
                docInput.value = '';
            }
        });
    }

    /* ── Chat Functionality ── */
    function appendMessage(text, sender, imageUrl = null, thinking = null) {
        if (!chatMessages) return;

        const row = document.createElement('div');
        row.classList.add('message-row');
        if (sender === 'user') row.classList.add('user-row');

        const avatar = document.createElement('div');
        avatar.classList.add('msg-avatar');
        avatar.classList.add(sender === 'user' ? 'user-av' : 'bot-av');
        avatar.innerHTML = sender === 'user'
            ? '<i class="fas fa-user"></i>'
            : '<i class="fas fa-robot"></i>';

        const bubble = document.createElement('div');
        bubble.classList.add('message', sender);

        if (imageUrl) {
            const img = document.createElement('img');
            img.src = imageUrl;
            img.classList.add('chat-img');
            bubble.appendChild(img);
        }

        if (thinking && sender === 'bot') {
            const thinkDiv = document.createElement('div');
            thinkDiv.classList.add('thought-process');
            thinkDiv.style.display = 'block';
            thinkDiv.innerHTML = renderMarkdown(thinking);
            bubble.appendChild(thinkDiv);
        }

        const content = document.createElement('div');
        content.classList.add('msg-content');
        if (sender === 'bot') {
            content.innerHTML = renderMarkdown(text);
        } else {
            content.textContent = text;
        }
        bubble.appendChild(content);

        const time = document.createElement('span');
        time.classList.add('msg-time');
        time.textContent = now();
        bubble.appendChild(time);

        row.appendChild(avatar);
        row.appendChild(bubble);

        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendLoading() {
        if (!chatMessages) return null;
        const row = document.createElement('div');
        row.classList.add('message-row');

        const avatar = document.createElement('div');
        avatar.classList.add('msg-avatar', 'bot-av');
        avatar.innerHTML = '<i class="fas fa-robot"></i>';

        const bubble = document.createElement('div');
        bubble.classList.add('message', 'bot', 'loading-msg');
        bubble.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';

        row.appendChild(avatar);
        row.appendChild(bubble);
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return row;
    }

    let isProcessing = false;

    async function handleSubmit(e) {
        if (e) e.preventDefault();
        if (isProcessing) return;

        const message = userInput ? userInput.value.trim() : "";
        if (!message && !selectedImage) return;

        isProcessing = true;
        const prompt = message || 'Analyze this image.';
        const currentImage = selectedImage;
        const imageUrl = currentImage ? URL.createObjectURL(currentImage) : null;

        appendMessage(prompt, 'user', imageUrl);

        if (userInput) userInput.value = '';
        clearImage();

        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.style.opacity = '0.6';
        }

        const loadingRow = appendLoading();

        try {
            const formData = new FormData();
            formData.append('message', prompt);
            formData.append('role', config.userRole);
            if (currentImage) {
                formData.append('image', currentImage);
            }

            const response = await fetch('/chat', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (loadingRow && loadingRow.parentNode) {
                chatMessages.removeChild(loadingRow);
            }

            const reply = data.response
                || ('Sorry, I encountered an error: ' + (data.error || 'Unknown error'));
            appendMessage(reply, 'bot', null, data.thinking);

            if (data.generated_docs && data.generated_docs.length > 0) {
                const docsPanel = document.getElementById('docs-panel');
                if (docsPanel) {
                    docsPanel.classList.remove('d-none');
                    docsPanel.classList.add('d-flex');
                }

                const list = document.getElementById('generated-docs-list');
                if (list) {
                    data.generated_docs.forEach(doc => {
                        const div = document.createElement('div');
                        div.className = 'btn-group w-100';

                        const previewBtn = document.createElement('button');
                        previewBtn.className = 'btn btn-sm btn-outline-light text-start text-truncate w-75';
                        previewBtn.innerHTML = `<i class="fas fa-eye text-info me-2"></i>${doc.name}`;
                        previewBtn.onclick = () => previewDocument(doc.url, doc.name);

                        const downloadBtn = document.createElement('a');
                        downloadBtn.className = 'btn btn-sm btn-outline-light w-25 text-center';
                        downloadBtn.href = doc.url;
                        downloadBtn.target = '_blank';
                        downloadBtn.title = 'Download';
                        downloadBtn.innerHTML = `<i class="fas fa-download text-warning"></i>`;

                        div.appendChild(previewBtn);
                        div.appendChild(downloadBtn);
                        list.appendChild(div);
                    });
                }
            }

        } catch (err) {
            if (loadingRow && loadingRow.parentNode) {
                chatMessages.removeChild(loadingRow);
            }
            appendMessage('Failed to connect to the server. Please try again.', 'bot');
            console.error('Chat error:', err);
        } finally {
            isProcessing = false;
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.style.opacity = '1';
            }
            if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    /* ── Scroll Reveal ── */
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
        }, { threshold: 0.12 });
        document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    }

    if (chatForm) {
        chatForm.addEventListener('submit', handleSubmit);
    }

    /* ── Toggle Theme ── */
    const themeBtn = document.getElementById('themeToggleBtn');
    const themeIcon = document.getElementById('themeIcon');
    const rootTheme = document.documentElement;

    if (themeIcon && rootTheme.getAttribute('data-theme') === 'light') {
        themeIcon.className = 'fas fa-sun';
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            if (rootTheme.getAttribute('data-theme') === 'light') {
                rootTheme.removeAttribute('data-theme');
                localStorage.setItem('wasla-theme', 'dark');
                if (themeIcon) themeIcon.className = 'fas fa-moon';
            } else {
                rootTheme.setAttribute('data-theme', 'light');
                localStorage.setItem('wasla-theme', 'light');
                if (themeIcon) themeIcon.className = 'fas fa-sun';
            }
        });
    }

    /* ── Export for manual use if needed ── */
    window.previewDocument = previewDocument;
    window.appendMessage = appendMessage;

})();
