# ZUGZWANG 

**The surgical, professional-grade lead generation engine for modern recruitment and market research.**

ZUGZWANG is a high-density desktop application designed to scrape, enrich, and export professional lead data from global sources including **Google Maps** and **Jobsuche (BA)**. Built with the "Obsidian Core" design philosophy, it merges industrial-strength performance with a premium, minimalist macOS-inspired aesthetic.

---

## ⚡ Executive Summary

Whether you are hunting for corporate hiring signals or local business contact data, ZUGZWANG automates the entire discovery pipeline—from browser orchestration to deep-website email discovery—all while maintaining a surgical, terminal-inspired user experience.

-   **Multi-Source Intelligence:** Unified scraping for Google Maps and federal job listings.
-   **Deep Discovery:** Automated website crawling to extract verified emails and social profiles.
-   **Obsidian Core UI:** High-density, performance-optimized interface with premium glassmorphism.
-   **Enterprise Persistence:** Full SQLite project support with formatted CSV and Excel (XLSX) exports.
-   **Trial Ready:** Built-in "20 Scraps Per Day" free trial mode for immediate onboarding.

---

## 🏗 Industrial Architecture

ZUGZWANG is engineered for stability and speed, utilizing a strictly decoupled layered architecture:

*   **UI Layer:** PySide6 (Qt) with custom Obsidian Core components.
*   **Orchestration:** Multi-threaded `asyncio` loop for non-blocking browser control.
*   **Automation:** Playwright (Chromium) with advanced anti-detection and rate-limiting.
*   **Extraction:** Pure-function regex and HTML parsing for surgical precision.

### Project Anatomy
-   `/src/core`: Domain models, Security Engine, and Persistence.
-   `/src/services`: Scraper logic, Browser orchestration, and Export engines.
-   `/src/ui`: Premium Pages (Dashboard, Search, Monitor, Results).
-   `/assets`: Visual identity and branding assets.

---

## 🚦 Developer Quickstart

### Prerequisites
-   Python 3.11+
-   Windows 10/11 (Target OS)
-   [NSIS 3.x](https://nsis.sourceforge.io/) (for building the installer)

### Setup
```bash
# 1. Clone & Enter
git clone https://github.com/whbexc/Zugzwang.git
cd Zugzwang

# 2. Virtualize & Install
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Initialize Browser
playwright install chromium

# 4. Launch
python main.py
```

---

## 📦 Build & Distribution

ZUGZWANG is designed to be shared as a professional standalone toolkit.

1.  **Generate Bundle:** Run `python build_with_browsers.py` to create the `dist/` folder.
2.  **Create Setup:** Run `makensis installer.nsi` to generate a professional Windows Installer (`.exe`).

---

## 🔑 Licensing & Trial

ZUGZWANG operates on a **Daily Free Trial** model:
-   **Unbalanced Users:** 20 free lead extractions every 24 hours. No activation required to start.
-   **Pro License:** Unlock unlimited extractions and premium features with a unique hardware-locked key.

*To manage licenses, use the built-in `generate_key.py` (Developer use only) to sign keys based on the unique Machine ID found in the app settings.*

---

## 🛡 Security & Privacy

This project is hardened to protect your data and intellectual property.
-   **Protected Files:** `settings.json`, `app_memory.db`, and `export/` folders are automatically ignored by GitHub to prevent accidental data leaks.
-   **Hardware Fingerprinting:** Licenses are cryptographically bound to the user's specific hardware ID.

---

## ⚖ Ethics & Compliance
*ZUGZWANG is a tool for professional research. Users are responsible for complying with the Terms of Service of target platforms and local data protection regulations (GDPR, etc.).*

**Designed by whbexc & Antigravity.**
