import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.email_extractor import extract_emails_from_html, MAX_PROCESS_SIZE

# Create a 500KB HTML
large_body = "word " * 100000
test_html = f"<html><body>{large_body} contact@target.com </body></html>"

print(f"Original size: {len(test_html)} bytes")
emails = extract_emails_from_html(test_html)
print(f"Extracted: {emails}")

# Verify it found it (because we take first and last half)
if "contact@target.com" in emails:
    print("SUCCESS: Found email in trailing part of trimmed HTML")
else:
    print("FAILURE: Email lost in trimming")
