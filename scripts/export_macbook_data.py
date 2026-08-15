"""
Export all ZUGZWANG user data, settings, databases, search history, and templates
into a portable ZIP archive ready to be imported on macOS (~/.config/ZUGZWANG).
"""

import os
import sys
import zipfile
from pathlib import Path

def create_macbook_export():
    # 1. Source AppData directory on Windows
    appdata_base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    zugzwang_appdata = appdata_base / "ZUGZWANG"

    # 2. Workspace export directory
    workspace_dir = Path(__file__).resolve().parent.parent
    export_dir = workspace_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / "ZUGZWANG_MacBook_Data_Export.zip"

    # Remove existing zip if present
    if zip_path.exists():
        zip_path.unlink()

    print(f"[{zugzwang_appdata}] -> Exporting ZUGZWANG application data...")
    print(f"Target archive: {zip_path}")

    file_count = 0
    total_size = 0

    readme_content = """ZUGZWANG MACBOOK DATA RESTORE INSTRUCTIONS
==========================================

On Windows, ZUGZWANG stores application data in:
  %APPDATA%\\ZUGZWANG  (C:\\Users\\Moham\\AppData\\Roaming\\ZUGZWANG)

On macOS, ZUGZWANG stores application data in:
  ~/.config/ZUGZWANG  (/Users/<your-username>/.config/ZUGZWANG)

HOW TO RESTORE ON YOUR NEW MACBOOK:
1. Open Terminal on your MacBook.
2. Create the ZUGZWANG config directory:
     mkdir -p ~/.config/ZUGZWANG
3. Extract all files from this ZIP archive directly into ~/.config/ZUGZWANG/ :
     unzip ZUGZWANG_MacBook_Data_Export.zip -d ~/.config/ZUGZWANG/
4. Verify that ~/.config/ZUGZWANG/ contains settings.json, data/, and templates/.
5. When you run ZUGZWANG on your MacBook, all your settings, search history, saved jobs, email profiles, and outreach history will be restored automatically!
"""

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Add instructions readme at root of archive
        zf.writestr("README_MAC_RESTORE.txt", readme_content)
        file_count += 1

        if zugzwang_appdata.exists():
            for root, dirs, files in os.walk(zugzwang_appdata):
                # Exclude transient directories
                dirs[:] = [d for d in dirs if d not in ("temp", "logs", "screenshots", "__pycache__")]

                for file_name in files:
                    if file_name.endswith(".tmp") or file_name == "settings.backup.json.tmp":
                        continue

                    full_path = Path(root) / file_name
                    rel_path = full_path.relative_to(zugzwang_appdata)

                    zf.write(full_path, rel_path)
                    file_count += 1
                    total_size += full_path.stat().st_size

        # Include local repository export files if any (e.g. sent_emails.txt)
        local_sent_emails = export_dir / "sent_emails.txt"
        if local_sent_emails.exists():
            zf.write(local_sent_emails, "export/sent_emails.txt")
            file_count += 1
            total_size += local_sent_emails.stat().st_size

    size_mb = total_size / (1024 * 1024)
    print(f"Successfully exported {file_count} files ({size_mb:.2f} MB) to:\n  {zip_path}")
    return zip_path

if __name__ == "__main__":
    create_macbook_export()

# 1.1.0 Beta5
