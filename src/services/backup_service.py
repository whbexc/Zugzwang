import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, QTimer

from ..core.config import config_manager, get_memory_db_path, get_app_data_dir

logger = logging.getLogger(__name__)

class BackupService(QObject):
    """Handles automatic periodic backups of the app memory database and settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._perform_backup)
        # 24 hours interval (86400000 ms)
        self._timer.setInterval(24 * 60 * 60 * 1000)
        
        # We will also trigger an initial backup 5 seconds after startup
        # to ensure we get a clean backup per session.
        QTimer.singleShot(5000, self._perform_backup)
        self._timer.start()
        
    def _perform_backup(self):
        settings = config_manager.settings
        
        if not getattr(settings, "auto_backup", True):
            logger.debug("Automatic backup is disabled in settings. Skipping.")
            return
            
        backup_dir = getattr(settings, "backup_dir", "")
        if not backup_dir:
            backup_dir = get_app_data_dir() / "backups"
        else:
            backup_dir = Path(backup_dir)
            
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            
            # Backup DB
            db_path = get_memory_db_path()
            if db_path.exists():
                db_backup_path = backup_dir / f"zugzwang_backup_{timestamp}.db"
                shutil.copy2(db_path, db_backup_path)
                logger.info(f"Backed up database to {db_backup_path}")
                
            # Backup Settings
            settings_path = get_app_data_dir() / "settings.json"
            if settings_path.exists():
                settings_backup_path = backup_dir / f"settings_backup_{timestamp}.json"
                shutil.copy2(settings_path, settings_backup_path)
                logger.info(f"Backed up settings to {settings_backup_path}")
                
            self._prune_old_backups(backup_dir)
            
        except Exception as e:
            logger.error(f"Failed to perform automatic backup: {e}", exc_info=True)
            
    def _prune_old_backups(self, backup_dir: Path):
        """Keep only the 7 most recent backup pairs."""
        try:
            # Gather all backups, sorting by modification time (oldest first)
            db_backups = sorted(backup_dir.glob("zugzwang_backup_*.db"), key=os.path.getmtime)
            settings_backups = sorted(backup_dir.glob("settings_backup_*.json"), key=os.path.getmtime)
            
            # Prune DBs
            if len(db_backups) > 7:
                for old_db in db_backups[:-7]:
                    old_db.unlink(missing_ok=True)
                    logger.debug(f"Pruned old backup: {old_db.name}")
                    
            # Prune Settings
            if len(settings_backups) > 7:
                for old_set in settings_backups[:-7]:
                    old_set.unlink(missing_ok=True)
                    logger.debug(f"Pruned old backup: {old_set.name}")
                    
        except Exception as e:
            logger.error(f"Failed to prune old backups: {e}")
