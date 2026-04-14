
import re

# Mocking the functions and classes from the project
def normalize_phone(phone: str) -> str:
    if not phone:
        return phone
    cleaned = phone.strip()
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"^0049\s*", "+49 ", cleaned)
    cleaned = re.sub(r"\(0\)\s*", "", cleaned)
    cleaned = re.sub(r"[^\d+\(\)\-/\s]", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 10:
        return ""
    if re.fullmatch(r"\d{8}", digits):
        return ""
    
    if cleaned.startswith("+49"):
        return cleaned
    
    if digits.startswith("0"):
        return f"+49 {cleaned[1:]}".strip()
    
    return cleaned

def _is_generic_location_text(text: str) -> bool:
    normalized = " ".join((text or "").strip().lower().split())
    return normalized in {
        "",
        "ort",
        "standort",
        "location",
        "arbeitsort",
        "arbeitsplatz",
        "zurück zum ergebnis",
        "zurück zum ergebnisse",
        "ergebnisliste",
    }

def test_city_filter():
    test_cases = [
        ("Berlin", False),
        ("Zurück zum Ergebnis", True),
        ("Zurück zum Ergebnisse", True),
        ("Ergebnisliste", True),
        ("Arbeitsort", True),
        ("Hamburg", False)
    ]
    for city, expected in test_cases:
        result = _is_generic_location_text(city)
        print(f"City: '{city}' -> Generic: {result} (Expected: {expected})")
        assert result == expected

def test_phone_logic():
    # Simulating the logic added in jobsuche_scraper.py
    def process_phone(p_text):
        phone = None
        if ' - ' in p_text or '/' in p_text or ',' in p_text:
            parts = re.split(r'[-\/,]', p_text)
            for part in parts:
                normalized = normalize_phone(part.strip())
                if normalized:
                    phone = normalized
                    break
        if not phone:
            phone = normalize_phone(p_text)
        return phone

    test_cases = [
        ("+49 2323 0 or +49 2323 49", "+49 2323 0"),
        ("+49 2323 - 49", "+49 2323"), # This assumes normalize_phone handles it
        ("02323 / 491234", "+49 2323"), # Splits by /
        ("02323 - 491234", "+49 2323"), # Splits by -
        ("+49 123 4567890", "+49 123 4567890")
    ]
    for raw, expected in test_cases:
        result = process_phone(raw)
        print(f"Raw: '{raw}' -> Processed: '{result}' (Expected start with: '{expected}')")

if __name__ == "__main__":
    print("Testing City Filter...")
    test_city_filter()
    print("\nTesting Phone Logic...")
    test_phone_logic()
