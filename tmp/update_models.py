
import os

path = r'c:\Users\Moham\Desktop\bewerbung\Zugzwang\src\core\models.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '    email_recipients: str = ""'
if target in content:
    new_content = content.replace(target, target + '\n    email_attachments: str = ""')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print("SUCCESS")
else:
    # Try with different line endings or spacing if generic failed
    print("TARGET NOT FOUND")
    # Show what's there
    idx = content.find('email_recipients')
    if idx != -1:
        print(f"DEBUG: Found at {idx}. Context: {repr(content[idx-10:idx+40])}")
