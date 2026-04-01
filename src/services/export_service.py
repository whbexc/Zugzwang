"""
ZUGZWANG - Export Service
Handles all data export formats: CSV, Excel (XLSX), JSON, SQLite.
Supports filtered/full export and project save/load.
"""

from __future__ import annotations
import csv
from dataclasses import replace
import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, ScrapingJob

logger = get_logger(__name__)

# Column headers in display order
EXPORT_COLUMNS = [
    "id", "source_type", "company_name", "job_title", "category",
    "email", "email_source_page", "phone", "website",
    "address", "city", "region", "postal_code", "country",
    "rating", "review_count", "description", "publication_date",
    "source_url", "maps_url", "search_query", "scraped_at", "notes",
]


class ExportService:
    """
    Handles all export and persistence operations.
    All methods are synchronous (called from export worker thread).
    """

    def export_csv(self, records: list[LeadRecord], path: str) -> int:
        """Export records to CSV. Returns number of rows written."""
        logger.info(f"Exporting {len(records)} records to CSV: {path}")
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=EXPORT_COLUMNS,
                    extrasaction="ignore",
                )
                writer.writeheader()
                for record in records:
                    row = record.to_dict()
                    writer.writerow({col: row.get(col, "") for col in EXPORT_COLUMNS})
            event_bus.emit(event_bus.EXPORT_COMPLETED, format="csv", path=path, count=len(records))
            return len(records)
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            event_bus.emit(event_bus.EXPORT_FAILED, format="csv", error=str(e))
            raise

    def export_json(self, records: list[LeadRecord], path: str) -> int:
        """Export records to JSON."""
        logger.info(f"Exporting {len(records)} records to JSON: {path}")
        try:
            data = [record.to_dict() for record in records]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            event_bus.emit(event_bus.EXPORT_COMPLETED, format="json", path=path, count=len(records))
            return len(records)
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            event_bus.emit(event_bus.EXPORT_FAILED, format="json", error=str(e))
            raise

    def export_excel(self, records: list[LeadRecord], path: str) -> int:
        """Export records to Excel XLSX format."""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("openpyxl required for Excel export: pip install openpyxl")

        logger.info(f"Exporting {len(records)} records to Excel: {path}")
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Leads"

            # Header styling
            header_fill = PatternFill("solid", fgColor="1A2B3C")
            header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
            alt_fill = PatternFill("solid", fgColor="F0F4F8")
            thin = Side(border_style="thin", color="D0D8E0")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            # Write headers
            for col_idx, col_name in enumerate(EXPORT_COLUMNS, 1):
                cell = ws.cell(row=1, column=col_idx, value=col_name.replace("_", " ").title())
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border

            ws.row_dimensions[1].height = 20

            # Write data rows
            for row_idx, record in enumerate(records, 2):
                row_data = record.to_dict()
                fill = alt_fill if row_idx % 2 == 0 else None
                for col_idx, col_name in enumerate(EXPORT_COLUMNS, 1):
                    val = row_data.get(col_name, "")
                    if val is None:
                        val = ""
                    cell = ws.cell(row=row_idx, column=col_idx, value=str(val))
                    cell.font = Font(name="Calibri", size=9)
                    cell.border = border
                    if fill:
                        cell.fill = fill
                    # Hyperlink for URLs
                    if col_name in ("website", "source_url", "maps_url", "email_source_page") and val:
                        url = val if val.startswith("http") else f"mailto:{val}" if "@" in val else val
                        try:
                            cell.hyperlink = url
                            cell.font = Font(name="Calibri", size=9, color="0066CC", underline="single")
                        except Exception:
                            pass

            # Auto-size columns
            col_widths = {
                "company_name": 30, "email": 35, "website": 40, "address": 35,
                "job_title": 30, "phone": 18, "city": 18, "description": 50,
            }
            for col_idx, col_name in enumerate(EXPORT_COLUMNS, 1):
                width = col_widths.get(col_name, 15)
                ws.column_dimensions[get_column_letter(col_idx)].width = width

            # Freeze header row
            ws.freeze_panes = "A2"

            # Auto-filter
            ws.auto_filter.ref = ws.dimensions

            wb.save(path)
            event_bus.emit(event_bus.EXPORT_COMPLETED, format="xlsx", path=path, count=len(records))
            return len(records)
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            event_bus.emit(event_bus.EXPORT_FAILED, format="xlsx", error=str(e))
            raise

    def export_docx(self, records: list[LeadRecord], path: str) -> int:
        """Export records to a Word DOCX document."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx required for Word export: pip install python-docx")

        logger.info(f"Exporting {len(records)} records to Word: {path}")
        try:
            doc = Document()
            doc.add_heading("ZUGZWANG Export", level=1)
            doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            doc.add_paragraph(f"Records: {len(records)}")

            for index, record in enumerate(records, 1):
                doc.add_heading(f"{index}. {record.company_name or record.job_title or 'Lead'}", level=2)
                table = doc.add_table(rows=0, cols=2)
                table.style = "Table Grid"

                row_data = record.to_dict()
                for col in EXPORT_COLUMNS:
                    value = row_data.get(col, "")
                    if value in (None, ""):
                        continue
                    cells = table.add_row().cells
                    cells[0].text = col.replace("_", " ").title()
                    cells[1].text = str(value)

            doc.save(path)
            event_bus.emit(event_bus.EXPORT_COMPLETED, format="docx", path=path, count=len(records))
            return len(records)
        except Exception as e:
            logger.error(f"Word export failed: {e}")
            event_bus.emit(event_bus.EXPORT_FAILED, format="docx", error=str(e))
            raise

    def save_project(self, job: ScrapingJob, path: str) -> None:
        """Save a scraping job (with results) to SQLite project file."""
        logger.info(f"Saving project to: {path}")
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            self._init_db(conn)
            conn.execute(
                "INSERT OR REPLACE INTO jobs (id, config_json, status, stats_json, created_at, started_at, completed_at) VALUES (?,?,?,?,?,?,?)",
                (
                    job.id,
                    json.dumps(self._serialize_config(job)),
                    job.status.value,
                    json.dumps({
                        "total_found": job.total_found,
                        "total_emails": job.total_emails,
                        "total_websites": job.total_websites,
                        "total_errors": job.total_errors,
                    }),
                    job.created_at,
                    job.started_at,
                    job.completed_at,
                ),
            )
            for record in job.results:
                prepared = self._prepare_record(record)
                row = prepared.to_dict()
                conn.execute(
                    f"INSERT OR REPLACE INTO leads ({','.join(EXPORT_COLUMNS)}) VALUES ({','.join(['?']*len(EXPORT_COLUMNS))})",
                    [row.get(c, "") for c in EXPORT_COLUMNS],
                )
            conn.commit()
            logger.info(f"Project saved: {len(job.results)} leads")
        finally:
            conn.close()

    def load_project(self, path: str) -> tuple[Optional[dict], list[LeadRecord]]:
        """Load a project from SQLite file. Returns (job_meta, records)."""
        logger.info(f"Loading project from: {path}")
        conn = sqlite3.connect(path)
        try:
            self._init_db(conn)
            job_row = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
            job_meta = None
            if job_row:
                cols = [d[0] for d in conn.execute("SELECT * FROM jobs LIMIT 0").description]
                job_meta = dict(zip(cols, job_row))

            leads_rows = conn.execute(f"SELECT {','.join(EXPORT_COLUMNS)} FROM leads").fetchall()
            records = []
            seen_ids: set[str] = set()
            cleaned_rows: list[dict] = []
            dirty = False
            for row in leads_rows:
                d = dict(zip(EXPORT_COLUMNS, row))
                try:
                    record = LeadRecord.from_dict(d).normalize()
                    record.id = record.stable_id()
                    cleaned = record.to_dict()
                    cleaned_rows.append(cleaned)
                    comparable_original = {col: (d.get(col) if d.get(col) is not None else "") for col in EXPORT_COLUMNS}
                    comparable_cleaned = {col: (cleaned.get(col) if cleaned.get(col) is not None else "") for col in EXPORT_COLUMNS}
                    if comparable_original != comparable_cleaned:
                        dirty = True
                    if record.id in seen_ids:
                        dirty = True
                        continue
                    seen_ids.add(record.id)
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Could not parse lead record: {e}")

            if dirty:
                try:
                    conn.execute("DELETE FROM leads")
                    persisted_ids: set[str] = set()
                    for record in records:
                        prepared = self._prepare_record(record)
                        if prepared.id in persisted_ids:
                            continue
                        persisted_ids.add(prepared.id)
                        row = prepared.to_dict()
                        conn.execute(
                            f"INSERT OR REPLACE INTO leads ({','.join(EXPORT_COLUMNS)}) VALUES ({','.join(['?']*len(EXPORT_COLUMNS))})",
                            [row.get(c, "") for c in EXPORT_COLUMNS],
                        )
                    conn.commit()
                    logger.info(f"Normalized and cleaned persisted project data at: {path}")
                except Exception as e:
                    logger.warning(f"Could not persist cleaned project data for {path}: {e}")
            return job_meta, records
        finally:
            conn.close()

    def _init_db(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                config_json TEXT,
                status TEXT,
                stats_json TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT
            )
        """)
        cols_def = ", ".join(f"{c} TEXT" for c in EXPORT_COLUMNS)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS leads (
                {cols_def},
                PRIMARY KEY (id)
            )
        """)
        conn.commit()

    def generate_filename(self, prefix: str, extension: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.{extension}"

    def _prepare_record(self, record: LeadRecord) -> LeadRecord:
        prepared = replace(record).normalize()
        prepared.id = prepared.stable_id()
        return prepared

    def _serialize_config(self, job: ScrapingJob) -> dict:
        data = dict(job.config.__dict__)
        source_type = data.get("source_type")
        if source_type is not None and hasattr(source_type, "value"):
            data["source_type"] = source_type.value
        return data
