# ZUGZWANG

**Professional lead generation and recruitment research desktop application.**  
Scrapes Google Maps and Jobsuche (Bundesagentur für Arbeit) to collect structured business and contact data, with automated email discovery from company websites.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Project Structure](#project-structure)
3. [Stack Justification](#stack-justification)
4. [Setup & Installation (Development)](#setup--installation-development)
5. [Running the Application](#running-the-application)
6. [Building the Windows .exe](#building-the-windows-exe)
7. [Creating the Installer](#creating-the-installer)
8. [Usage Guide](#usage-guide)
9. [Configuration](#configuration)
10. [Data Model](#data-model)
11. [Export Formats](#export-formats)
12. [Running Tests](#running-tests)
13. [Extending the Application](#extending-the-application)

---

## Architecture

ZUGZWANG uses a strict **layered architecture** with clean separation of concerns:

```
┌──────────────────────────────────────────────────────────────┐
│                        UI Layer (PySide6)                     │
│  MainWindow → Sidebar → Pages (Dashboard, Search, Results,   │
│               Monitor, Settings, LogViewer)                   │
└───────────────────────────┬──────────────────────────────────┘
                            │ Signals / EventBus
┌───────────────────────────▼──────────────────────────────────┐
│                    Orchestration Layer                        │
│          ScrapingOrchestrator (threading + asyncio)           │
└──────────┬─────────────────────────┬─────────────────────────┘
           │                         │
┌──────────▼──────────┐   ┌──────────▼──────────┐
│   Google Maps       │   │   Jobsuche Scraper   │
│   Scraper Service   │   │   Service            │
└──────────┬──────────┘   └──────────┬───────────┘
           └──────────┬──────────────┘
┌──────────────────────▼──────────────────────────────────────┐
│              Browser Automation Layer (Playwright)            │
│  BrowserSession — rate limiting, retry, anti-detection,       │
│  user-agent rotation, proxy support                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Extraction / Parsing Layer                       │
│  EmailExtractor, WebsiteCrawler                               │
│  Pure functions — unit-testable, zero side effects            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│            Persistence / Export Layer                         │
│  ExportService — CSV, Excel, JSON, SQLite                     │
│  ConfigManager — AppData JSON persistence                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Thread isolation:** The scraping orchestrator runs in a dedicated background thread with its own `asyncio` event loop. The UI thread never blocks — all cross-thread communication uses Qt's queued signal/slot mechanism and the central `EventBus`.

**EventBus:** A simple pub/sub bus decouples services from UI. Scraper services `emit()` events; UI pages `subscribe()` to them. Neither side holds references to the other.

**Async scraping with Playwright:** Each scraper is a pure `async` generator — yielding `LeadRecord` instances as they are discovered. This enables natural streaming to the UI (no buffering all results first).

**Pure extraction functions:** All email/phone/URL parsing lives in `email_extractor.py` as pure functions with no I/O, making them trivially unit-testable without mocking.

**Configurable without code changes:** Selectors, email discovery paths, delays, domain filters, and user agents are all runtime-configurable through the Settings page and persisted to `AppData`.

---

## Project Structure

```
zugzwang/
├── main.py                         # Entry point
├── requirements.txt
├── zugzwang.spec                   # PyInstaller build spec
├── installer.nsi                   # NSIS Windows installer script
├── version_info.txt                # Windows .exe version metadata
│
├── src/
│   ├── core/                       # Domain models, config, logging, events
│   │   ├── models.py               # LeadRecord, SearchConfig, ScrapingJob, AppSettings
│   │   ├── config.py               # ConfigManager (AppData JSON persistence)
│   │   ├── logger.py               # Structured logging + UI log sink
│   │   └── events.py               # Thread-safe EventBus
│   │
│   ├── services/                   # Business logic — no UI imports
│   │   ├── browser.py              # Playwright BrowserSession (retry, rate limit)
│   │   ├── email_extractor.py      # Pure email extraction/normalization functions
│   │   ├── website_crawler.py      # Shallow contact-page crawler
│   │   ├── maps_scraper.py         # Google Maps scraper
│   │   ├── jobsuche_scraper.py     # Jobsuche (BA) scraper
│   │   ├── export_service.py       # CSV/Excel/JSON/SQLite export
│   │   └── orchestrator.py         # Job lifecycle management
│   │
│   └── ui/                         # PySide6 UI — no business logic
│       ├── stylesheet.py           # Global QSS dark theme
│       ├── components.py           # Reusable widgets
│       ├── main_window.py          # Root window + navigation
│       ├── dashboard_page.py       # Stats overview
│       ├── search_page.py          # Job configuration form
│       ├── results_page.py         # Live results table + detail panel
│       ├── monitor_page.py         # Progress monitor + controls
│       ├── settings_page.py        # Application settings
│       └── log_viewer_page.py      # Log viewer
│
├── tests/
│   ├── conftest.py
│   └── test_extraction.py          # Unit tests for parsing logic
│
├── assets/
│   └── icon.ico                    # Application icon
│
└── docs/
    ├── sample_export.csv           # Example exported data
    └── ARCHITECTURE.md
```

---

## Stack Justification

**Python + PySide6 + Playwright** was chosen over Electron + React + TypeScript for the following reasons:

| Concern | Python/PySide6/Playwright | Electron/React/TypeScript |
|---|---|---|
| Browser automation maturity | ✅ Playwright is the gold standard | ✅ Puppeteer/Playwright available |
| Native Windows feel | ✅ Qt renders native controls | ⚠ Chromium shell, not native |
| Installer size | ✅ ~80MB with Chromium | ⚠ 120MB+ baseline |
| Anti-detection capability | ✅ Full Playwright CDP access | ✅ Same |
| Data processing (parsing, regex, SQLite) | ✅ Python ecosystem | ⚠ Node ecosystem less ergonomic |
| Packaging to single .exe | ✅ PyInstaller | ✅ electron-builder |
| Dev environment simplicity | ✅ Single language | ⚠ Node + npm build toolchain |

---

## Setup & Installation (Development)

### Requirements
- Python 3.11+
- Windows 10/11 (production target), macOS/Linux also work for development
- 4GB RAM minimum (Chromium + Python)

### Steps

```bash
# 1. Clone repository
git clone https://github.com/yourorg/zugzwang.git
cd zugzwang

# 2. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser (Chromium only — ~130MB)
playwright install chromium

# 5. Run the application
python main.py
```

---

## Running the Application

```bash
python main.py
```

The application window will open. No further setup required — settings are auto-initialized on first launch at:
- **Windows:** `%APPDATA%\ZUGZWANG\settings.json`
- **macOS:** `~/.config/ZUGZWANG/settings.json`

Logs are written to `%APPDATA%\ZUGZWANG\logs\`.

---

## Building the Windows .exe

### Step 1 — Install PyInstaller

```bash
pip install pyinstaller
```

### Step 1 — Build & Bundle (Recommended)

The project includes an automation script that runs PyInstaller, installs the necessary Playwright browsers, and bundles them into the distribution folder automatically.

```bash
# This script handles everything: PyInstaller + Browser Bundling
python build_with_browsers.py
```

- **Output:** `dist/ZUGZWANG/`
- **Main Executable:** `dist/ZUGZWANG/ZUGZWANG.exe`
- **Browsers:** Bundled in `dist/ZUGZWANG/browsers/`

### Step 2 — Manual Build (Alternative)

If you prefer to run the steps manually:

```bash
# 1. Run PyInstaller
pyinstaller zugzwang.spec --clean

# 2. Manually copy Playwright chromium folder to dist/ZUGZWANG/browsers/
# On Windows, browsers are typically at %LOCALAPPDATA%\ms-playwright\
```

### Step 4 — Test the build

```bash
dist\ZUGZWANG\ZUGZWANG.exe
```

---

## Creating the Installer

### Requirements
- [NSIS 3.x](https://nsis.sourceforge.io/) installed

### Build

```bash
# After successfully building the .exe (Step 2 above):
makensis installer.nsi
```

Output: `ZUGZWANG_Setup_v1.0.0.exe` — a professional Windows installer with:
- Welcome screen, license page, directory selection
- Start Menu and Desktop shortcuts
- Add/Remove Programs entry
- Clean uninstaller

---

## Distribution Checklist

To share ZUGZWANG with other users as a standalone program:

1.  **Build the Distribution Folder:**
    Run `python build_with_browsers.py`. This creates the `dist/ZUGZWANG` folder containing everything needed (the code, dependencies, and the Chromium browser).
2.  **Choose your Sharing Method:**
    *   **Option A (Zip):** Compress the **entire** `dist/ZUGZWANG` folder into a `.zip` file. Users must extract the zip and run `ZUGZWANG.exe`.
    *   **Option B (Installer - Recommended):** Install [NSIS](https://nsis.sourceforge.io/) and run `makensis installer.nsi`. This produces a single `ZUGZWANG_Setup_v1.0.0.exe` that looks and feels like a professional Windows app.
3.  **What NOT to do:**
    *   Do **NOT** just send the `ZUGZWANG.exe` file alone. It will crash because it cannot find its internal libraries or the browser.
    *   Do **NOT** send your personal `settings.json` or `export/` folder.

---

## Usage Guide

### Starting a Search

1. Click **New Search** in the sidebar or dashboard
2. Select data source: **Google Maps** or **Jobsuche (BA)**
3. Enter job/profession type and location
4. Configure options (max results, email scraping, headless mode)
5. Click **▶ Start Scraping**

### During Scraping

- The **Monitor** page shows live progress, stats, and log output
- Use **⏸ Pause** to temporarily pause (resumes from current position)
- Use **⏹ Stop** to cancel the job

### Viewing Results

- Results stream live to the **Results** page as they are found
- Filter by source, email status, or free-text search
- Click any row to see full details in the right panel

### Exporting Data

From the Results page, use the export buttons:
- **CSV** — comma-separated, UTF-8 with BOM (Excel-compatible)
- **Excel** — formatted XLSX with hyperlinks and auto-filter
- **JSON** — normalized array of lead objects
- **Save Project** — SQLite .db file preserving full job history

### Settings

Configure scraping behavior, email discovery paths, domain filters, proxy, and logging from the **Settings** page.

---

## Configuration

All settings are persisted to `settings.json` in AppData. Key settings:

| Setting | Default | Description |
|---|---|---|
| `default_delay_min` | 1.5 | Minimum seconds between requests |
| `default_delay_max` | 4.0 | Maximum seconds between requests |
| `default_max_results` | 100 | Default result limit per job |
| `default_headless` | true | Run browser without visible window |
| `default_scrape_emails` | true | Auto-crawl websites for emails |
| `email_discovery_paths` | impressum, kontakt, karriere… | Paths to check for emails |
| `blacklisted_domains` | [] | Domains to skip entirely |
| `debug_screenshots` | false | Capture screenshots on failures |
| `proxy_url` | null | HTTP proxy for all requests |

---

## Data Model

Every scraped record is normalized into a `LeadRecord`:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique record identifier |
| `source_type` | enum | `google_maps` or `jobsuche` |
| `company_name` | string | Business or employer name |
| `job_title` | string | Job title (Jobsuche only) |
| `category` | string | Business category/profession |
| `email` | string | Best contact email found |
| `email_source_page` | URL | Page where email was discovered |
| `phone` | string | Contact phone number |
| `website` | URL | Company website |
| `address` | string | Full street address |
| `city` | string | City |
| `region` | string | State/region |
| `postal_code` | string | Postal code |
| `country` | string | Country |
| `rating` | float | Google Maps rating (Maps only) |
| `review_count` | int | Number of reviews (Maps only) |
| `description` | string | Business/job description snippet |
| `publication_date` | string | Job posting date (Jobsuche only) |
| `source_url` | URL | Original listing URL |
| `maps_url` | URL | Google Maps place URL |
| `search_query` | string | Query that produced this result |
| `scraped_at` | ISO datetime | When record was collected |

---

## Export Formats

### CSV
UTF-8 with BOM, all 23 columns, suitable for Excel, Google Sheets, and any data tool.

### Excel (XLSX)
- Professional formatting with dark header row
- Color-coded email and website cells
- Clickable hyperlinks for URLs and mailto
- Auto-filter on all columns
- Frozen header row

### JSON
Array of normalized lead objects, all fields included.

### SQLite (.db)
Full project persistence including job metadata and all result records. Load from File → Open Project.

---

## Running Tests

```bash
# Install test dependencies
pip install pytest

# Run all unit tests
pytest tests/ -v

# Run with coverage
pip install pytest-cov
pytest tests/ -v --cov=src --cov-report=term-missing
```

Tests cover:
- Email extraction from text and HTML
- Email source classification
- URL and phone normalization
- Email deduplication and prioritization
- LeadRecord serialization/deserialization
- SearchConfig defaults and validation

---

## Extending the Application

### Adding a New Scraper Source

1. Create `src/services/new_portal_scraper.py` implementing an `async def scrape()` generator that yields `LeadRecord` instances
2. Add the new `SourceType` enum value to `src/core/models.py`
3. In `src/services/orchestrator.py`, add the instantiation branch in `_run_job_async()`
4. Add a source button in `src/ui/search_page.py`

### Adding a New Export Format

Add a method to `src/services/export_service.py` and wire a button in `src/ui/results_page.py`.

### Configuring New Email Discovery Paths

Open Settings → Email Discovery Paths and add new paths (one per line). No code changes required.

---

## Compliance Notes

- Scraping is rate-limited by default (1.5–4.0 second delays)
- `robots.txt` respect is configurable (enabled by default)
- Domain blacklist/whitelist available for targeted scraping
- User-agent rotation mimics real browser sessions
- Crawl depth is shallow and controlled (configurable max pages per domain)
- Users are responsible for compliance with target sites' terms of service

---

## License

Commercial proprietary software. All rights reserved.
