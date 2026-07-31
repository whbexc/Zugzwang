<p align="center">
  <img src="src/ui/assets/logo-mark.png" alt="ZUGZWANG" width="120">
</p>

<h1 align="center">ZUGZWANG</h1>

<p align="center">
  Lead generation, enrichment, and outreach in one cross-platform desktop app for macOS, Linux, and Windows.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-0A84FF?style=for-the-badge">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-30D158?style=for-the-badge">
  <img alt="UI" src="https://img.shields.io/badge/UI-PySide6-5AC8FA?style=for-the-badge">
  <img alt="Automation" src="https://img.shields.io/badge/automation-Playwright-FF9F0A?style=for-the-badge">
<img alt="Version" src="https://img.shields.io/badge/version-1.1.0%20Beta%203-E5E5EA?style=for-the-badge&color=2C2C2E">
</p>

<p align="center">
  <b>Search.</b> <b>Scrape.</b> <b>Enrich.</b> <b>Review.</b> <b>Send.</b>
</p>

---

## Overview

ZUGZWANG is a PySide6 desktop application built for high-volume lead discovery and outbound workflow. It combines browser-based scraping, local lead persistence, enrichment, review, and SMTP outreach inside one interface.

It is designed for:

- local business discovery
- recruitment research
- apprenticeship/job lead collection
- outbound contact workflows
- cross-platform standalone usage (macOS, Linux, Windows)

## What It Does

### Multi-source scraping

- Google Maps
- Jobsuche / Bundesagentur
- Ausbildung.de
- Aubi-Plus
- Azubiyo

### Lead enrichment

- email extraction
- website discovery
- phone normalization
- address and city parsing
- social/profile fields where available

### Outreach workflow

- SMTP sending
- Gmail-safe broadcast mode
- recipient queue management
- inline queue editing
- manual recipient add dialog
- duplicate-send protection
- message-sensitive resend logic
- attachment persistence
- HTML preview
- sender profiles with autocomplete

### Local persistence

- SQLite-backed app memory
- search history
- outreach history
- saved sender settings
- saved attachment paths
- one-time upgrade reset for stale local UI state

## Product Flow

```text
Search -> Monitor -> Results -> Send
```

ZUGZWANG keeps that loop in one app instead of splitting it across separate scraper, spreadsheet, and mail tools.

## Core Screens

| Screen | Purpose |
|---|---|
| Dashboard | Recent jobs, activity, startup diagnostics, top-level stats |
| Search | Query builder, source selection, radius/city filters, history reuse |
| Monitor | Live progress, runtime metrics, activity stream, pause/resume/stop |
| Results | Persistent lead library, dedupe-aware review, export-ready records |
| Send | SMTP broadcast workflow, queue control, inline email editing, sender profiles, attachments, HTML preview |
| Settings / Logs | Runtime config, cache cleanup, diagnostics, activation, product state |

## Feature Snapshot

### Scraping engine

- Playwright-based browser automation
- source-specific scraper modules
- background orchestration to keep UI responsive
- CAPTCHA handoff flow
- rate limiting and session management
- direct fallback paths for unstable packaged-search flows

### Lead model

- company name
- category
- email
- phone
- website
- address
- city / postal code
- source metadata

### Sending engine

- STARTTLS / SSL SMTP support
- Gmail per-recipient fresh-session mode
- Gmail Anti-Lockdown Protection with 45s+ velocity floor, human-like randomized jitter (+5-18s), and 2.5-minute micro-batch cooldowns every 12 emails
- Smart 5-minute backoff when SMTP rate-limit or throttling codes (421/450/451/452/550) are detected
- Auto-cleanup of sent company-specific PDF cover letters to optimize disk space while preserving raw CV attachments
- reconnect and retry logic
- test-send and full broadcast flows
- sent-history tracking
- sender identity profiles
- inline recipient editing and manual-add flow
- resend allowed when the message content changes

### Storage model

- local AppData settings
- local app memory database
- dedupe via stable lead identifiers
- persisted attachment and sender state
- targeted upgrade cleanup that preserves scraped data, send data, and Pro activation

## Tech Stack

- Python 3.11+
- PySide6
- PyQt-Fluent-Widgets
- Playwright
- SQLite
- openpyxl
- httpx
- certifi

## Project Structure

```text
src/
  core/        models, config, security, events
  services/    scrapers, browser session, export/import, orchestrator
  ui/          pages, dialogs, theme, components
assets/        installer and branding assets
tests/         verification and regression tests
```

## Quick Start

### Requirements

- Python 3.11+
- Operating System: **macOS 11+**, **Linux** (Ubuntu, Debian, Fedora, Arch), or **Windows 10/11**
- Chromium installed through Playwright

### Setup

#### 🍎 macOS (Apple Silicon & Intel)

```bash
# 1. Clone repository and enter directory
git clone https://github.com/whbexc/Zugzwang.git
cd Zugzwang

# 2. Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies & Playwright Chromium browser
pip install -r requirements.txt
playwright install chromium

# 4. Launch ZUGZWANG
python3 main.py
```

#### 🐧 Linux (Ubuntu, Debian, Fedora, Arch)

```bash
# 1. Clone repository and enter directory
git clone https://github.com/whbexc/Zugzwang.git
cd Zugzwang

# 2. Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies & Playwright Chromium browser (including OS dependencies)
pip install -r requirements.txt
playwright install --with-deps chromium

# 4. Launch ZUGZWANG
python3 main.py
```

#### 🪟 Windows (10 & 11)

```powershell
# 1. Clone repository and enter directory
git clone https://github.com/whbexc/Zugzwang.git
cd Zugzwang

# 2. Create and activate Python virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies & Playwright Chromium browser
pip install -r requirements.txt
playwright install chromium

# 4. Launch ZUGZWANG
python main.py
```

## Build

### Build local bundle

```powershell
python build_with_browsers.py
```

### Build Windows installer

```powershell
iscc installer.iss
```

Legacy fallback:

```powershell
makensis installer.nsi
```

## Current Version

**1.1.0 Beta 3**

Recent work includes:

- Multi-Email Extraction with Zero Duplicates — Scraper now captures every unique department and employee email address from an employer's website while automatically dropping identical duplicate email addresses across Google Maps listings
- SMTP Credential Sanitization & Broadcast Auto-Deduplication — Automatically strips non-breaking and zero-width spaces from copied Gmail App Passwords and deduplicates queue recipients to protect sender domain reputation

- Gmail Anti-Lockdown Protection — comprehensive SMTP throttling engine featuring a safe 45s+ velocity floor, human-like randomized jitter (+5-18s), automatic 2.5-minute micro-batch coffee breaks every 12 emails, and smart 5-minute backoff on server throttling
- Automated Sent-PDF Disk Optimization — automatically cleans up company-specific 11 MB PDF cover letters immediately after SMTP send confirmation, keeping your exports directory slim while permanently preserving your uploaded CV templates and lead spreadsheets
- Always-On HTML Email Styling & Inline Signature Embedding — automatically formats every outbound email with crisp paragraphs, clean bullet lists, German grammar placeholder replacement ('in Ihrer Einrichtung'), and embeds your handwritten blue signature inline at the bottom of the message text
- macOS Apple Dock Icon Polish — scaled down squircle icon to 82% canvas width with standard Apple Dock padding to match the exact visual weight and dimensions of native macOS app icons
- Fail-Forward Batch Exports — seamlessly falls back to attaching your raw uploaded PDF for leads that exceed your daily custom PDF limit without halting the workflow
- Auto-Clamped Broadcasting — mass email broadcasts now automatically clamp to your remaining limit instead of blocking the entire batch
- Dynamic Anschreiben Personalization — automatically generate perfectly tailored and personalized cover letters for every single lead
- Intrusive Popup Removal — completely removed hard-blocking 'Activate Pro' dialogs from all export and email functions, replacing them with elegant banners
- Edit Page Redesign — comprehensive rewrite of the editor UI for better responsiveness, cleaner spacing, and strict adherence to the premium macOS dark theme
- Ausbildung Engine Upgrade — completely refactored the extraction engine to support robust URL-based radius parameters and true infinite-scroll pagination
- Scraping Latency Optimizations — massively reduced search latency by stripping out legacy hardcoded delays and streamlining intelligent browser timeouts
- Visual Polish — fixed dark artifacting behind popup text and resolved UI layout overflows across the Settings and Email Sender pages

- separate internal app build tracking so future hotfixes can force updates even when the visible version string stays the same
- one-time upgrade reset of stale local UI/app state after update
- scraped leads, sent-email history, send drafts, and Pro activation preserved across that reset
- atomic settings persistence with backup recovery for license state, SMTP setup, send drafts, and sender profiles
- machine ID recovery from the persisted local machine ID file if settings ever load without it
- Send page protection against accidental SMTP host/port loss during local edits or clear actions
- reduced startup/dashboard refresh pressure to improve Google Maps launch responsiveness and avoid false temporary freeze behavior
- sender profiles with saved Gmail identities and password autofill
- recipient queue inline editing fixes with solid in-row editor rendering
- manual recipient add dialog styled to match the app
- clear-sent-history control and message-sensitive resend tracking for the same recipient
- cleaner activity log filtering so internal startup/activation traces stay out of the user activity feed
- stronger Jobsuche filter, radius, Detailansicht, and Kontakt/CAPTCHA recovery behavior
- duplicate headed CAPTCHA solver suppression and cleaner shutdown handling per job
- recurring post-'What's New' upgrade prompting for unsubscribed users without re-prompting activated installs
- trial-to-Pro max-results recovery so old trial-capped search values do not stay stuck after activation
- resend logic now allows the same email when the message changed
- Gmail per-recipient fresh-session delivery hardening
- packaged Google Maps search fallback improvements

## Licensing

ZUGZWANG includes:

- a daily free trial
- a machine-bound Pro activation flow

The repository also contains developer-side license utilities for local operations and support workflows.

## Data & Privacy

ZUGZWANG stores local application state in AppData, including:

- settings
- logs
- screenshots
- app memory database

On version upgrades, the app can refresh stale cached local state once to avoid carrying old UI bugs forward. That reset is designed to preserve scraped leads, send-related state, outreach history, and Pro/license state.

You remain responsible for how scraped data and outbound email are used.

## Development Notes

This codebase is optimized around:

- non-blocking UI behavior
- background persistence
- source-specific scraper isolation
- Windows packaging and standalone distribution

Primary folders:

- `src/ui` for app pages and dialogs
- `src/services` for scraping and orchestration
- `src/core` for config, models, events, and security

## Roadmap Direction

High-value next additions:

- project workspaces
- lead status pipeline
- saved templates with personalization
- stronger search continuation
- verification and skip-contacted rules

## Disclaimer

Users are responsible for complying with:

- target platform terms
- anti-spam and outreach rules
- privacy and data protection law

---

<p align="center">
  <b>ZUGZWANG</b><br>
  Windows desktop scraping and outreach, built for speed.
</p>
