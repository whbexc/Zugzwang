// ausbildung_script.js
let isScraping = false;
let isPaused = false;
let targetLimit = 50;

const finishedSound = new Audio(chrome.runtime.getURL('finished.mp3'));
let settings = { notifyFinish: true };

function waitForElement(selector, timeout = 10000) {
    return new Promise((resolve) => {
        if (document.querySelector(selector)) return resolve(document.querySelector(selector));

        const observer = new MutationObserver(() => {
            if (document.querySelector(selector)) {
                observer.disconnect();
                resolve(document.querySelector(selector));
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        setTimeout(() => {
            observer.disconnect();
            resolve(null);
        }, timeout);
    });
}

// 1. Job details page text extraction
async function extractDataAndClose() {
    const companyNameEl = document.querySelector('.jp-c-header__corporation-link');
    const companyName = companyNameEl ? companyNameEl.innerText.trim() : '';

    const addressEl = document.querySelector('.jp-title__address');
    const address = addressEl ? addressEl.innerText.replace(/📍/g, '').trim() : '';

    const mailtoLinks = Array.from(document.querySelectorAll('a[href^="mailto:"]'));
    const emailLink = mailtoLinks.find(a => a.href.includes('@'));
    const email = emailLink ? emailLink.href.replace('mailto:', '').split('?')[0].trim() : '';

    if (companyName || email || address) {
        chrome.storage.local.get(['scrapedData'], (res) => {
            const data = res.scrapedData || [];
            data.push({
                company: companyName,
                email: email,
                address: address,
                contact: '',
                anrede: '',
                link: '',
                phone: ''
            });

            chrome.storage.local.set({ scrapedData: data }, () => {
                console.log("Ausbildung.de data saved:", { companyName, email, address });
                // We let the extension save it and keep the page open as requested
            });
        });
    }
}

// 2. Main search page interaction
async function applyFilters() {
    // wait for filter id: "_R_d6cpav5tpflb_" and click it
    const filterBtn = await waitForElement('#_R_d6cpav5tpflb_', 10000);
    if (filterBtn) {
        filterBtn.click();

        // Find div id: "klassische-duale-berufsausbildung-label" and check it
        const checkLabel = await waitForElement('#klassische-duale-berufsausbildung-label', 5000);
        if (checkLabel) {
            checkLabel.click();
        } else {
            const checkIcon = await waitForElement('.CheckboxItem-module__P4--Qq__checkmark', 5000);
            if (checkIcon) checkIcon.click();
        }

        // Let it load after filtering
        await new Promise(r => setTimeout(r, 1500));
    }
}

// 2. Main search page interaction
async function handleSearchPage(limit = 50) {
    if (isScraping) return;
    isScraping = true;
    isPaused = false;
    targetLimit = limit;

    await applyFilters();

    // Give it a moment to ensure cards are loaded
    await new Promise(r => setTimeout(r, 2000));

    let currentData = await new Promise(r => {
        chrome.storage.local.get(['scrapedData'], res => r(res.scrapedData || []));
    });

    let i = 0;
    let retries = 0;

    while (isScraping && currentData.length < limit) {
        while (isPaused) {
            await new Promise(r => setTimeout(r, 500));
            if (!isScraping) break;
        }
        if (!isScraping) break;

        if (currentData.length >= limit) break;

        const cards = document.querySelectorAll('.JobPostingCard-module__RpcvXq__cardWrapper');

        if (i >= cards.length) {
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 1500));

            const spinnerContainer = document.querySelector('.SearchResults-module__6Vm6GG__spinnerContainer');
            if (spinnerContainer) {
                const btn = spinnerContainer.querySelector('button');
                if (btn) btn.click();
                else spinnerContainer.click();
            } else {
                const buttons = Array.from(document.querySelectorAll('button'));
                const loadMoreBtn = buttons.find(b => {
                    const txt = (b.innerText || '').toLowerCase();
                    return txt.includes('load more') || txt.includes('mehr laden') || txt.includes('weitere');
                });
                if (loadMoreBtn) loadMoreBtn.click();
            }

            await new Promise(r => setTimeout(r, 1500));

            const newCardsLength = document.querySelectorAll('.JobPostingCard-module__RpcvXq__cardWrapper').length;
            if (newCardsLength === cards.length) {
                retries++;
                if (retries > 5) {
                    console.log("No more cards loaded after scrolling.");
                    break;
                }
            } else {
                retries = 0;
            }
            continue;
        }

        const linkElement = cards[i].querySelector('a');
        if (!linkElement || !linkElement.href) {
            i++;
            continue;
        }

        try {
            const response = await fetch(linkElement.href);
            const text = await response.text();

            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');

            const companyNameEl = doc.querySelector('.jp-c-header__corporation-link');
            const companyName = companyNameEl ? companyNameEl.innerText.trim() : '';

            const addressEl = doc.querySelector('.jp-title__address');
            const address = addressEl ? addressEl.innerText.replace(/📍/g, '').trim() : '';

            const mailtoLinks = Array.from(doc.querySelectorAll('a[href^="mailto:"]'));
            const emailLink = mailtoLinks.find(a => a.href.includes('@'));
            const email = emailLink ? emailLink.href.replace('mailto:', '').split('?')[0].trim() : '';

            if (!email) {
                i++;
                continue; // Skip if no email found
            }

            if (companyName || email || address) {
                currentData.push({
                    company: companyName,
                    email: email,
                    address: address,
                    contact: '',
                    anrede: '',
                    link: linkElement.href,
                    phone: ''
                });

                await new Promise(r => chrome.storage.local.set({ scrapedData: currentData }, r));
                chrome.runtime.sendMessage({ action: 'progress', count: currentData.length });
            }
        } catch (err) {
            console.error("Error fetching job details", err);
        }

        // Wait a bit to not overwhelm the server
        await new Promise(r => setTimeout(r, 1000));
        i++;
    }

    if (isScraping) {
        if (settings.notifyFinish) finishedSound.play();
        chrome.runtime.sendMessage({ action: 'finished', count: currentData.length });
    }
    isScraping = false;
    isPaused = false;
}

async function countResults() {
    await applyFilters();

    const h2 = await waitForElement('.SearchResults-module__6Vm6GG__headline', 5000) ||
        document.querySelector('[data-testid="search-result-title"]');

    if (h2) {
        const text = h2.innerText || h2.textContent;
        const match = text.match(/([\d\.]+)\s*freie Ausbildungspl(?:ä|a)tze/i);
        if (match) {
            return parseInt(match[1].replace(/\./g, ''), 10);
        } else {
            const numMatch = text.match(/([\d\.]+)/);
            if (numMatch) return parseInt(numMatch[1].replace(/\./g, ''), 10);
        }
    }
    return 0;
}

function init() {
    // If we're on a job detail page
    if (document.querySelector('.jp-c-header__corporation-link') || window.location.pathname.includes('/stellen/')) {
        setTimeout(extractDataAndClose, 2000);
        return;
    }
}

// Run on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(init, 1000);
    });
} else {
    setTimeout(init, 1000);
}

// 3. Listen for popup actions
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.settings) {
        settings = request.settings;
    }

    if (request.action === 'countResults') {
        countResults().then(total => sendResponse({ total }));
        return true;
    }
    if (request.action === 'reset') {
        isScraping = false;
        isPaused = false;
        chrome.storage.local.set({ scrapedData: [] }, () => {
            sendResponse({ status: 'reset' });
        });
        return true;
    }
    if (request.action === 'start') {
        const limit = request.limit || 50;
        if (!isScraping) {
            handleSearchPage(limit);
        }
        sendResponse({ status: 'started' });
        return true;
    }
    if (request.action === 'pause') {
        isPaused = true;
        sendResponse({ status: 'paused' });
        return true;
    }
    if (request.action === 'resume') {
        isPaused = false;
        if (isScraping) {
            // we are already paused within loop, so setting isPaused to false resumes it
        }
        sendResponse({ status: 'resumed' });
        return true;
    }
    if (request.action === 'stop') {
        isScraping = false;
        isPaused = false;
        sendResponse({ status: 'stopped' });
        return true;
    }
    if (request.action === 'getInitialInfo') {
        chrome.storage.local.get(['scrapedData'], (res) => {
            const scount = res.scrapedData ? res.scrapedData.length : 0;
            sendResponse({ isScraping: isScraping, isPaused: isPaused, scrapedCount: scount });
        });
        return true;
    }
    if (request.action === 'getData') {
        chrome.storage.local.get(['scrapedData'], (res) => {
            sendResponse({ data: res.scrapedData || [] });
        });
        return true;
    }
});
