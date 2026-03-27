"""
ZUGZWANG - License Key Generator Utility
Use this script to generate license keys for your customers.
"""

import sys
import os

# Add src to path so we can import our security logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.core.security import LicenseManager

def main():
    print("="*40)
    print(" ZUGZWANG - License Generator ")
    print("="*40)
    
    machine_id = input("\nEnter the Customer's MACHINE ID: ").strip().upper()
    
    if len(machine_id) != 16:
        print("\nERROR: Machine ID must be exactly 16 characters.")
        return

    license_key = LicenseManager.generate_license_key(machine_id)
    
    print("\n" + "-"*40)
    print(f" GENERATED LICENSE KEY: {license_key}")
    print("-"*40)
    print("\nSend this key to the customer to activate their application.")
    print("="*40)

if __name__ == "__main__":
    main()
mode:AGENT_MODE_EXECUTION
