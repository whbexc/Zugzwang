// aubiplus_script.js
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

async function applyFilters() {
    // Check and wait for the filter dropdown
    const dropdownBtn = await waitForElement('.btn-filter', 5000);
    if (dropdownBtn) {
        dropdownBtn.click();

        // The checkbox is hidden (d-none), so we click its label instead
        const ausbildungCheckbox = await waitForElement('#fTyp_ausbildung', 3000);
        const ausbildungLabel = document.querySelector('label[for="fTyp_ausbildung"]');
        if (ausbildungCheckbox && ausbildungLabel) {
            if (!ausbildungCheckbox.checked) {
                ausbildungLabel.click();
                // Wait a bit for the page to refresh or apply the filter
                await new Promise(r => setTimeout(r, 1500));
            }
        }
    }
}

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

    let keepGoing = true;
    let currentPage = 1;

    let docToSearch = document;

    while (keepGoing && currentData.length < limit) {
        if (!isScraping) break;

        while (isPaused) {
            await new Promise(r => setTimeout(r, 500));
            if (!isScraping) break;
        }
        if (!isScraping) break;

        if (currentPage > 1) {
            // Recognize Aubi-Plus pagination button
            let nextBtn = docToSearch.querySelector('li.page-item a[rel="next"]') ||
                docToSearch.querySelector('a.page-link[aria-label*="Next"]') ||
                docToSearch.querySelector('a.page-link[aria-label*="Weiter"]') ||
                Array.from(docToSearch.querySelectorAll('ul.pagination a.page-link')).find(a => a.innerText.includes('»') || a.innerText.includes('Weiter') || a.innerText.includes('Nächste'));

            if (!nextBtn || !nextBtn.href) {
                console.log("No next page button found. Pagination ends.");
                break; // No more cards/pages found
            }

            try {
                // Because DOMParser resolves relative URLs differently, we might need absolute URL
                let nextUrl = nextBtn.href;
                if (nextUrl.startsWith('chrome-extension')) {
                    nextUrl = new URL(nextBtn.getAttribute('href'), 'https://www.aubi-plus.de').href;
                }

                console.log("Fetching next page: ", nextUrl);
                const res = await fetch(nextUrl);
                const text = await res.text();
                const parser = new DOMParser();
                docToSearch = parser.parseFromString(text, 'text/html');
            } catch (e) {
                console.error("Error fetching next page", e);
                break;
            }
        }

        const cards = docToSearch.querySelectorAll('.my-3.text-primary-dark.overflow-hidden.rounded-3');
        if (cards.length === 0) {
            console.log("No cards found on this page.");
            break; // No more cards found on this page
        }

        for (let i = 0; i < cards.length; i++) {
            while (isPaused) {
                await new Promise(r => setTimeout(r, 500));
                if (!isScraping) break;
            }
            if (!isScraping) break;

            if (currentData.length >= limit) break;

            // Look for the actual job link, not the "merkzettel" heart icon which has href="#"
            let linkElement = cards[i].querySelector('a.stretched-link') || cards[i].querySelector('h2 a') || cards[i].querySelector('a:not([href="#"])');
            if (cards[i].tagName === 'A') linkElement = cards[i];
            if (!linkElement) continue;

            let href = linkElement.href || linkElement.getAttribute('href');
            if (!href) continue;

            // Resolving URLs parsed by DOMParser from text
            if (href.startsWith('chrome-extension://')) {
                href = new URL(linkElement.getAttribute('href'), 'https://www.aubi-plus.de').href;
            } else if (href.startsWith('/')) {
                href = 'https://www.aubi-plus.de' + href;
            }

            try {
                const response = await fetch(href);
                const text = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(text, 'text/html');

                // Extract fields
                const companyNameEl = doc.querySelector('.fs-6.mb-0.lh-1');
                const companyName = companyNameEl ? companyNameEl.innerText.replace(/\s+/g, ' ').trim() : '';

                let address = '';
                const locationIcons = doc.querySelectorAll('.fa-location-dot');
                for (let icon of locationIcons) {
                    if (icon.nextElementSibling && icon.nextElementSibling.tagName === 'SPAN') {
                        address = icon.nextElementSibling.innerText.trim();
                        break;
                    }
                }

                let email = '';
                // Check class mail-protect, or ID emailbewerbung, or regex inside card-body
                const emailBewerbung = doc.querySelector('#emailbewerbung');
                if (emailBewerbung && emailBewerbung.href && emailBewerbung.href.includes('mailto:')) {
                    email = emailBewerbung.href.replace('mailto:', '').split('?')[0].trim();
                } else {
                    const mailtoLinks = Array.from(doc.querySelectorAll('a[href^="mailto:"]'));
                    const emailLink = mailtoLinks.find(a => a.href.includes('@'));
                    if (emailLink) {
                        email = emailLink.href.replace('mailto:', '').split('?')[0].trim();
                    } else {
                        // Fallback logic
                        const cardBodies = doc.querySelectorAll('.card-body.p-4');
                        for (let cb of cardBodies) {
                            const textContent = cb.innerText || '';
                            const ematch = textContent.match(/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/);
                            if (ematch) {
                                email = ematch[1];
                                break;
                            }
                        }
                    }
                }

                // Phone number
                const phoneEl = doc.querySelector('.phoneNumber');
                const phone = phoneEl ? phoneEl.innerText.trim() : '';

                if (!email) continue; // Skip if no email found

                if (companyName || email || address || phone) {
                    currentData.push({
                        company: companyName,
                        email: email,
                        address: address,
                        contact: '',
                        anrede: '',
                        link: href,
                        phone: phone
                    });

                    await new Promise(r => chrome.storage.local.set({ scrapedData: currentData }, r));
                    chrome.runtime.sendMessage({ action: 'progress', count: currentData.length });
                }

            } catch (err) {
                console.error("Error fetching details", err);
            }

            await new Promise(r => setTimeout(r, 1000));
        }

        currentPage++;
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
    const titleEl = await waitForElement('.mb-0.pe-5.pe-sm-0.text-md-center.suchmaschine-title', 5000) ||
        await waitForElement('.suchmaschine-title', 2000);
    if (titleEl) {
        const dangerSpan = titleEl.querySelector('.text-danger');
        if (dangerSpan) {
            const numText = dangerSpan.innerText.replace(/\D/g, '');
            const num = parseInt(numText, 10);
            return isNaN(num) ? 0 : num;
        }
    }
    return 0;
}

// Listen for popup actions
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
            // Already inside the loop, just toggled boolean
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
