import csv
import io
import logging
import threading
from dataclasses import dataclass, fields
from datetime import datetime, timezone

from services.drive_service import DriveService

logger = logging.getLogger(__name__)

CSV_FILENAME = "цифровки.csv"
CSV_MIME = "text/csv"
CSV_FIELDS = [
    "folder_id", "folder_name", "version", "content",
    "author", "created_at", "updated_at", "note",
]
BOM = "\ufeff"


@dataclass
class Cifrovka:
    folder_id: str
    folder_name: str
    version: int
    content: str
    author: str
    created_at: str
    updated_at: str
    note: str = ""


class CifrovkaService:
    def __init__(self, drive: DriveService, root_folder_id: str):
        self._drive = drive
        self._root_folder_id = root_folder_id
        self._lock = threading.Lock()

    def _get_csv_file_id(self) -> str | None:
        file_info = self._drive.find_file_by_name(self._root_folder_id, CSV_FILENAME)
        return file_info["id"] if file_info else None

    def _load_csv(self) -> list[Cifrovka]:
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
            rows.append(Cifrovka(
                folder_id=row["folder_id"],
                folder_name=row["folder_name"],
                version=int(row["version"]),
                content=row["content"],
                author=row["author"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                note=row.get("note", ""),
            ))
        return rows

    def _save_csv(self, rows: list[Cifrovka]) -> None:
        buf = io.StringIO()
        buf.write(BOM)
        writer = csv.DictWriter(
            buf, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({f.name: getattr(r, f.name) for f in fields(r)})

        data = buf.getvalue().encode("utf-8")
        file_id = self._get_csv_file_id()
        if not file_id:
            raise FileNotFoundError(
                f"Файл «{CSV_FILENAME}» не найден на Google Drive. "
                "Создайте его вручную в корневой папке."
            )
        self._drive.update_file(file_id, data, CSV_MIME)

    def _filter(self, rows: list[Cifrovka], folder_id: str, folder_name: str) -> list[Cifrovka]:
        by_id = [r for r in rows if r.folder_id == folder_id]
        if by_id:
            return sorted(by_id, key=lambda r: r.version)
        by_name = [r for r in rows if r.folder_name == folder_name]
        return sorted(by_name, key=lambda r: r.version)

    def get_versions(self, folder_id: str, folder_name: str) -> list[Cifrovka]:
        with self._lock:
            rows = self._load_csv()
        return self._filter(rows, folder_id, folder_name)

    def get_latest_version(self, folder_id: str, folder_name: str) -> Cifrovka | None:
        versions = self.get_versions(folder_id, folder_name)
        return versions[-1] if versions else None

    def create_version(
        self,
        folder_id: str,
        folder_name: str,
        content: str,
        author: str,
        note: str = "",
    ) -> Cifrovka:
        with self._lock:
            rows = self._load_csv()
            existing = self._filter(rows, folder_id, folder_name)
            next_ver = existing[-1].version + 1 if existing else 1
            now = datetime.now(timezone.utc).isoformat()

            entry = Cifrovka(
                folder_id=folder_id,
                folder_name=folder_name,
                version=next_ver,
                content=content,
                author=author,
                created_at=now,
                updated_at=now,
                note=note,
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
    ) -> Cifrovka | None:
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
