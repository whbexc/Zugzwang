/**
 * Auth Helper for License Verification
 */

const API_URL = 'https://etxt.net/api/verify.php';

const Auth = {
    /**
     * Treat unpacked/local builds as development so we can skip license UX there
     * without changing the packaged production flow.
     */
    isDevBuild() {
        const manifest = chrome.runtime.getManifest();
        return !manifest.update_url;
    },

    /**
     * Generates a stable device fingerprint
     */
    async getFingerprint() {
        return new Promise((resolve) => {
            chrome.storage.local.get(['device_id'], (result) => {
                if (result.device_id) {
                    resolve(result.device_id);
                } else {
                    // Generate a random ID if not exists
                    const newId = 'id-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
                    chrome.storage.local.set({ device_id: newId }, () => {
                        resolve(newId);
                    });
                }
            });
        });
    },

    /**
     * Verifies the license key with the server
     */
    async verifyLicense(key) {
        if (this.isDevBuild()) {
            await chrome.storage.local.set({
                license_key: 'DEV-BUILD',
                is_activated: true,
                activation_date: new Date().toISOString()
            });
            return { success: true, message: 'Development build activated locally.' };
        }

        try {
            const fingerprint = await this.getFingerprint();

            const formData = new FormData();
            formData.append('key', key);
            formData.append('fingerprint', fingerprint);

            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.status === 'active') {
                await chrome.storage.local.set({
                    license_key: key,
                    is_activated: true,
                    activation_date: new Date().toISOString()
                });
                return { success: true, message: data.message };
            } else {
                // If the server says anything other than active, we revoke local access
                await chrome.storage.local.set({ is_activated: false });
                return { success: false, message: data.message || 'Verification failed', status: data.status };
            }
        } catch (error) {
            console.error('Auth Error:', error);
            // On network error, we don't necessarily want to lock them out immediately 
            // but we'll return failure so the UI can decide.
            return { success: false, message: 'Server connection error', isNetworkError: true };
        }
    },

    /**
     * Checks if the extension is currently activated (Local check)
     */
    async checkActivation() {
        if (this.isDevBuild()) {
            return true;
        }

        return new Promise((resolve) => {
            chrome.storage.local.get(['license_key', 'is_activated'], async (result) => {
                if (result.is_activated && result.license_key) {
                    resolve(true);
                } else {
                    resolve(false);
                }
            });
        });
    },

    /**
     * Performs a live server check for the currently stored license
     */
    async performLiveCheck() {
        if (this.isDevBuild()) {
            return { success: true, message: 'Development build skips live license checks.' };
        }

        return new Promise((resolve) => {
            chrome.storage.local.get(['license_key', 'is_activated'], async (result) => {
                if (result.is_activated && result.license_key) {
                    const verification = await this.verifyLicense(result.license_key);
                    resolve(verification);
                } else {
                    resolve({ success: false, message: 'No active session' });
                }
            });
        });
    }
};

// Export to window if not in a module environment
window.Auth = Auth;
