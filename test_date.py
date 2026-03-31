import sys
from datetime import datetime

scraped_at = datetime.utcnow().isoformat()
print(f"Scraped At: {scraped_at}")

dt = scraped_at
if isinstance(dt, str):
    dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()

print(f"Parsed DT: {repr(dt)}")
print(f"Now: {repr(now)}")

delta = (now - dt).total_seconds()
print(f"Delta: {delta}")
