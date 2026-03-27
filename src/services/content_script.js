/**
 * Job Scraper Content Script V2.2
 * Added: Persistence, improved pause/resume, and optimized filtering.
 */

let isScraping = false;
let isPaused = false;
let scrapedData = [];
let targetLimit = 0;
let filtersApplied = false;

// Audio setup
const captchaSound = new Audio(chrome.runtime.getURL('captcha.mp3'));
const finishedSound = new Audio(chrome.runtime.getURL('finished.mp3'));
const isDevBuild = !chrome.runtime.getManifest().update_url;

// Settings Cache
let settings = {
    notifyCaptcha: true,
    notifyFinish: true
};

// Initialize State from Storage
chrome.storage.local.get(['scrapedData', 'isScraping', 'isPaused', 'targetLimit', 'filtersApplied', 'notifyCaptcha', 'notifyFinish'], (result) => {
    if (result.scrapedData) scrapedData = result.scrapedData;
    if (result.isScraping !== undefined) isScraping = result.isScraping;
    if (result.isPaused !== undefined) isPaused = result.isPaused;
    if (result.targetLimit) targetLimit = result.targetLimit;
    if (result.filtersApplied !== undefined) filtersApplied = result.filtersApplied;

    settings.notifyCaptcha = result.notifyCaptcha !== false;
    settings.notifyFinish = result.notifyFinish !== false;

    console.log(`State recovered: ${scrapedData.length} records, isScraping: ${isScraping}, isPaused: ${isPaused}`);

    if (isScraping && !isPaused) {
        startScraping();
    }
});

// Update Storage helper
function updateStorage() {
    chrome.storage.local.set({
        scrapedData,
        isScraping,
        isPaused,
        targetLimit,
        filtersApplied
    });
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.settings) {
        settings = request.settings;
        chrome.storage.local.set(settings);
    }

    switch (request.action) {
        case 'start':
            // Check activation before starting
            chrome.storage.local.get(['is_activated'], (result) => {
                if (isDevBuild || result.is_activated) {
                    isScraping = true;
                    isPaused = false;
                    if (request.reset) {
                        scrapedData = [];
                        filtersApplied = false;
                    }
                    targetLimit = request.limit || 50;
                    updateStorage();
                    startScraping();
                    sendResponse({ status: 'started' });
                } else {
                    sendResponse({ status: 'unauthorized', message: 'License not activated' });
                }
            });
            return true; // async response
        case 'pause':
            isPaused = true;
            updateStorage();
            sendResponse({ status: 'paused' });
            break;
        case 'resume':
            isPaused = false;
            updateStorage();
            if (isScraping) startScraping();
            sendResponse({ status: 'resumed' });
            break;
        case 'stop':
            isScraping = false;
            isPaused = false;
            updateStorage();
            sendResponse({ status: 'stopped' });
            break;
        case 'reset':
            isScraping = false;
            isPaused = false;
            scrapedData = [];
            filtersApplied = false;
            updateStorage();
            sendResponse({ status: 'reset' });
            break;
        case 'getData':
            sendResponse({ data: scrapedData });
            break;
        case 'getInitialInfo':
            getInitialInfo().then(total => sendResponse({
                total,
                scrapedCount: scrapedData.length,
                isScraping,
                isPaused
            }));
            return true;
        case 'countResults':
            countResults().then(total => {
                filtersApplied = true;
                updateStorage();
                sendResponse({ total });
            });
            return true;
    }
});

async function getInitialInfo() {
    const total = document.getElementById('suchergebnis-h1-anzeige');
    const totalText = total ? total.innerText.replace(/[^0-9]/g, '') : '0';
    return parseInt(totalText) || 0;
}

async function countResults() {
    console.log("Applying filters before counting...");
    await applyFilter();
    await sleep(2000);
    return await getInitialInfo();
}

async function startScraping() {
    // 1. Initial Filtering (only if not already applied)
    if (!filtersApplied) {
        await applyFilter();
        filtersApplied = true;
        updateStorage();
    }

    // 2. Select List View
    const viewTab = document.getElementById('ansicht-auswahl-tabbar-item-1');
    if (viewTab) {
        console.log("Switching to list view...");
        viewTab.click();
        await sleep(1500);
    }

    while (isScraping) {
        if (isPaused) {
            console.log("Scraping paused...");
            break; // Exit loop, resume will re-call startScraping
        }

        let cards = document.querySelectorAll('[id^="ergebnisliste-item-"]');

        if (scrapedData.length < targetLimit) {
            for (let i = scrapedData.length; i < cards.length; i++) {
                if (!isScraping || isPaused) break;
                if (scrapedData.length >= targetLimit) break;

                const card = cards[i];
                card.click();

                await sleep(1500);

                if (await handleCaptcha()) {
                    // logic inside handlCaptcha waits for solve
                }

                const info = extractInfo();
                if (info) {
                    const linkElement = document.getElementById(`agdarstellung-websitelink-${i}`);
                    info.link = linkElement ? linkElement.href : '';

                    scrapedData.push(info);
                    updateStorage();
                    console.log(`Extracted (${scrapedData.length}/${targetLimit}):`, info);
                    chrome.runtime.sendMessage({ action: 'progress', count: scrapedData.length });
                }

                await sleep(1000);
            }
        }

        if (scrapedData.length >= targetLimit) {
            console.log("Target limit reached.");
            break;
        }

        const loadMoreBtn = document.getElementById('ergebnisliste-ladeweitere-button');
        if (loadMoreBtn && isScraping && !isPaused) {
            console.log("Loading more results...");
            loadMoreBtn.click();
            await sleep(3000);
        } else if (!loadMoreBtn) {
            console.log("No more results available.");
            break;
        }
    }

    // Only set finished if we actually hit the limit or ran out of results
    if (isScraping && !isPaused && (scrapedData.length >= targetLimit || !document.getElementById('ergebnisliste-ladeweitere-button'))) {
        if (settings.notifyFinish) finishedSound.play();
        isScraping = false;
        isPaused = false;
        updateStorage();
        chrome.runtime.sendMessage({ action: 'finished', count: scrapedData.length });
    }
}

async function applyFilter() {
    console.log("Checking filter state...");
    const filterToggle = document.getElementById('filter-toggle');
    if (filterToggle) {
        if (filterToggle.getAttribute('aria-expanded') !== 'true') {
            filterToggle.click();
            await sleep(800);
        }

        const extFilter = document.querySelector('input[type="checkbox"][id*="externe"]');
        if (extFilter && !extFilter.checked) {
            console.log("Enabling 'no external offers' filter...");
            extFilter.click();
            await sleep(1000);
        }

        const applyBtn = document.getElementById('footer-button-modales-slide-in-filter');
        if (applyBtn) {
            console.log("Clicking apply filters button...");
            applyBtn.click();
            await sleep(2000);
        }
    }
}

async function handleCaptcha() {
    let captchaForm = document.getElementById('captchaForm') || document.querySelector('form[id*="captcha"]');
    if (captchaForm) {
        console.log("Captcha detected!");

        // Setup repeating sound every 4 seconds
        let soundInterval = null;
        if (settings.notifyCaptcha) {
            captchaSound.play();
            soundInterval = setInterval(() => {
                const stillExists = document.getElementById('captchaForm') || document.querySelector('form[id*="captcha"]');
                if (stillExists && isScraping) {
                    captchaSound.play();
                } else {
                    clearInterval(soundInterval);
                }
            }, 4000);
        }

        const notice = document.createElement('div');
        notice.id = 'scraper-notice';
        notice.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #6366f1; color: white; padding: 24px; border-radius: 12px; z-index: 10000; box-shadow: 0 10px 25px rgba(0,0,0,0.5); font-family: sans-serif; max-width: 320px; border: 1px solid rgba(255,255,255,0.2);';
        notice.innerHTML = `
            <h3 style="margin: 0 0 10px 0; font-family: Outfit, sans-serif;">Action Required</h3>
            <p style="margin: 0; font-size: 14px; opacity: 0.9;">A captcha has appeared. Please solve it manually to continue scraping.</p>
        `;
        document.body.appendChild(notice);

        while (isScraping && (document.getElementById('captchaForm') || document.querySelector('form[id*="captcha"]'))) {
            await sleep(1000);
        }

        if (soundInterval) clearInterval(soundInterval);
        if (notice) notice.remove();
        return true;
    }
    return false;
}

function extractInfo() {
    const addressParent = document.getElementById('detail-bewerbung-adresse');
    const mailElement = document.getElementById('detail-bewerbung-mail');
    const phoneElement = document.getElementById('detail-bewerbung-telefon-Telefon');
    const descContainer = document.getElementById('detail-beschreibung-text-container');

    // Requirement 2: Skip data without email
    if (!mailElement) {
        console.log("No email ID 'detail-bewerbung-mail' found, skipping...");
        return null;
    }

    let company = '';
    let contact = '';
    let address = '';
    let email = mailElement.innerText.trim();
    let phone = '';

    // Requirement 1: Extract phone from href
    if (phoneElement) {
        // Usually href="tel:+49..."
        phone = phoneElement.getAttribute('href') ? phoneElement.getAttribute('href').replace('tel:', '').trim() : phoneElement.innerText.trim();
    }

    if (addressParent) {
        const html = addressParent.innerHTML;
        const lines = html.split(/<br\s*\/?>/i).map(l => l.trim().replace(/<.*?>/g, ''));
        company = lines[0] || '';
        contact = lines[1] || '';
        address = lines.slice(2).join(', ');
    }

    // If no email found in regular field, search in description
    if (!email && descContainer) {
        // Search for mailto: links
        const mailtoMatch = descContainer.innerHTML.match(/mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})/i);
        if (mailtoMatch) {
            email = mailtoMatch[1];
        } else {
            // Broad regex search as fallback
            const emailRegex = /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})/g;
            const textMatch = descContainer.innerText.match(emailRegex);
            if (textMatch) email = textMatch[0];
        }
    }

    // Return object if we found email (already enforced above, but returning consistent object)
    if (email) {
        return { company, contact, address, email, phone };
    }

    return null;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
