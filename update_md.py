import re
from pathlib import Path

# Update README.md
readme = Path('README.md')
text = readme.read_text('utf-8')

# Replace the version badge
text = text.replace('version-1.0.94-E5E5EA', 'version-1.1.0%20Beta-E5E5EA')

# Replace the Current Version header
text = text.replace('**1.0.94**', '**1.1.0 Beta**')

# Insert the new features into the 'Recent work includes:' section
new_features = """- Fail-Forward Batch Exports — seamlessly falls back to attaching your raw uploaded PDF for leads that exceed your daily custom PDF limit without halting the workflow
- Auto-Clamped Broadcasting — mass email broadcasts now automatically clamp to your remaining limit instead of blocking the entire batch
- Dynamic Anschreiben Personalization — automatically generate perfectly tailored and personalized cover letters for every single lead
- Intrusive Popup Removal — completely removed hard-blocking 'Activate Pro' dialogs from all export and email functions, replacing them with elegant banners
- Edit Page Redesign — comprehensive rewrite of the editor UI for better responsiveness, cleaner spacing, and strict adherence to the premium macOS dark theme
- Ausbildung Engine Upgrade — completely refactored the extraction engine to support robust URL-based radius parameters and true infinite-scroll pagination
- Scraping Latency Optimizations — massively reduced search latency by stripping out legacy hardcoded delays and streamlining intelligent browser timeouts
- Visual Polish — fixed dark artifacting behind popup text and resolved UI layout overflows across the Settings and Email Sender pages
"""

text = text.replace('Recent work includes:\n', 'Recent work includes:\n\n' + new_features)

readme.write_text(text, 'utf-8')

# Update ZUGZWANG_DOCUMENTATION.md
doc = Path('ZUGZWANG_DOCUMENTATION.md')
doc_text = doc.read_text('utf-8')
doc_text = doc_text.replace('ZUGZWANG v1.2.0', 'ZUGZWANG v1.1.0 Beta')
doc.write_text(doc_text, 'utf-8')

print("Markdown files updated.")
