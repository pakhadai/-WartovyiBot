document.addEventListener('DOMContentLoaded', () => {
    // 1. Ініціалізація Telegram Web App
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    tg.setHeaderColor(getComputedStyle(document.documentElement).getPropertyValue('--tg-secondary-bg').trim());

    // 2. Глобальні змінні та ідентифікація користувача
    let translations = {};
    const userLang = tg.initDataUnsafe?.user?.language_code || 'en';
    let selectedChatId = null;
    let chatsLoaded = false;
    const userData = tg.initDataUnsafe?.user ? JSON.stringify(tg.initDataUnsafe.user) : null;

    if (!userData) {
        tg.showAlert('Помилка: не вдалося ідентифікувати користувача. Будь ласка, перезапустіть Web App.');
        return;
    }
    const commonHeaders = { 'Content-Type': 'application/json', 'X-User-Data': userData };

    // 3. Пошук основних елементів на сторінці (DOM)
    const pages = document.querySelectorAll('.page');
    const navButtons = document.querySelectorAll('.nav-btn');
    const chatSelector = document.getElementById('chat-selector');
    const settingsContent = document.getElementById('settings-content');
    const settingsContainer = document.getElementById('settings-container');
    const settingsLoader = document.getElementById('settings-loader');
    const toastElement = document.getElementById('toast-notification');
    let toastTimeout;

    // 4. Мультимовність та сповіщення
    async function loadTranslations() {
        try {
            const response = await fetch(`/api/translations/${userLang}`);
            translations = await response.ok ? await response.json() : {};
        } catch (error) { console.error("Failed to load primary translations:", error); }
        try {
            const fallbackResponse = await fetch(`/api/translations/en`);
            const fallbackTranslations = await fallbackResponse.ok ? await fallbackResponse.json() : {};
            translations = { ...fallbackTranslations, ...translations };
        } catch (error) { console.error("Failed to load fallback translations:", error); }
        finally { applyTranslations(); }
    }
    function t(key) { return translations[key] || `[${key}]`; }
    function applyTranslations() {
        document.querySelectorAll('[data-translate]').forEach(el => {
            const key = el.dataset.translate;
            const target = el.placeholder ? 'placeholder' : 'innerHTML';
            el[target] = t(key);
        });
    }
    function showToast(message, isError = false) {
        clearTimeout(toastTimeout);
        toastElement.textContent = message;
        toastElement.className = 'toast show';
        if (isError) toastElement.classList.add('error');
        toastTimeout = setTimeout(() => { toastElement.className = 'toast'; }, 2500);
    }

    // 5. Навігація між сторінками
    function showPage(pageId) {
        pages.forEach(page => page.classList.toggle('active', page.id === pageId));
        navButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.page === pageId));
        if (pageId === 'settings-page' && !chatsLoaded) {
            loadUserChats();
        }
    }

    // 6. Логіка сторінки "Налаштування"
    async function loadUserChats() {
        chatSelector.innerHTML = `<option value="">${t('loading_chats')}</option>`;
        settingsContent.classList.add('hidden');
        try {
            const response = await fetch('/api/my-chats', { headers: commonHeaders });
            if (!response.ok) throw new Error('Не вдалося завантажити список чатів.');
            const chats = await response.json();
            chatsLoaded = true;

            chatSelector.innerHTML = `<option value="">-- ${t('select_chat_placeholder')} --</option>`;
            const defaultOption = document.createElement('option');
            defaultOption.value = 'global';
            defaultOption.textContent = `⚙️ ${t('default_settings') || 'Налаштування за замовчуванням'}`;
            chatSelector.appendChild(defaultOption);

            if (chats.length > 0) {
                chats.forEach(chat => {
                    const option = document.createElement('option');
                    option.value = chat.id;
                    option.textContent = chat.name;
                    chatSelector.appendChild(option);
                });
            }
        } catch (error) {
            tg.showAlert(error.message);
        }
    }

    async function loadChatSettings(chatId) {
        if (!chatId) {
            settingsContent.classList.add('hidden');
            return;
        }
        settingsContent.classList.remove('hidden');
        settingsContainer.classList.add('hidden');
        settingsLoader.classList.remove('hidden');
        try {
            const response = await fetch(`/api/settings/${chatId}`, { headers: commonHeaders });
            if (!response.ok) throw new Error('Не вдалося завантажити налаштування.');
            const settings = await response.json();
            document.getElementById('captcha-toggle').checked = settings.captcha_enabled;
            document.getElementById('spamfilter-toggle').checked = settings.spam_filter_enabled;
            document.getElementById('use-global-list-toggle').checked = settings.use_global_list;
            document.getElementById('use-custom-list-toggle').checked = settings.use_custom_list;
        } catch (error) {
            tg.showAlert(error.message);
        } finally {
            settingsLoader.classList.add('hidden');
            settingsContainer.classList.remove('hidden');
        }
    }

    async function handleSettingUpdate(key, value) {
        if (!selectedChatId) return;
        try {
            const response = await fetch(`/api/settings/${selectedChatId}`, {
                method: 'POST',
                headers: commonHeaders,
                body: JSON.stringify({ key, value })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Не вдалося зберегти.');
            tg.HapticFeedback.notificationOccurred('success');
            showToast(`✅ ${t('changes_saved') || 'Зміни збережено'}`);
        } catch (e) {
            tg.HapticFeedback.notificationOccurred('error');
            showToast(`❌ ${t('error_saving') || 'Помилка збереження'}: ${e.message}`, true);
            loadChatSettings(selectedChatId);
        }
    }

    // 7. Обробники подій
    navButtons.forEach(button => button.addEventListener('click', () => showPage(button.dataset.page)));
    chatSelector.addEventListener('change', (e) => {
        selectedChatId = e.target.value;
        loadChatSettings(selectedChatId);
    });
    document.getElementById('captcha-toggle').addEventListener('change', (e) => handleSettingUpdate('captcha_enabled', e.target.checked));
    document.getElementById('spamfilter-toggle').addEventListener('change', (e) => handleSettingUpdate('spam_filter_enabled', e.target.checked));
    document.getElementById('use-global-list-toggle').addEventListener('change', (e) => handleSettingUpdate('use_global_list', e.target.checked));
    document.getElementById('use-custom-list-toggle').addEventListener('change', (e) => handleSettingUpdate('use_custom_list', e.target.checked));

    // 8. Ініціалізація
    loadTranslations().then(() => {
        showPage('home-page');
    });
});