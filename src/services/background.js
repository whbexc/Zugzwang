/**
 * Background Service Worker - Gatekeeper
 * Handles background license checks and extension lifecycle
 */

const API_URL = 'https://etxt.net/api/verify.php';
const isDevBuild = !chrome.runtime.getManifest().update_url;

// Listen for messages
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'progress' && request.status === 'waiting_captcha') {
        console.log('Scraper paused: Waiting for manual captcha solve in tab', sender.tab.id);
    }
});

/**
 * Periodic License Verification
 * Checks if the license is still active, not banned, or expired
 */
async function checkLicenseJob() {
    if (isDevBuild) {
        return;
    }

    const result = await chrome.storage.local.get(['license_key', 'is_activated', 'device_id']);

    if (result.is_activated && result.license_key && result.device_id) {
        try {
            const formData = new FormData();
            formData.append('key', result.license_key);
            formData.append('fingerprint', result.device_id);

            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.status !== 'active') {
                console.log('License no longer active:', data.message);
                await chrome.storage.local.set({ is_activated: false });
            }
        } catch (error) {
            console.error('Background Auth Error:', error);
            // Don't deactivate on transient network errors
        }
    }
}

// Alarm Listener
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'licenseCheck') {
        checkLicenseJob();
    }
});

// Setup on install/startup
chrome.runtime.onInstalled.addListener(() => {
    console.log('Extension installed/updated');
    createAlarm();
    checkLicenseJob();
});

chrome.runtime.onStartup.addListener(() => {
    console.log('Browser started');
    createAlarm();
    checkLicenseJob();
});

function createAlarm() {
    if (chrome.alarms) {
        chrome.alarms.create('licenseCheck', { periodInMinutes: 60 });
        console.log('Alarm created');
    } else {
        console.error('Alarms API not available. Check manifest permissions.');
    }
}
