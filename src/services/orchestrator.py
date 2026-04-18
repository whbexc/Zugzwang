"""
ZUGZWANG - Scraping Orchestrator
Manages the full lifecycle of scraping jobs:
thread isolation, asyncio event loop management,
pause/resume/cancel, and result streaming to the UI.
"""

import asyncio
from pathlib import Path
import threading
import time
from dataclasses import replace
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QThread

from .browser import BrowserSession
from .maps_scraper import GoogleMapsScraper
from .jobsuche_scraper import JobsucheScraper
from .ausbildung_scraper import AusbildungScraper
from .aubiplus_scraper import AubiPlusScraper
from .azubiyo_scraper import AzubiyoScraper
from .export_service import ExportService
from .import_service import ImportService
from ..core.config import config_manager, get_data_dir, get_memory_db_path
from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, ScrapingJob, ScrapingStatus, SourceType, SearchConfig

logger = get_logger(__name__)


class ScrapingWorker(QObject):
    """
    Worker object that encapsulates the Playwright asyncio loop.
    Moves the execution into a PySide6 QThread to ensure UI responsiveness
    while avoiding GIL collisions caused by raw Python threads.
    """
    def __init__(self, orchestrator_ref, job: ScrapingJob):
        super().__init__()
        self.orchestrator = orchestrator_ref
        self.job = job

    def run(self):
        """Runs in a dedicated QThread. Creates its own asyncio event loop."""
        # Lower thread priority so the Qt main event loop is never starved
        # when Playwright drives the browser at full CPU.
        from PySide6.QtCore import QThread
        QThread.currentThread().setPriority(QThread.Priority.LowPriority)

        self.orchestrator._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.orchestrator._loop)

        # Load app memory in the background thread if not already loaded
        if not self.orchestrator._known_record_ids:
            try:
                self.orchestrator.load_app_memory()
            except Exception as e:
                logger.warning(f"Background app memory load failed: {e}")

        try:
            self.orchestrator._loop.run_until_complete(self.orchestrator._run_job_async(self.job))
        except Exception as e:
            logger.error(f"Job thread crashed: {e}", exc_info=True)
            self.job.fail(str(e))
            event_bus.emit(event_bus.JOB_FAILED, job_id=self.job.id, error=str(e))
        finally:
            try:
                self.orchestrator._loop.close()
            except Exception:
                pass
            # Trigger clean QThread exit
            if hasattr(self.orchestrator, '_thread') and self.orchestrator._thread:
                self.orchestrator._thread.quit()

class ScrapingOrchestrator:
    """
    Coordinates scraping job execution in a dedicated background QThread
    with an asyncio event loop. Provides thread-safe control (pause/resume/cancel).
    One instance per application session.
    """

    def __init__(self):
        self._current_job: Optional[ScrapingJob] = None
        self._scraper: Optional[GoogleMapsScraper | JobsucheScraper] = None
        self._session: Optional[BrowserSession] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._export = ExportService()
        self._import = ImportService()
        self._memory_lock = threading.Lock()
        self._known_record_ids: set[str] = set()
        # O(1) id-keyed dict; preserves insertion order (Python 3.7+)
        self._app_memory_records: dict[str, LeadRecord] = {}
        self._last_progress_emit_ts: float = 0.0
        self._last_db_save_ts: float = 0.0
        self._persistence_lock = threading.Lock()
        self._is_persisting = False
        self._library_verify_count: int = 0
        
        # Load existing history from disk in a background thread so the main
        # thread (and the UI it's about to render) is never stalled.
        # ScrapingWorker.run() already re-checks _known_record_ids before each
        # job, so there is no race: the worker will wait on its own load if
        # this one hasn't finished yet.
        def _bg_load_memory():
            try:
                records = self.load_app_memory()
                event_bus.emit(event_bus.DB_UPDATED, records=records)
            except Exception as e:
                logger.warning(f"Initial app memory load failed: {e}")

        threading.Thread(
            target=_bg_load_memory,
            daemon=True,
            name="startup-memory-load",
        ).start()

    @property
    def is_running(self) -> bool:
        return (
            self._current_job is not None
            and self._current_job.status == ScrapingStatus.RUNNING
        )

    @property
    def current_job(self) -> Optional[ScrapingJob]:
        return self._current_job

    def start_job(self, config: SearchConfig) -> ScrapingJob:
        """
        Start a new scraping job. Raises if a job is already running.
        Returns the ScrapingJob instance immediately (results streamed via events).
        """
        if self.is_running:
            raise RuntimeError("A scraping job is already running. Stop it first.")

        job = ScrapingJob(config=config)
        self._current_job = job

        self._thread = QThread()
        self._worker = ScrapingWorker(self, job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        
        self._thread.start()
        logger.info(f"Started scraping job {job.id} ({config.source_type.value})")
        return job

    def pause_job(self) -> None:
        if self._scraper and self.is_running:
            self._scraper.pause()
            if self._current_job:
                self._current_job.status = ScrapingStatus.PAUSED
            event_bus.emit(event_bus.JOB_PAUSED, job_id=self._current_job.id if self._current_job else "")
            self.persist_current_job()
            logger.info(f"Job paused: {self._current_job.id if self._current_job else ''}")

    def resume_job(self) -> None:
        if self._scraper and self._current_job and self._current_job.status == ScrapingStatus.PAUSED:
            self._scraper.resume()
            self._current_job.status = ScrapingStatus.RUNNING
            event_bus.emit(event_bus.JOB_RESUMED, job_id=self._current_job.id)
            logger.info(f"Job resumed: {self._current_job.id}")

    def cancel_job(self) -> None:
        if self._scraper:
            self._scraper.cancel()
        if self._current_job:
            self._current_job.status = ScrapingStatus.CANCELLED
            event_bus.emit(event_bus.JOB_CANCELLED, job_id=self._current_job.id)
            self.persist_current_job()
            logger.info(f"Job cancelled: {self._current_job.id}")

    def export_results(
        self,
        records: list,
        format: str,
        path: str,
    ) -> None:
        """Export results in a background thread to keep UI responsive."""
        def _do_export():
            try:
                event_bus.emit(event_bus.EXPORT_STARTED, format=format, path=path)
                if format in ("xlsx", "excel"):
                    self._export.export_excel(records, path)
                elif format == "docx":
                    self._export.export_docx(records, path)
                elif format == "sqlite":
                    self._export.save_project(self._build_export_job(records), path)
                    event_bus.emit(
                        event_bus.EXPORT_COMPLETED,
                        format="sqlite",
                        path=path,
                        count=len(records),
                    )
                elif format == "txt":
                    self._export.export_txt(records, path)
                else:
                    raise ValueError(f"Unsupported export format: {format}")
                logger.info(f"Export complete: {format} -> {path}")
            except Exception as e:
                event_bus.emit(event_bus.EXPORT_FAILED, format=format, error=str(e))
                logger.error(f"Export failed ({format}): {e}")

        t = threading.Thread(target=_do_export, daemon=True, name="export-worker")
        t.start()

    def remove_leads(self, lead_ids: list[str]) -> None:
        """Remove leads from the global memory and persist the change."""
        if not lead_ids:
            return
        
        with self._memory_lock:
            initial_count = len(self._app_memory_records)
            # O(1) per id — dict.pop is constant time
            for lid in lead_ids:
                self._app_memory_records.pop(lid, None)
                self._known_record_ids.discard(lid)
            removed_count = initial_count - len(self._app_memory_records)

        if removed_count > 0:
            # Persist to disk
            self.persist_current_job()
            logger.info(f"Removed {removed_count} leads from global memory.")

    def mark_as_contacted(self, emails: list[str]) -> None:
        """Mark leads with matching emails as contacted and persist the change. 
        Creates manual stub records for unseen emails."""
        if not emails:
            return
            
        email_set = {e.strip().lower() for e in emails}
        from datetime import datetime as _dt
        from ..core.models import LeadRecord, SourceType
        now = _dt.utcnow().isoformat()
        updated = 0
        
        with self._memory_lock:
            # Build a reverse email→record map for O(1) lookup
            email_to_record: dict[str, LeadRecord] = {
                r.email.strip().lower(): r
                for r in self._app_memory_records.values()
                if r.email
            }
            found_emails: set[str] = set()
            for target_email in email_set:
                r = email_to_record.get(target_email)
                if r:
                    found_emails.add(target_email)
                    r.is_contacted = True
                    if not r.contacted_at:
                        r.contacted_at = now
                    updated += 1

            # For any emails not in memory (e.g. pasted from clipboard),
            # create a stub 'manual' lead to track the send persistently.
            missing = email_set - found_emails
            for m_email in missing:
                stub = LeadRecord(
                    source_type=SourceType.MANUAL,
                    email=m_email,
                    is_contacted=True,
                    contacted_at=now,
                    notes="Auto-generated stub from manual broadcast"
                )
                stub.id = stub.stable_id()
                if stub.id not in self._known_record_ids:
                    self._known_record_ids.add(stub.id)
                    self._app_memory_records[stub.id] = stub
                    updated += 1

        if updated > 0:
            self.persist_current_job()
            logger.info(f"Marked {updated} lead(s) as contacted (including stubs for manual emails).")

    def is_already_contacted(self, email: str) -> bool:
        """Check if an email has already been contacted according to app memory."""
        if not email:
            return False
        email_lower = email.strip().lower()
        with self._memory_lock:
            # O(N) list scan replaced with O(N) dict-values scan; still linear but
            # avoids holding the lock across a worst-case O(N) random-access list.
            # A secondary email→id index would make this O(1); add if needed.
            for r in self._app_memory_records.values():
                if r.email and r.email.strip().lower() == email_lower:
                    return bool(r.is_contacted)
        return False

    def import_leads(self, file_path: Optional[str] = None, text: Optional[str] = None) -> None:
        """Import leads from a file or raw text in a background thread."""
        def _do_import():
            try:
                if file_path:
                    event_bus.emit(event_bus.EXPORT_STARTED, format="import", path=file_path)
                    records = self._import.import_from_file(file_path)
                    source_name = Path(file_path).name
                elif text:
                    records = self._import.import_from_text(text)
                    source_name = "Clipboard"
                else:
                    return

                new_count = 0
                with self._memory_lock:
                    for record in records:
                        record.id = record.stable_id()
                        if record.id not in self._known_record_ids:
                            self._known_record_ids.add(record.id)
                            self._app_memory_records[record.id] = record
                            new_count += 1
                
                if new_count > 0:
                    self.persist_current_job()
                
                event_bus.emit(
                    event_bus.EXPORT_COMPLETED,
                    format="import",
                    path=source_name,
                    count=new_count,
                )
                logger.info(f"Import complete: {new_count} new leads from {source_name}")
            except Exception as e:
                logger.error(f"Import failed: {e}")
                event_bus.emit(event_bus.EXPORT_FAILED, format="import", error=str(e))

        t = threading.Thread(target=_do_import, daemon=True, name="import-worker")
        t.start()

    def load_app_memory(self) -> list[LeadRecord]:
        memory_path = get_memory_db_path()
        if not memory_path.exists():
            return []
        try:
            _, records = self._export.load_project(str(memory_path))
        except Exception as e:
            logger.warning(f"Could not load app memory: {e}")
            return []

        with self._memory_lock:
            self._known_record_ids = {record.id for record in records}
            # Rebuild O(1) dict; later records win if there are id collisions
            self._app_memory_records = {record.id: record for record in records}
        return records

    def clear_app_memory(self) -> None:
        with self._memory_lock:
            self._known_record_ids.clear()
            self._app_memory_records.clear()

        memory_path = Path(get_memory_db_path())
        if memory_path.exists():
            memory_path.unlink()

        event_bus.emit(event_bus.DB_UPDATED, records=[])

    def get_app_memory_records(self) -> list[LeadRecord]:
        """Return a thread-safe snapshot of all historical records."""
        with self._memory_lock:
            return list(self._app_memory_records.values())

    def persist_current_job(self) -> None:
        """Persist the cumulative in-memory application records over time."""
        from ..core.models import ScrapingJob, ScrapingStatus
        
        with self._memory_lock:
            all_records = list(self._app_memory_records.values())
            config = self._current_job.config if self._current_job else SearchConfig()

        def _do_persist():
            try:
                dummy_job = ScrapingJob(config=config, results=all_records, status=ScrapingStatus.COMPLETED)
                self._export.save_project(dummy_job, str(get_memory_db_path()))
                event_bus.emit(event_bus.DB_UPDATED, records=all_records)
            except Exception as e:
                logger.warning(f"Background persistence failed: {e}")
            finally:
                with self._persistence_lock:
                    self._is_persisting = False

        # Ensure only one persistence thread runs at a time to prevent SQLite locks
        with self._persistence_lock:
            if self._is_persisting:
                logger.debug("Persistence already in progress, skipping batch.")
                return
            self._is_persisting = True
            
        threading.Thread(target=_do_persist, daemon=True, name="persist-worker").start()

    async def _run_job_async(self, job: ScrapingJob) -> None:
        """Async job runner. Creates browser session and delegates to scraper."""
        settings = replace(
            config_manager.settings,
            default_headless=job.config.headless,
            default_delay_min=job.config.delay_min,
            default_delay_max=job.config.delay_max,
            browser_engine=job.config.browser_engine or config_manager.settings.browser_engine
        )

        self._session = BrowserSession(settings, job_id=job.id, source_type=job.config.source_type)
        try:
            await self._session.start()
            job.start()
            event_bus.emit(event_bus.JOB_STARTED, job_id=job.id, config=job.config)

            # Instantiate the correct scraper
            if job.config.source_type == SourceType.GOOGLE_MAPS:
                self._scraper = GoogleMapsScraper(self._session, job.config, job.id)
            elif job.config.source_type == SourceType.JOBSUCHE:
                self._scraper = JobsucheScraper(self._session, job.config, job.id)
            elif job.config.source_type == SourceType.AUSBILDUNG_DE:
                self._scraper = AusbildungScraper(self._session, job.config, job.id)
            elif job.config.source_type == SourceType.AUBIPLUS_DE:
                self._scraper = AubiPlusScraper(self._session, job.config, job.id)
            elif job.config.source_type == SourceType.AZUBIYO:
                self._scraper = AzubiyoScraper(self._session, job.config, job.id)
            else:
                raise ValueError(f"Unsupported source type: {job.config.source_type}")

            # Stream results in batches to prevent UI signal flooding
            current_job_ids: set[str] = set()
            result_batch: list[LeadRecord] = []
            last_batch_emit: float = time.monotonic()

            async for record in self._scraper.scrape():
                if job.status == ScrapingStatus.CANCELLED:
                    break
                record = record.normalize()
                record.id = record.stable_id()
                record.job_id = job.id
                with self._memory_lock:
                    if record.id in current_job_ids:
                        existing = self._app_memory_records.get(record.id)
                        if existing:
                            record.email = record.email or existing.email
                            record.phone = record.phone or existing.phone
                            record.website = record.website or existing.website
                            record.address = record.address or existing.address
                            record.contact_person = record.contact_person or existing.contact_person
                            record.linkedin = record.linkedin or existing.linkedin
                            record.twitter = record.twitter or existing.twitter
                            record.instagram = record.instagram or existing.instagram
                            record.is_duplicate = existing.is_duplicate
                        self._app_memory_records[record.id] = record
                        for idx, existing_job_record in enumerate(job.results):
                            if existing_job_record.id == record.id:
                                job.results[idx] = record
                                break
                        job._update_stats()
                        continue
                    
                    is_new_globally = record.id not in self._known_record_ids
                    if is_new_globally:
                        self._known_record_ids.add(record.id)
                        # O(1) dict insert — no list append/scan needed
                        self._app_memory_records[record.id] = record
                    else:
                        logger.debug(f"Job {job.id}: Lead {record.id} already exists in global library.")
                        # O(1) dict lookup — replaces next(r for r in list if r.id == id)
                        existing = self._app_memory_records.get(record.id)
                        if existing:
                            # Prefer existing contact info if incoming is missing
                            record.email = record.email or existing.email
                            record.phone = record.phone or existing.phone
                            record.website = record.website or existing.website
                            record.address = record.address or existing.address
                            record.contact_person = record.contact_person or existing.contact_person
                            record.linkedin = record.linkedin or existing.linkedin
                            record.twitter = record.twitter or existing.twitter
                            record.instagram = record.instagram or existing.instagram

                        # Mark as duplicate and update in-place — O(1), no list scan or insert(0)
                        record.is_duplicate = True
                        record.scraped_at = datetime.utcnow().isoformat()
                        self._app_memory_records[record.id] = record

                        self._library_verify_count += 1
                    
                    # Store result in this job and update dashboard stats
                    job.results.append(record)
                    current_job_ids.add(record.id)
                    job._update_stats()

                # Add to batch and emit periodically
                result_batch.append(record)
                now = time.monotonic()
                if len(result_batch) >= 10 or (now - last_batch_emit >= 1.0):
                    for r in result_batch:
                        event_bus.emit(event_bus.JOB_RESULT, job_id=job.id, record=r)
                    result_batch.clear()
                    
                    # Throttled Progress update (emit on batch or min 1s)
                    if (now - self._last_progress_emit_ts >= 1.0):
                        self._last_progress_emit_ts = now
                        event_bus.emit(
                            event_bus.JOB_PROGRESS,
                            job_id=job.id,
                            total_found=job.total_found,
                            total_emails=job.total_emails,
                            total_websites=job.total_websites,
                            total_errors=job.total_errors,
                            completion=job.completion_rate,
                        )
                    last_batch_emit = now

            # All results and progress emitted via batch logic above.
            job.total_errors = getattr(self._scraper, "_total_errors", job.total_errors)

            if job.status != ScrapingStatus.CANCELLED:
                if self._library_verify_count:
                    event_bus.emit(
                        event_bus.JOB_LOG,
                        job_id=job.id,
                        message=f"Verified {self._library_verify_count} lead(s) from Library during this run.",
                        level="INFO",
                    )
                job.complete()
                event_bus.emit(
                    event_bus.JOB_PROGRESS,
                    job_id=job.id,
                    total_found=job.total_found,
                    total_emails=job.total_emails,
                    total_websites=job.total_websites,
                    total_errors=job.total_errors,
                    completion=job.completion_rate,
                )
                event_bus.emit(
                    event_bus.JOB_COMPLETED,
                    job_id=job.id,
                    total_found=job.total_found,
                    total_emails=job.total_emails,
                    total_websites=job.total_websites,
                )
                logger.info(
                    f"Job {job.id} completed: {job.total_found} results, "
                    f"{job.total_emails} emails, {job.total_websites} websites"
                )

                # (Self-cleaning redundant block)

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}", exc_info=True)
            job.fail(str(e))
            event_bus.emit(event_bus.JOB_FAILED, job_id=job.id, error=str(e))
        finally:
            self._last_progress_emit_ts = 0.0
            self._last_progress_found = -1
            self._library_verify_count = 0
            await self._cleanup_job()

    async def _cleanup_job(self) -> None:
        """Centralized cleanup to ensure no browser processes hang."""
        if self._session:
            try:
                await self._session.stop()
            except Exception as e:
                logger.warning(f"Error during session cleanup: {e}")
            self._session = None
        self._scraper = None
        logger.info("Scraping job cleanup finalized.")

    def _build_export_job(self, records: list) -> ScrapingJob:
        """Create a project snapshot from the records currently being exported."""
        base_job = self._current_job
        now = datetime.utcnow().isoformat()
        export_job = ScrapingJob(
            config=base_job.config if base_job else SearchConfig(),
            status=base_job.status if base_job else ScrapingStatus.COMPLETED,
            results=list(records),
        )

        if base_job:
            export_job.id = base_job.id
            export_job.created_at = base_job.created_at
            export_job.started_at = base_job.started_at
            export_job.completed_at = base_job.completed_at
            export_job.error_message = base_job.error_message
            export_job.log_entries = list(base_job.log_entries)
            export_job.total_errors = base_job.total_errors
        else:
            export_job.started_at = now
            export_job.completed_at = now

        if export_job.status == ScrapingStatus.PENDING:
            export_job.status = ScrapingStatus.COMPLETED
        if export_job.completed_at is None:
            export_job.completed_at = now

        export_job._update_stats()
        return export_job


# Global orchestrator instance
orchestrator = ScrapingOrchestrator()
