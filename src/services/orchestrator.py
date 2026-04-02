"""
ZUGZWANG - Scraping Orchestrator
Manages the full lifecycle of scraping jobs:
thread isolation, asyncio event loop management,
pause/resume/cancel, and result streaming to the UI.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
import threading
from dataclasses import replace
from datetime import datetime
from typing import Optional

from .browser import BrowserSession
from .maps_scraper import GoogleMapsScraper
from .jobsuche_scraper import JobsucheScraper
from .ausbildung_scraper import AusbildungScraper
from .aubiplus_scraper import AubiPlusScraper
from .azubiyo_scraper import AzubiyoScraper
from .export_service import ExportService
from ..core.config import config_manager, get_data_dir, get_memory_db_path
from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, ScrapingJob, ScrapingStatus, SourceType, SearchConfig

logger = get_logger(__name__)


class ScrapingOrchestrator:
    """
    Coordinates scraping job execution in a dedicated background thread
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
        self._memory_lock = threading.Lock()
        self._known_record_ids: set[str] = set()

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
        if not self._known_record_ids:
            self.load_app_memory()

        job = ScrapingJob(config=config)
        self._current_job = job

        self._thread = threading.Thread(
            target=self._run_job_thread,
            args=(job,),
            daemon=True,
            name=f"scraper-{job.id[:8]}",
        )
        self._thread.start()
        logger.info(f"Started scraping job {job.id} ({config.source_type.value})")
        return job

    def pause_job(self) -> None:
        if self._scraper and self.is_running:
            self._scraper.pause()
            if self._current_job:
                self._current_job.status = ScrapingStatus.PAUSED
            event_bus.emit(event_bus.JOB_PAUSED, job_id=self._current_job.id if self._current_job else "")
            logger.info(f"Job paused: {self._current_job.id if self._current_job else ''}")

    def resume_job(self) -> None:
        if self._scraper and self._current_job and self._current_job.status == ScrapingStatus.PAUSED:
            self._scraper.resume()
            self._current_job.status = ScrapingStatus.RUNNING
            logger.info(f"Job resumed: {self._current_job.id}")

    def cancel_job(self) -> None:
        if self._scraper:
            self._scraper.cancel()
        if self._current_job:
            self._current_job.status = ScrapingStatus.CANCELLED
            event_bus.emit(event_bus.JOB_CANCELLED, job_id=self._current_job.id)
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
        return records

    def clear_app_memory(self) -> None:
        with self._memory_lock:
            self._known_record_ids.clear()

        memory_path = Path(get_memory_db_path())
        if memory_path.exists():
            memory_path.unlink()

        event_bus.emit(event_bus.DB_UPDATED, records=[])

    def persist_current_job(self) -> None:
        """Persist the current in-memory job snapshot to app memory."""
        if not self._current_job:
            return
        try:
            self._export.save_project(self._current_job, str(get_memory_db_path()))
            event_bus.emit(event_bus.DB_UPDATED, records=list(self._current_job.results))
        except Exception as e:
            logger.warning(f"Could not persist current job snapshot: {e}")

    def _run_job_thread(self, job: ScrapingJob) -> None:
        """Runs in a dedicated thread. Creates its own asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_job_async(job))
        except Exception as e:
            logger.error(f"Job thread crashed: {e}", exc_info=True)
            job.fail(str(e))
            event_bus.emit(event_bus.JOB_FAILED, job_id=job.id, error=str(e))
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _run_job_async(self, job: ScrapingJob) -> None:
        """Async job runner. Creates browser session and delegates to scraper."""
        settings = replace(
            config_manager.settings,
            default_headless=job.config.headless,
            default_delay_min=job.config.delay_min,
            default_delay_max=job.config.delay_max,
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

            # Stream results
            current_job_ids: set[str] = set()
            async for record in self._scraper.scrape():
                if job.status == ScrapingStatus.CANCELLED:
                    break
                record = record.normalize()
                record.id = record.stable_id()
                with self._memory_lock:
                    if record.id in self._known_record_ids or record.id in current_job_ids:
                        logger.info(
                            f"Job {job.id}: skipped duplicate record "
                            f"'{record.company_name or record.email}' (already captured in a previous run)"
                        )
                        event_bus.emit(
                            event_bus.JOB_LOG,
                            job_id=job.id,
                            message=f"⏭ Skipped (already captured): {record.company_name or record.email}",
                            level="INFO",
                        )
                        continue
                    current_job_ids.add(record.id)
                    self._known_record_ids.add(record.id)

                job.results.append(record)
                job._update_stats()
                job.total_errors = getattr(self._scraper, "_total_errors", 0)

                event_bus.emit(
                    event_bus.JOB_PROGRESS,
                    job_id=job.id,
                    total_found=job.total_found,
                    total_emails=job.total_emails,
                    total_websites=job.total_websites,
                    total_errors=job.total_errors,
                    completion=job.completion_rate,
                )

            job.total_errors = getattr(self._scraper, "_total_errors", job.total_errors)
            if job.status != ScrapingStatus.CANCELLED:
                job.complete()
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

                # Auto-save to SQLite
                try:
                    auto_save_path = str(get_data_dir() / self._export.generate_filename("job", "db"))
                    self._export.save_project(job, auto_save_path)
                    self._export.save_project(job, str(get_memory_db_path()))
                    logger.info(f"Auto-saved project to {auto_save_path}")
                except Exception as e:
                    logger.warning(f"Auto-save failed: {e}")

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}", exc_info=True)
            job.fail(str(e))
            event_bus.emit(event_bus.JOB_FAILED, job_id=job.id, error=str(e))
        finally:
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
