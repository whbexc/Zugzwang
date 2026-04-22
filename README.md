<p align="center">
  <img src="src/ui/assets/logo-mark.png" alt="ZUGZWANG" width="120">
</p>

<h1 align="center">ZUGZWANG</h1>

<p align="center">
  Lead generation, enrichment, and outreach in one Windows desktop app.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0A84FF?style=for-the-badge">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-30D158?style=for-the-badge">
  <img alt="UI" src="https://img.shields.io/badge/UI-PySide6-5AC8FA?style=for-the-badge">
  <img alt="Automation" src="https://img.shields.io/badge/automation-Playwright-FF9F0A?style=for-the-badge">
<img alt="Version" src="https://img.shields.io/badge/version-1.0.9b-E5E5EA?style=for-the-badge&color=2C2C2E">
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
- Windows-first standalone usage

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
- duplicate-send protection
- attachment persistence
- HTML preview

### Local persistence

- SQLite-backed app memory
- search history
- outreach history
- saved sender settings
- saved attachment paths

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
| Send | SMTP broadcast workflow, queue control, attachments, HTML preview |
| Settings / Logs | Runtime config, sender setup, diagnostics, product state |

## Feature Snapshot

### Scraping engine

- Playwright-based browser automation
- source-specific scraper modules
- background orchestration to keep UI responsive
- CAPTCHA handoff flow
- rate limiting and session management

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
- reconnect and retry logic
- test-send and full broadcast flows
- sent-history tracking

### Storage model

- local AppData settings
- local app memory database
- dedupe via stable lead identifiers
- persisted attachment and sender state

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
- Windows 10 or Windows 11
- Chromium installed through Playwright

### Setup

```powershell
git clone https://github.com/whbexc/Zugzwang.git
cd Zugzwang

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium

python main.py
```

## Build

### Build local bundle

```powershell
python build_with_browsers.py
```

### Build Windows installer

```powershell
makensis installer.nsi
```

## Current Version

**1.0.9b**

Recent work includes:

- Ausbildung.de pagination improvements
- runtime progress reliability fixes
- Windows/UI stability work
- Gmail sender hardening
- persistent attachments in Send page

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
