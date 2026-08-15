import re

def fix_file(filename):
    with open(filename, "r") as f:
        content = f.read()

    # 1. Add import if missing
    if "LicenseManager" not in content:
        content = content.replace("from ..core.models import", "from ..core.security import LicenseManager\nfrom ..core.models import")

    # 2. Add LicenseManager.record_extraction() before yield lead / record
    if "yield record" in content and "LicenseManager.record_extraction()" not in content:
        content = content.replace("yield record", "LicenseManager.record_extraction()\n                    yield record")
    elif "yield lead" in content and "LicenseManager.record_extraction()" not in content:
        content = content.replace("yield lead", "LicenseManager.record_extraction()\n                            yield lead")

    with open(filename, "w") as f:
        f.write(content)

fix_file("src/services/dasoertliche_scraper.py")
fix_file("src/services/ausbildung_scraper.py")


# 1.1.0 Beta5
