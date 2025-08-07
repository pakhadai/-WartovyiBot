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
        } catch (error) {
            console.error("Failed to load primary translations:", error);
        }
        try {
            const fallbackResponse = await fetch(`/api/translations/en`);
            const fallbackTranslations = await fallbackResponse.ok ? await fallbackResponse.json() : {};
            translations = { ...fallbackTranslations, ...translations };
        } catch (error) {
            console.error("Failed to load fallback translations:", error);
        }
        finally {
            applyTranslations();
        }
    }

    function t(key) {
        return translations[key] || `[${key}]`;
    }

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
        // Завантажуємо чати для статистики при першому відкритті
        if (pageId === 'stats-page' && window.statsModule && !window.statsModule.chatsLoaded) {
            window.statsModule.loadChats();
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
            document.getElementById('spam-threshold').value = settings.spam_threshold;
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

    // === МОДУЛЬ СТАТИСТИКИ ===
    window.statsModule = {
        currentChatId: null,
        currentPeriod: 7,
        charts: {},
        chatsLoaded: false,

        init() {
            console.log('Initializing stats module...');

            const statsChatSelector = document.getElementById('stats-chat-selector');
            if (statsChatSelector) {
                statsChatSelector.addEventListener('change', (e) => {
                    this.currentChatId = e.target.value;
                    if (this.currentChatId) {
                        this.loadStats();
                    } else {
                        document.getElementById('stats-container').classList.add('hidden');
                    }
                });
            }

            document.querySelectorAll('.period-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    this.currentPeriod = parseInt(e.target.dataset.days);
                    if (this.currentChatId) {
                        this.loadStats();
                    }
                });
            });

            const exportBtn = document.getElementById('export-stats-btn');
            if (exportBtn) {
                exportBtn.addEventListener('click', () => this.exportStats());
            }
        },

        async loadChats() {
            console.log('Loading chats for stats...');
            const selector = document.getElementById('stats-chat-selector');
            selector.innerHTML = `<option value="">${t('loading_chats')}</option>`;

            try {
                const response = await fetch('/api/my-chats', { headers: commonHeaders });
                if (!response.ok) throw new Error('Failed to load chats');

                const chats = await response.json();
                this.chatsLoaded = true;

                selector.innerHTML = `<option value="">-- ${t('select_chat_placeholder')} --</option>`;

                chats.forEach(chat => {
                    const option = document.createElement('option');
                    option.value = chat.id;
                    option.textContent = chat.name;
                    selector.appendChild(option);
                });
            } catch (error) {
                console.error('Error loading chats for stats:', error);
                selector.innerHTML = `<option value="">Error loading chats</option>`;
            }
        },

        async loadStats() {
            console.log('Loading stats for chat:', this.currentChatId);
            const container = document.getElementById('stats-container');
            const noDataContainer = document.getElementById('no-stats-data');

            container.classList.remove('hidden');
            noDataContainer.classList.add('hidden');

            try {
                const response = await fetch(
                    `/api/stats/${this.currentChatId}?days=${this.currentPeriod}`,
                    { headers: commonHeaders }
                );

                if (!response.ok) throw new Error('Failed to load stats');

                const data = await response.json();
                console.log('Stats data received:', data);
                this.renderStats(data);

            } catch (error) {
                console.error('Error loading stats:', error);
                container.classList.add('hidden');
                noDataContainer.classList.remove('hidden');
            }
        },

        renderStats(data) {
            const { historical, current } = data;
            const totals = historical.totals || {};

            document.getElementById('total-messages').textContent =
                this.formatNumber(totals.total_messages || 0);

            document.getElementById('spam-blocked').textContent =
                this.formatNumber(totals.total_deleted || 0);

            const userGrowth = (totals.total_joined || 0) - (totals.total_left || 0);
            document.getElementById('user-growth').textContent =
                (userGrowth >= 0 ? '+' : '') + userGrowth;

            const captchaTotal = (totals.total_captcha_passed || 0) + (totals.total_captcha_failed || 0);
            const captchaRate = captchaTotal > 0
                ? Math.round((totals.total_captcha_passed / captchaTotal) * 100)
                : 0;
            document.getElementById('captcha-success').textContent = captchaRate + '%';

            this.updateChangeIndicators(historical);
            this.drawActivityChart(historical.daily || []);
            this.drawHourlyChart(historical.hourly_activity || []);
            this.renderViolators(historical.top_violators || []);
            this.renderCurrentStatus(current);
        },

        updateChangeIndicators(historical) {
            const changes = document.querySelectorAll('.stat-change');
            if (changes[0]) changes[0].textContent = '+12%';
            if (changes[1]) changes[1].textContent = '-8%';
            if (changes[2]) changes[2].textContent = '+' + ((historical.totals?.total_joined || 0) - (historical.totals?.total_left || 0));
            if (changes[3]) changes[3].textContent = `${historical.totals?.total_captcha_passed || 0}/${(historical.totals?.total_captcha_passed || 0) + (historical.totals?.total_captcha_failed || 0)}`;
        },

        drawActivityChart(dailyData) {
            const canvas = document.getElementById('activity-chart');
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            const labels = dailyData.map(d => this.formatDate(d.date));
            const messagesData = dailyData.map(d => d.messages_total || 0);
            const deletedData = dailyData.map(d => d.messages_deleted || 0);

            this.drawSimpleLineChart(ctx, labels, [
                { data: messagesData, color: '#007aff', label: 'Повідомлення' },
                { data: deletedData, color: '#e74c3c', label: 'Видалено' }
            ]);
        },

        drawHourlyChart(hourlyData) {
            const canvas = document.getElementById('hourly-chart');
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            const hours = Array.from({length: 24}, (_, i) => i);
            const data = new Array(24).fill(0);

            hourlyData.forEach(item => {
                const hour = parseInt(item.hour);
                data[hour] = item.count;
            });

            this.drawSimpleBarChart(ctx, hours.map(h => `${h}:00`), data, '#007aff');
        },

        drawSimpleLineChart(ctx, labels, datasets) {
            const canvas = ctx.canvas;
            const width = canvas.width = canvas.offsetWidth * 2;
            const height = canvas.height = 300;
            const padding = 40;

            ctx.clearRect(0, 0, width, height);
            ctx.scale(2, 2);

            let maxValue = 0;
            datasets.forEach(dataset => {
                maxValue = Math.max(maxValue, ...dataset.data);
            });
            maxValue = maxValue || 1;

            const chartWidth = width/2 - padding * 2;
            const chartHeight = height/2 - padding * 2;
            const stepX = chartWidth / (labels.length - 1 || 1);

            ctx.strokeStyle = '#e0e0e0';
            ctx.lineWidth = 0.5;
            for (let i = 0; i <= 5; i++) {
                const y = padding + (chartHeight * i / 5);
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(padding + chartWidth, y);
                ctx.stroke();
            }

            datasets.forEach(dataset => {
                ctx.strokeStyle = dataset.color;
                ctx.lineWidth = 2;
                ctx.beginPath();

                dataset.data.forEach((value, index) => {
                    const x = padding + index * stepX;
                    const y = padding + chartHeight - (value / maxValue * chartHeight);

                    if (index === 0) {
                        ctx.moveTo(x, y);
                    } else {
                        ctx.lineTo(x, y);
                    }
                });

                ctx.stroke();

                ctx.fillStyle = dataset.color;
                dataset.data.forEach((value, index) => {
                    const x = padding + index * stepX;
                    const y = padding + chartHeight - (value / maxValue * chartHeight);
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, Math.PI * 2);
                    ctx.fill();
                });
            });

            ctx.fillStyle = '#666';
            ctx.font = '10px Inter';
            labels.forEach((label, index) => {
                if (index % Math.ceil(labels.length / 7) === 0) {
                    const x = padding + index * stepX;
                    ctx.fillText(label, x - 15, height/2 - 10);
                }
            });
        },

        drawSimpleBarChart(ctx, labels, data, color) {
            const canvas = ctx.canvas;
            const width = canvas.width = canvas.offsetWidth * 2;
            const height = canvas.height = 200;
            const padding = 20;

            ctx.clearRect(0, 0, width, height);
            ctx.scale(2, 2);

            const maxValue = Math.max(...data) || 1;
            const barWidth = (width/2 - padding * 2) / labels.length;
            const chartHeight = height/2 - padding * 2;

            ctx.fillStyle = color;

            data.forEach((value, index) => {
                const x = padding + index * barWidth;
                const barHeight = (value / maxValue) * chartHeight;
                const y = height/2 - padding - barHeight;

                ctx.globalAlpha = 0.8;
                ctx.fillRect(x + barWidth * 0.1, y, barWidth * 0.8, barHeight);
            });

            ctx.globalAlpha = 1;
        },

        renderViolators(violators) {
            const container = document.getElementById('top-violators');

            if (violators.length === 0) {
                container.innerHTML = `<div class="loading-placeholder">${t('no_violators')}</div>`;
                return;
            }

            container.innerHTML = violators.map(v => `
                <div class="violator-item">
                    <span class="violator-name">ID: ${v.user_id}</span>
                    <span class="violator-count">${v.violation_count} ${t('violations_count').replace('{count}', v.violation_count)}</span>
                </div>
            `).join('');
        },

        renderCurrentStatus(current) {
            const settings = current.settings || {};
            const warnings = current.warnings || {};

            const captchaStatus = document.getElementById('captcha-status');
            const statusEnabled = t('status_enabled');
            const statusDisabled = t('status_disabled');

            captchaStatus.textContent = settings.captcha_enabled ? statusEnabled : statusDisabled;
            captchaStatus.className = settings.captcha_enabled ? 'status-value enabled' : 'status-value disabled';

            const spamStatus = document.getElementById('spam-filter-status');
            spamStatus.textContent = settings.spam_filter_enabled ? statusEnabled : statusDisabled;
            spamStatus.className = settings.spam_filter_enabled ? 'status-value enabled' : 'status-value disabled';

            document.getElementById('spam-threshold-status').textContent = settings.spam_threshold || '-';

            const warnedText = t('warned_users_format')
                .replace('{users}', warnings.users_with_warnings || 0)
                .replace('{warnings}', warnings.total_warnings || 0);
            document.getElementById('warned-users').textContent = warnedText;

            document.getElementById('blocklist-size').textContent = current.blocklist_count || 0;
            document.getElementById('whitelist-size').textContent = current.whitelist_count || 0;
        },

        async exportStats() {
            if (!this.currentChatId) {
                tg.showAlert('Спочатку виберіть групу');
                return;
            }

            try {
                const response = await fetch(
                    `/api/stats/${this.currentChatId}/export?format=csv`,
                    { headers: commonHeaders }
                );

                if (!response.ok) throw new Error('Failed to export');

                const data = await response.json();
                const blob = new Blob([data.csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `stats_${this.currentChatId}_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);

                showToast('✅ Статистику експортовано');

            } catch (error) {
                console.error('Export error:', error);
                tg.showAlert('Помилка експорту даних');
            }
        },

        formatNumber(num) {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(1) + 'M';
            } else if (num >= 1000) {
                return (num / 1000).toFixed(1) + 'K';
            }
            return num.toString();
        },

        formatDate(dateStr) {
            const date = new Date(dateStr);
            return `${date.getDate()}.${date.getMonth() + 1}`;
        }
    };

    // 7. Обробники подій
    navButtons.forEach(button => button.addEventListener('click', () => {
        const pageId = button.dataset.page;
        showPage(pageId);
    }));

    chatSelector.addEventListener('change', (e) => {
        selectedChatId = e.target.value;
        loadChatSettings(selectedChatId);
    });

    document.getElementById('captcha-toggle').addEventListener('change', (e) =>
        handleSettingUpdate('captcha_enabled', e.target.checked));

    document.getElementById('spamfilter-toggle').addEventListener('change', (e) =>
        handleSettingUpdate('spam_filter_enabled', e.target.checked));

    document.getElementById('use-global-list-toggle').addEventListener('change', (e) =>
        handleSettingUpdate('use_global_list', e.target.checked));

    document.getElementById('use-custom-list-toggle').addEventListener('change', (e) =>
        handleSettingUpdate('use_custom_list', e.target.checked));

    document.getElementById('spam-threshold').addEventListener('change', (e) => {
        const value = parseInt(e.target.value);
        if (value >= 5 && value <= 50) {
            handleSettingUpdate('spam_threshold', value);
        }
    });

    // 8. Ініціалізація
    loadTranslations().then(() => {
        showPage('home-page');
        // Ініціалізуємо модуль статистики
        window.statsModule.init();
    });
});