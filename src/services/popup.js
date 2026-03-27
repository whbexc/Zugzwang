document.addEventListener('DOMContentLoaded', async () => {
    // View Elements
    const loginView = document.getElementById('login-view');
    const mainView = document.getElementById('main-view');
    const loginError = document.getElementById('login-error');

    // Auth Elements
    const licenseInput = document.getElementById('license-key');
    const activateBtn = document.getElementById('activate-btn');
    const logoutBtn = document.getElementById('logout-btn');

    // Scraper UI Elements
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    const countBtn = document.getElementById('count-btn');
    const resetBtn = document.getElementById('reset-btn');
    const arbeitsagenturBtn = document.getElementById('arbeitsagentur-btn');
    const ausbildungBtn = document.getElementById('ausbildung-btn');
    const aubiplusBtn = document.getElementById('aubiplus-btn');
    const downloadBtn = document.getElementById('download-btn');
    const statusText = document.getElementById('status-text');
    const countDisplay = document.getElementById('scraped-count');
    const totalDisplay = document.getElementById('total-found');
    const limitInput = document.getElementById('fetch-limit');

    // Settings
    const notifyCaptchaCheckbox = document.getElementById('notify-captcha');
    const notifyFinishCheckbox = document.getElementById('notify-finish');
    const initialBtns = document.getElementById('initial-btns');
    const ongoingBtns = document.getElementById('ongoing-btns');

    const i18n = {
        "en": {
            "titleText": "Scrabb",
            "subtitleText": "Premium Extraction Tool",
            "activationLabel": "Enter Activation Code",
            "activateBtn": "Activate License",
            "statusTitle": "Current Status",
            "statusIdle": "Idle",
            "statusFinished": "Finished",
            "statusRunning": "Running",
            "statusPaused": "Paused",
            "targetLabel": "Target Number of Offers",
            "countBtn": "Count Available",
            "startBtn": "Start Scraping",
            "resetBtn": "Reset",
            "arbBtn": "Take me to Arbeitsagentur",
            "ausBtn": "Go to Ausbildung.de",
            "aubiBtn": "Go to Aubi-Plus.de",
            "pauseBtn": "Pause",
            "resumeBtn": "Resume",
            "stopBtn": "Stop",
            "settingsTitle": "Settings",
            "captchaLabel": "Captcha Sound",
            "finishLabel": "Finish Sound",
            "noteTitle": "Note:",
            "noteDesc": "Solve captchas manually if they appear to keep the scraper running.",
            "downloadBtn": "Download CSV Results",
            "logoutBtn": "Deactivate License",
            "loading": "Verifying...",
            "applyingFilters": "Applying filters...",
            "refreshPage": "Please refresh the page",
            "waitingCaptcha": "Waiting for Captcha"
        },
        "ar": {
            "titleText": "Scrabb",
            "subtitleText": "أداة الاستخراج المميزة",
            "activationLabel": "أدخل رمز التفعيل",
            "activateBtn": "تفعيل الترخيص",
            "statusTitle": "الحالة الحالية",
            "statusIdle": "خامل",
            "statusFinished": "مكتمل",
            "statusRunning": "قيد التشغيل",
            "statusPaused": "متوقف مؤقتاً",
            "targetLabel": "العدد المستهدف للعروض",
            "countBtn": "حساب المتاح",
            "startBtn": "بدء الاستخراج",
            "resetBtn": "إعادة ضبط",
            "arbBtn": "انتقل إلى Arbeitsagentur",
            "ausBtn": "اذهب إلى Ausbildung.de",
            "aubiBtn": "اذهب إلى Aubi-Plus.de",
            "pauseBtn": "إيقاف مؤقت",
            "resumeBtn": "استئناف",
            "stopBtn": "إيقاف",
            "settingsTitle": "الإعدادات",
            "captchaLabel": "صوت الكابتشا",
            "finishLabel": "صوت الانتهاء",
            "noteTitle": "ملاحظة:",
            "noteDesc": "قم بحل الكابتشا يدويًا إذا ظهرت لإبقاء المستخرج قيد التشغيل.",
            "downloadBtn": "تحميل نتائج CSV",
            "logoutBtn": "إلغاء تفعيل الترخيص",
            "loading": "جارِ التحقق...",
            "applyingFilters": "جارِ تطبيق الفلاتر...",
            "refreshPage": "يرجى تحديث الصفحة",
            "waitingCaptcha": "في انتظار الكابتشا"
        }
    };

    let currentLang = 'en';

    function applyLanguage(lang) {
        currentLang = lang;
        document.body.dir = lang === 'ar' ? 'rtl' : 'ltr';
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (i18n[lang][key]) {
                el.innerText = i18n[lang][key];
            }
        });

        document.getElementById('lang-en').classList.toggle('active', lang === 'en');
        document.getElementById('lang-ar').classList.toggle('active', lang === 'ar');

        chrome.storage.local.set({ uiLang: lang });

        const statusClass = statusText.className;
        if (statusClass.includes('status-idle')) statusText.innerText = i18n[lang]['statusIdle'];
        else if (statusClass.includes('status-running')) statusText.innerText = i18n[lang]['statusRunning'];
        else if (statusClass.includes('status-finished')) statusText.innerText = i18n[lang]['statusFinished'];
        else if (statusClass.includes('status-paused')) {
            if (statusText.innerText === i18n['en']['waitingCaptcha'] || statusText.innerText === i18n['ar']['waitingCaptcha']) {
                statusText.innerText = i18n[lang]['waitingCaptcha'];
            } else {
                statusText.innerText = i18n[lang]['statusPaused'];
            }
        }

        if (activateBtn.disabled) {
            activateBtn.innerText = i18n[lang]['loading'];
        } else {
            activateBtn.innerText = i18n[lang]['activateBtn'];
        }
    }

    document.getElementById('lang-en').addEventListener('click', () => applyLanguage('en'));
    document.getElementById('lang-ar').addEventListener('click', () => applyLanguage('ar'));

    // 1. Check Activation Status on Load (Local then Live)
    chrome.storage.local.get(['uiLang'], async (res) => {
        applyLanguage(res.uiLang || 'en');

        const isLocalActivated = await window.Auth.checkActivation();
        if (isLocalActivated) {
            showScraper(); // Show immediately for fast DX

            // Perform silent live re-verify
            const liveResult = await window.Auth.performLiveCheck();
            if (!liveResult.success && !liveResult.isNetworkError) {
                // If server says no, and it's not a network fluke, force logout
                showLogin();
            }
        } else {
            showLogin();
        }
    });

    function showLogin() {
        loginView.classList.remove('hidden');
        mainView.classList.add('hidden');
    }

    async function showScraper() {
        loginView.classList.add('hidden');
        mainView.classList.remove('hidden');
        if (window.Auth.isDevBuild()) {
            loginError.classList.add('hidden');
        }
        loadState();
    }

    // 2. Activation Logic
    activateBtn.addEventListener('click', async () => {
        if (window.Auth.isDevBuild()) {
            await window.Auth.verifyLicense('DEV-BUILD');
            showScraper();
            return;
        }

        const key = licenseInput.value.trim();
        if (!key) {
            showError('Please enter a license key');
            return;
        }

        activateBtn.disabled = true;
        activateBtn.innerText = i18n[currentLang]['loading'];
        loginError.classList.add('hidden');

        const result = await window.Auth.verifyLicense(key);

        if (result.success) {
            showScraper();
        } else {
            showError(result.message);
        }

        activateBtn.disabled = false;
        activateBtn.innerText = i18n[currentLang]['activateBtn'];
    });

    logoutBtn.addEventListener('click', async () => {
        if (confirm('Deactivating will remove the link to this device. Continue?')) {
            await chrome.storage.local.remove(['license_key', 'is_activated']);
            showLogin();
        }
    });

    function showError(msg) {
        loginError.innerText = msg;
        loginError.classList.remove('hidden');
    }

    // 3. Main Scraper Logic (V2.2 Core)
    function loadState() {
        chrome.storage.local.get(['notifyCaptcha', 'notifyFinish', 'scrapedData', 'isScraping', 'isPaused', 'targetLimit'], (result) => {
            notifyCaptchaCheckbox.checked = result.notifyCaptcha !== false;
            notifyFinishCheckbox.checked = result.notifyFinish !== false;

            if (result.scrapedData) {
                countDisplay.innerText = result.scrapedData.length;
                downloadBtn.disabled = result.scrapedData.length === 0;
            }

            if (result.targetLimit) {
                limitInput.value = result.targetLimit;
            }

            if (result.isScraping) {
                updateUI(result.isPaused ? 'paused' : 'running');
            } else {
                updateUI('idle');
            }

            syncSettings();
        });
    }

    function getSettings() {
        return {
            notifyCaptcha: notifyCaptchaCheckbox.checked,
            notifyFinish: notifyFinishCheckbox.checked
        };
    }

    /**
     * Helper to safely send messages to the active tab
     * Enhanced with auto-injection and loading state handling
     */
    async function sendMessageToTab(message, callback, retryCount = 0) {
        const [currTab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!currTab || !currTab.id || !isUrlValid(currTab.url)) {
            console.warn('Cannot send message: No active compatible tab found.');
            if (callback) callback(null);
            return;
        }

        // Handle loading state
        if (currTab.status === 'loading' && retryCount < 3) {
            console.log('Tab is loading, retrying in 1s...');
            setTimeout(() => sendMessageToTab(message, callback, retryCount + 1), 1000);
            return;
        }

        chrome.tabs.sendMessage(currTab.id, message, async (response) => {
            if (chrome.runtime.lastError) {
                const errorMsg = chrome.runtime.lastError.message;
                console.warn('Message error:', errorMsg);

                // If content script is missing, try to inject it
                if (errorMsg.includes('Could not establish connection') || errorMsg.includes('Receiving end does not exist')) {
                    console.log('Content script missing. Attempting manual injection...');
                    try {
                        await chrome.scripting.executeScript({
                            target: { tabId: currTab.id },
                            files: ['content_script.js']
                        });
                        // Wait a bit for initialization then retry once
                        setTimeout(() => sendMessageToTab(message, callback, retryCount + 1), 500);
                    } catch (injectError) {
                        console.error('Injection failed:', injectError);
                        if (callback) callback(null);
                    }
                } else {
                    if (callback) callback(null);
                }
                return;
            }
            if (callback) callback(response);
        });
    }

    function isUrlValid(url) {
        if (!url) return false;
        // Loosen to cover search results and landing pages
        return url.includes('arbeitsagentur.de/jobsuche/') || url.includes('arbeitsagentur.de/ksw/ergebnisliste') || url.includes('ausbildung.de') || url.includes('aubi-plus.de');
    }

    async function syncSettings() {
        sendMessageToTab({ settings: getSettings() });
    }

    function saveSettings() {
        chrome.storage.local.set(getSettings());
        syncSettings();
    }

    notifyCaptchaCheckbox.addEventListener('change', saveSettings);
    notifyFinishCheckbox.addEventListener('change', saveSettings);

    function updateUI(status) {
        if (status === 'running') statusText.innerText = i18n[currentLang]['statusRunning'];
        else if (status === 'paused') statusText.innerText = i18n[currentLang]['statusPaused'];
        else if (status === 'finished') statusText.innerText = i18n[currentLang]['statusFinished'];
        else statusText.innerText = i18n[currentLang]['statusIdle'];

        statusText.className = `status-${status}`;

        if (status === 'running') {
            initialBtns.classList.add('hidden');
            ongoingBtns.classList.remove('hidden');
            pauseBtn.classList.remove('hidden');
            resumeBtn.classList.add('hidden');
        } else if (status === 'paused') {
            initialBtns.classList.add('hidden');
            ongoingBtns.classList.remove('hidden');
            pauseBtn.classList.add('hidden');
            resumeBtn.classList.remove('hidden');
        } else if (status === 'idle' || status === 'finished') {
            initialBtns.classList.remove('hidden');
            ongoingBtns.classList.add('hidden');
        }
    }

    // Get initial info about total offers
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Auto-navigate removed based on user request

    if (tab && tab.id && isUrlValid(tab.url)) {
        sendMessageToTab({ action: 'getInitialInfo' }, (response) => {
            if (response) {
                if (response.total) totalDisplay.innerText = response.total;
                if (response.scrapedCount !== undefined) countDisplay.innerText = response.scrapedCount;
                if (response.isScraping) updateUI(response.isPaused ? 'paused' : 'running');
            }
        });
    }

    countBtn.addEventListener('click', async () => {
        statusText.innerText = i18n[currentLang]['applyingFilters'];
        countBtn.disabled = true;

        sendMessageToTab({ action: 'countResults' }, (response) => {
            countBtn.disabled = false;
            updateUI('idle');
            if (response && response.total !== undefined) {
                totalDisplay.innerText = response.total;
                limitInput.value = Math.min(parseInt(limitInput.value), response.total);
            }
        });
    });

    startBtn.addEventListener('click', async () => {
        const limit = parseInt(limitInput.value) || 50;

        sendMessageToTab({ action: 'start', limit, settings: getSettings() }, (response) => {
            if (response && response.status === 'started') {
                updateUI('running');
            } else if (!response) {
                statusText.innerText = i18n[currentLang]['refreshPage'];
            }
        });
    });

    pauseBtn.addEventListener('click', async () => {
        sendMessageToTab({ action: 'pause' }, (response) => {
            if (response && response.status === 'paused') {
                updateUI('paused');
            }
        });
    });

    resumeBtn.addEventListener('click', async () => {
        sendMessageToTab({ action: 'resume' }, (response) => {
            if (response && response.status === 'resumed') {
                updateUI('running');
            }
        });
    });

    stopBtn.addEventListener('click', async () => {
        sendMessageToTab({ action: 'stop' }, (response) => {
            if (response && response.status === 'stopped') {
                updateUI('idle');
            }
        });
    });

    resetBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to clear all scraped data?')) {
            sendMessageToTab({ action: 'reset' }, (response) => {
                if (response && response.status === 'reset') {
                    countDisplay.innerText = '0';
                    totalDisplay.innerText = '?';
                    downloadBtn.disabled = true;
                    updateUI('idle');
                } else if (!response) {
                    statusText.innerText = i18n[currentLang]['refreshPage'];
                }
            });
        }
    });

    arbeitsagenturBtn.addEventListener('click', () => {
        chrome.tabs.create({ url: 'https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=4&id=17907-44005832-32-S' });
    });

    ausbildungBtn.addEventListener('click', () => {
        chrome.tabs.create({ url: 'https://www.ausbildung.de/' });
    });

    aubiplusBtn.addEventListener('click', () => {
        chrome.tabs.create({ url: 'https://www.aubi-plus.de/' });
    });

    downloadBtn.addEventListener('click', async () => {
        sendMessageToTab({ action: 'getData' }, (response) => {
            if (response && response.data) {
                downloadCSV(response.data);
            }
        });
    });

    chrome.runtime.onMessage.addListener((request) => {
        if (request.action === 'progress') {
            if (request.status === 'waiting_captcha') {
                updateUI('paused');
                statusText.innerText = i18n[currentLang]['waitingCaptcha'];
            } else {
                countDisplay.innerText = request.count;
                downloadBtn.disabled = false;
            }
        } else if (request.action === 'finished') {
            updateUI('finished');
            countDisplay.innerText = request.count;
            downloadBtn.disabled = false;
        }
    });

    function downloadCSV(data) {
        // Requirement 3: CSV order - Company Name, Email, Address, D empty, E empty, Ansprechpartner, Anrede, H empty, I empty, website, telephone
        const headers = ['Company Name', 'Email', 'Address', '', '', 'Ansprechpartner', 'Anrede', '', '', 'website', 'telephone'];
        const csvContent = [
            headers.join(','),
            ...data.map(row => {
                const contact = row.contact || '';
                const anrede = contact.trim().split(' ')[0] || '';
                const values = [
                    row.company || '',
                    row.email || '',
                    row.address || '',
                    '', // empty D
                    '', // empty E
                    contact,
                    anrede,
                    '', // empty H
                    '', // empty I
                    row.link || '',
                    row.phone || ''
                ];
                return values.map(v => `"${v.replace(/"/g, '""')}"`).join(',');
            })
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `scraped_jobs_${new Date().toISOString().slice(0, 10)}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
});
