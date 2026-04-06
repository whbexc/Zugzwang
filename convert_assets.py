"""
Convert PNG installer art to correctly-sized BMPs for NSIS MUI2.

NSIS MUI2 requirements:
  wizard.bmp  — 164 x 314 pixels, 24-bit BMP
  header.bmp  — 150 x 57 pixels, 24-bit BMP
"""

from PIL import Image
import os

# Paths to generated PNGs
WIZARD_SRC  = r"C:\Users\Moham\.gemini\antigravity\brain\c1c39335-00ad-4787-a1ba-17e2c892c637\zugzwang_wizard_v106_1775435204298.png"
HEADER_SRC  = r"C:\Users\Moham\.gemini\antigravity\brain\c1c39335-00ad-4787-a1ba-17e2c892c637\zugzwang_header_v106_1775435217403.png"

# Destination paths in the workspace
WIZARD_DEST = r"c:\Users\Moham\Desktop\bewerbung\Zugzwang\assets\wizard.bmp"
HEADER_DEST = r"c:\Users\Moham\Desktop\bewerbung\Zugzwang\assets\header.bmp"

WIZARD_SIZE = (164, 314)
HEADER_SIZE = (150, 57)

def convert(src, dest, size):
    if not os.path.exists(src):
        print(f"Error: {src} not found.")
        return
    img = Image.open(src).convert("RGB")   # drop alpha, NSIS needs 24-bit
    img = img.resize(size, Image.LANCZOS)
    img.save(dest, format="BMP")
    print(f"Saved {dest} ({size[0]}x{size[1]})")

if __name__ == "__main__":
    convert(WIZARD_SRC, WIZARD_DEST, WIZARD_SIZE)
    convert(HEADER_SRC, HEADER_DEST, HEADER_SIZE)
    print("Optimization Complete.")
