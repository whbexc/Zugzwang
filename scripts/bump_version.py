import sys
import re
import os
from datetime import datetime

# Files where version needs to be bumped
FILES_TO_BUMP = [
    "version_info.txt",
    "src/core/models.py",
    "src/core/config.py",
    "installer.nsi",
    "src/changelog.py"
]

def get_current_version(root_dir):
    changelog_path = os.path.join(root_dir, "src", "changelog.py")
    with open(changelog_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Could not find APP_VERSION in changelog.py")
    return match.group(1)

def update_version_in_files(root_dir, old_version, new_version):
    for rel_path in FILES_TO_BUMP:
        path = os.path.join(root_dir, rel_path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace occurrences of old_version
        if "changelog.py" in rel_path:
            # ONLY replace APP_VERSION to preserve history
            new_content = re.sub(
                f'^APP_VERSION\\s*=\\s*"{old_version}"',
                f'APP_VERSION = "{new_version}"',
                content,
                flags=re.MULTILINE
            )
        else:
            new_content = content.replace(old_version, new_version)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Bumped version in {rel_path}")

def format_date_en():
    return datetime.now().strftime("%B %d, %Y")

def format_date_ar():
    months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    now = datetime.now()
    return f"{now.day} {months[now.month-1]} {now.year}"

def inject_changelog(root_dir, new_version, changes_en, changes_ar):
    path = os.path.join(root_dir, "src", "changelog.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Determine if we need to remove old "LATEST" labels
    if f'"version": "{new_version}"' in content:
        print("Version already in changelog. Skipping injection.")
        return

    # Step 1: Remove "LATEST" labels from the previous version
    content = content.replace('"label": "LATEST",', '"label": None,')
    content = content.replace('"label": "الأحدث",', '"label": None,')
    content = content.replace('"label_color": "#30D158",', '"label_color": None,')

    # Step 2: Ensure we use 4 spaces for indentation when injecting
    def format_changes(changes):
        lines = []
        for c in changes:
            lines.append('            {')
            lines.append(f'                "type": "{c["type"]}",')
            lines.append(f'                "text": "{c["text"]}"')
            lines.append('            },')
        return "\n".join(lines)

    date_en = format_date_en()
    date_ar = format_date_ar()

    en_block = f"""    {{
        "version": "{new_version}",
        "date": "{date_en}",
        "label": "LATEST",
        "label_color": "#30D158",
        "changes": [
{format_changes(changes_en)}
        ]
    }},"""

    ar_block = f"""    {{
        "version": "{new_version}",
        "date": "{date_ar}",
        "label": "الأحدث",
        "label_color": "#30D158",
        "type_labels": {{
            "new": "جديد",
            "improved": "مُحسَّن",
            "fixed": "مُصلَّح",
            "removed": "مُزال"
        }},
        "changes": [
{format_changes(changes_ar)}
        ]
    }},"""

    # Inject EN
    content = content.replace("CHANGELOG = [\n", f"CHANGELOG = [\n{en_block}\n")
    # Inject AR
    content = content.replace("CHANGELOG_AR = [\n", f"CHANGELOG_AR = [\n{ar_block}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Injected new changelog entries")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py <new_version>")
        sys.exit(1)
        
    new_version = sys.argv[1]
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    old_version = get_current_version(root_dir)
    print(f"Bumping version from {old_version} to {new_version}...")
    
    update_version_in_files(root_dir, old_version, new_version)
    
    # 1.0.9 Specific Changes (Can be parameterized for future versions later)
    changes_en = [
        {"type": "improved", "text": "Ausbildung.de Pagination — native infinite scroll support for limitless lead extraction"},
        {"type": "fixed", "text": "Progress Indicators — resolved an update queue glitch where complete runs appeared stuck at 10%"},
        {"type": "fixed", "text": "Radius Accuracy — search URLs now perfectly match their configured catchment area"}
    ]
    changes_ar = [
        {"type": "improved", "text": "تصفح صفحات Ausbildung.de — دعم التمرير اللانهائي لاستخراج عدد غير محدود من العملاء"},
        {"type": "fixed", "text": "مؤشرات التقدم — حل خلل في طابور التحديث كان يجعل المهام المكتملة تظهر عالقة عند 10%"},
        {"type": "fixed", "text": "دقة نطاق البحث — روابط البحث تتطابق الآن تماماً مع النطاق الجغرافي المحدد"}
    ]
    
    inject_changelog(root_dir, new_version, changes_en, changes_ar)
    print("Done!")
