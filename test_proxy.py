import sys
from datetime import datetime
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

# Mock necessary path addition
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.models import LeadRecord, SourceType
from src.ui.results_page import LeadFilterProxy, ResultsTableModel

def test_filter():
    app = QApplication(sys.argv)
    
    model = ResultsTableModel()
    proxy = LeadFilterProxy()
    proxy.setSourceModel(model)
    
    # Create test records
    r1 = LeadRecord(company_name="Aubi Company", source_type=SourceType.AUBIPLUS_DE, scraped_at=datetime.utcnow().isoformat())
    r2 = LeadRecord(company_name="Google Company", source_type=SourceType.GOOGLE_MAPS, scraped_at=datetime.utcnow().isoformat())
    
    model.add_record(r1)
    model.add_record(r2)
    
    print(f"Total records in model before filter: {model.rowCount()}")
    print(f"Total records in proxy before filter: {proxy.rowCount()}")
    
    # Apply source filter for Aubi-Plus (index = 4)
    print("Applying filter source=4 (Aubi-Plus)")
    try:
        proxy.set_source_filter(4)
        print(f"Total records in proxy after filter: {proxy.rowCount()}")
        for i in range(proxy.rowCount()):
            src_row = proxy.mapToSource(proxy.index(i, 0)).row()
            print(f"Visible row {i} -> Company: {model.get_record(src_row).company_name}")
    except Exception as e:
        print(f"Error during filter: {e}")

if __name__ == "__main__":
    test_filter()
