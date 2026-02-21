import csv
import io
import logging
import threading
from dataclasses import dataclass, fields
from datetime import datetime, timezone

from services.drive_service import DriveService

logger = logging.getLogger(__name__)

CSV_FILENAME = "формы.csv"
CSV_MIME = "text/csv"
CSV_FIELDS = [
    "folder_id", "folder_name", "version", "content",
    "author", "created_at", "updated_at", "note", "pinned",
]
BOM = "\ufeff"


@dataclass
class Form:
    folder_id: str
    folder_name: str
    version: int
    content: str
    author: str
    created_at: str
    updated_at: str
    note: str = ""
    pinned: bool = False


class FormService:
    def __init__(self, drive: DriveService, root_folder_id: str):
        self._drive = drive
        self._root_folder_id = root_folder_id
        self._lock = threading.Lock()

    def _get_csv_file_id(self) -> str | None:
        file_info = self._drive.find_file_by_name(self._root_folder_id, CSV_FILENAME)
        return file_info["id"] if file_info else None

    def _load_csv(self) -> list[Form]:
        file_info = self._drive.find_file_by_name(self._root_folder_id, CSV_FILENAME)
        if not file_info:
            return []

        content_bytes, _ = self._drive.download_file(file_info["id"])
        text = content_bytes.decode("utf-8-sig")
        if not text.strip():
            return []

        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            rows.append(Form(
                folder_id=row["folder_id"],
                folder_name=row["folder_name"],
                version=int(row["version"]),
                content=row["content"],
                author=row["author"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                note=row.get("note", ""),
                pinned=row.get("pinned", "").lower() == "true",
            ))
        return rows

    def _save_csv(self, rows: list[Form]) -> None:
        buf = io.StringIO()
        buf.write(BOM)
        writer = csv.DictWriter(
            buf, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for r in rows:
            row_dict = {f.name: getattr(r, f.name) for f in fields(r)}
            row_dict["pinned"] = "true" if r.pinned else "false"
            writer.writerow(row_dict)

        data = buf.getvalue().encode("utf-8")
        file_id = self._get_csv_file_id()
        if not file_id:
            raise FileNotFoundError(
                f"Файл «{CSV_FILENAME}» не найден на Google Drive. "
                "Создайте его вручную в корневой папке."
            )
        self._drive.update_file(file_id, data, CSV_MIME)

    def _filter(self, rows: list[Form], folder_id: str, folder_name: str) -> list[Form]:
        by_id = [r for r in rows if r.folder_id == folder_id]
        if by_id:
            return by_id
        return [r for r in rows if r.folder_name == folder_name]

    @staticmethod
    def _sort_for_display(versions: list[Form]) -> list[Form]:
        """Sort by version ascending, pinned version goes last.
        If none explicitly pinned, the highest version is naturally last."""
        pinned = [v for v in versions if v.pinned]
        unpinned = [v for v in versions if not v.pinned]
        unpinned.sort(key=lambda v: v.version)
        if pinned:
            return unpinned + pinned
        return unpinned

    def get_versions(self, folder_id: str, folder_name: str) -> list[Form]:
        with self._lock:
            rows = self._load_csv()
        matched = self._filter(rows, folder_id, folder_name)
        return self._sort_for_display(matched)

    def get_latest_version(self, folder_id: str, folder_name: str) -> Form | None:
        versions = self.get_versions(folder_id, folder_name)
        return versions[0] if versions else None

    def create_version(
        self,
        folder_id: str,
        folder_name: str,
        content: str,
        author: str,
        note: str = "",
    ) -> Form:
        with self._lock:
            rows = self._load_csv()
            existing = self._filter(rows, folder_id, folder_name)
            for e in existing:
                e.pinned = False
            next_ver = max((e.version for e in existing), default=0) + 1
            now = datetime.now(timezone.utc).isoformat()

            entry = Form(
                folder_id=folder_id,
                folder_name=folder_name,
                version=next_ver,
                content=content,
                author=author,
                created_at=now,
                updated_at=now,
                note=note,
                pinned=False,
            )
            rows.append(entry)
            self._save_csv(rows)
        return entry

    def edit_version(
        self,
        folder_id: str,
        version: int,
        content: str,
        note: str,
        author: str,
    ) -> Form | None:
        with self._lock:
            rows = self._load_csv()
            for r in rows:
                if r.folder_id == folder_id and r.version == version:
                    r.content = content
                    r.note = note
                    r.author = author
                    r.updated_at = datetime.now(timezone.utc).isoformat()
                    self._save_csv(rows)
                    return r
        return None

    def delete_version(self, folder_id: str, version: int) -> bool:
        with self._lock:
            rows = self._load_csv()
            new_rows = [
                r for r in rows
                if not (r.folder_id == folder_id and r.version == version)
            ]
            if len(new_rows) == len(rows):
                return False
            self._save_csv(new_rows)
        return True

    def toggle_pin(self, folder_id: str, version: int) -> bool:
        """Pin version if not pinned (unpins others), unpin if already pinned.
        Returns new pinned state."""
        with self._lock:
            rows = self._load_csv()
            target = None
            folder_rows = []
            for r in rows:
                if r.folder_id == folder_id:
                    folder_rows.append(r)
                    if r.version == version:
                        target = r

            if not target:
                return False

            if target.pinned:
                target.pinned = False
            else:
                for r in folder_rows:
                    r.pinned = False
                target.pinned = True

            self._save_csv(rows)
            return target.pinned
