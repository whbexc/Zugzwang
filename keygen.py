from src.core.security import LicenseManager

machine_id = LicenseManager.get_machine_id()
key = LicenseManager.generate_license_key(machine_id)
adm_key = LicenseManager.generate_admin_override_key(machine_id)

print(f"Machine ID: {machine_id}")
print(f"PRO License Key: {key}")
print(f"Admin Key: {adm_key}")
