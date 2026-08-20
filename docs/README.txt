ZUGZWANG 1.1.0 Beta5.1
Professional Cross-Platform Lead Generation, Enrichment & Outreach Suite

OVERVIEW:
ZUGZWANG is a surgical, high-density desktop application designed for rapid lead extraction, recruitment automation, and personalized email campaigns. Engineered with an ultra-responsive dark mode UI inspired by modern macOS aesthetics.

SUPPORTED PLATFORMS:
- macOS 11+ (Apple Silicon M1/M2/M3/M4 & Intel 64-bit)
- Windows 10 or 11 (64-bit)
- Linux (Ubuntu, Debian, Fedora, Arch)
- ~1.5 GB free disk space
- No separate Playwright or Chrome installation required (browser engine is bundled)

MACOS GATEKEEPER NOTICE (IMPORTANT):
When downloading the standalone macOS release (.zip) from GitHub, macOS Gatekeeper may show an "app is damaged" warning because the bundle is ad-hoc signed. To remove the quarantine attribute before launching, open Terminal and run:
    xattr -cr ~/Downloads/ZUGZWANG.app
(If placed in Applications, run: xattr -cr /Applications/ZUGZWANG.app)

KEY FEATURES (1.1.0 Beta5.1):
1. Multi-Engine Lead Harvesting:
   - Bundesagentur für Arbeit (Jobsuche API & Web Scraper)
   - Google Maps Business Lead Extractor
   - AubiPlus, Azubiyo, Ausbildung.de & Das Örtliche Scrapers
2. Integrated Email Campaign Sender:
   - Direct SMTP outreach with live progress tracking
   - Personalized template variables ({{FIRMA}}, {{ANSPRECHPARTNER}}, {{ANREDE}})
   - Multi-format letter template previewing (PDF, DOCX, XLSX, CSV, HTML, TXT)
3. Smart Automation:
   - Automatic background updates & version checks
   - SQLite WAL-mode caching & deduplication
   - Excel / CSV / JSON high-speed export

QUICK START (STANDALONE DESKTOP):
1. macOS: Extract ZUGZWANG_macOS.zip, run the xattr command above, and open ZUGZWANG.app.
   Windows: Run ZUGZWANG_Setup.exe and launch from Start Menu or Desktop.
   Linux: Extract ZUGZWANG_Linux.tar.gz and execute ./ZUGZWANG.
2. Configure your search parameters in the Jobsuche, Maps, or Scrapers tab.
3. Click "Start Extraction" to begin harvesting leads.
4. Export leads to CSV/Excel or send outreach emails directly from the Send tab.

SUPPORT & LICENSE:
Licensed under the MIT License. Copyright (c) 2024-2026 ZUGZWANG.
For technical assistance, documentation, or feature requests, visit https://github.com/whbexc/Zugzwang

