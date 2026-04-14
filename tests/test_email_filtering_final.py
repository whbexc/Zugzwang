# Mock EmailSource and other dependencies if needed, or just import after path setup
import sys
import os

# Add the project root to sys.path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root not in sys.path:
    sys.path.insert(0, root)

# Now we can import from src
try:
    from src.services.email_extractor import _is_valid_email, extract_emails_from_html
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback: manually define the logic if import fails due to complex dependencies
    print("Falling back to manual logic verification...")
    # (I'll skip manual definition for now and try to make the import work)

def test_email_filtering():
    test_cases = [
        # Placeholders
        ("johndoe@example.com", False),
        ("max.mustermann@gmail.com", False),
        ("mustermann@company.de", False),
        ("test@test.com", False),
        ("info@example.com", False),
        
        # Portals
        ("info@ausbildung.de", False),
        ("kontakt@arbeitsagentur.de", False),
        ("recruiting@stepstone.de", False),
        ("support@indeed.com", False),
        
        # Valid ones
        ("jobs@real-company.de", True),
        ("bewerbung@medical-center.com", True),
        ("hr@startup.io", True),
        ("kontakt@handwerker-mueller.de", True),
        ("info@kmu-beratung.de", True),
    ]
    
    print("Testing Email Filtering Logic...")
    passed = 0
    for email, expected in test_cases:
        result = _is_valid_email(email)
        status = "PASSED" if result == expected else "FAILED"
        print(f"Email: {email:<35} -> Result: {result:<5} (Expected: {expected:<5}) [{status}]")
        if result == expected:
            passed += 1
            
    print(f"\nPassed {passed}/{len(test_cases)} cases.")
    assert passed == len(test_cases)

def test_html_extraction_filtering():
    html = """
    <div>
        <p>Contact us at <a href="mailto:max.mustermann@example.com">max.mustermann@example.com</a></p>
        <p>Or portal at <a href="mailto:info@ausbildung.de">info@ausbildung.de</a></p>
        <p>Actual HR: <a href="mailto:jobs@real-employer.de">jobs@real-employer.de</a></p>
    </div>
    """
    print("\nTesting HTML Extraction Filtering...")
    emails = extract_emails_from_html(html)
    print(f"Extracted: {emails}")
    assert "jobs@real-employer.de" in emails
    assert "max.mustermann@example.com" not in emails
    assert "info@ausbildung.de" not in emails
    print("HTML Extraction Filtering: PASSED")

if __name__ == "__main__":
    try:
        test_email_filtering()
        test_html_extraction_filtering()
        print("\nAll Email Filtering Tests: PASSED")
    except Exception as e:
        print(f"\nTests FAILED: {e}")
        sys.exit(1)
