import io
import logging
import threading
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = (1, 2, 4)


def _with_retry(func):
    """Retry on transient connection errors."""
    for attempt in range(MAX_RETRIES):
        try:
            return func()
        except ConnectionError as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_DELAYS[attempt]
            logger.warning("Connection error (attempt %d/%d), retrying in %ds: %s",
                           attempt + 1, MAX_RETRIES, delay, e)
            time.sleep(delay)


class DriveService:
    def __init__(self, credentials_path: str):
        self._credentials_path = credentials_path
        self.service = self._build_service()
        self._local = threading.local()

        # Cache: {folder_id: list[dict]}
        self._folder_list_cache: dict[str, list] = {}
        self._file_list_cache: dict[str, list] = {}

        # File content cache: {file_id: {"content": bytes, "filename": str}}
        self._file_content_cache: dict[str, dict] = {}

        # Mapping file_id -> folder_id (populated by list_files)
        self._file_to_folder: dict[str, str] = {}

        # Changes API token — tracks any change on the drive
        self._changes_token: str = self._get_start_page_token()

    def _build_service(self):
        creds = service_account.Credentials.from_service_account_file(
            self._credentials_path, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds)

    def _get_thread_service(self):
        if not hasattr(self._local, "service"):
            self._local.service = self._build_service()
        return self._local.service

    def _get_start_page_token(self) -> str:
        result = _with_retry(
            self.service.changes().getStartPageToken().execute
        )
        return result["startPageToken"]

    def _check_for_changes(self):
        """One lightweight API call: are there any changes since last check?
        If yes — drop all caches."""
        response = _with_retry(
            self.service.changes()
            .list(
                pageToken=self._changes_token,
                fields="nextPageToken,newStartPageToken,changes(fileId)",
                pageSize=1,
            )
            .execute
        )

        if not response.get("changes"):
            # No changes — caches are valid
            return

        logger.info("Обнаружены изменения на диске, сброс кеша")
        self._folder_list_cache.clear()
        self._file_list_cache.clear()
        self._file_content_cache.clear()
        self._file_to_folder.clear()

        # Drain remaining changes to get the latest token
        while "nextPageToken" in response:
            response = _with_retry(
                self.service.changes()
                .list(
                    pageToken=response["nextPageToken"],
                    fields="nextPageToken,newStartPageToken,changes(fileId)",
                    pageSize=100,
                )
                .execute
            )

        self._changes_token = response["newStartPageToken"]

    def _invalidate_folder_files(self, folder_id: str):
        """Remove file content cache for all files that belonged to a folder."""
        to_remove = [
            fid for fid, fol in self._file_to_folder.items()
            if fol == folder_id
        ]
        for fid in to_remove:
            self._file_content_cache.pop(fid, None)
            self._file_to_folder.pop(fid, None)

    def list_folders(self, parent_folder_id: str) -> list[dict]:
        self._check_for_changes()

        cached = self._folder_list_cache.get(parent_folder_id)
        if cached is not None:
            logger.info("list_folders: cache HIT (%d папок)", len(cached))
            return cached

        logger.info("list_folders: cache MISS, запрос к Drive API")
        query = (
            f"'{parent_folder_id}' in parents "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = _with_retry(
            self.service.files()
            .list(q=query, fields="files(id, name)", orderBy="name")
            .execute
        )
        data = results.get("files", [])

        self._folder_list_cache[parent_folder_id] = data
        return data

    def list_files(self, folder_id: str) -> list[dict]:
        self._check_for_changes()

        cached = self._file_list_cache.get(folder_id)
        if cached is not None:
            logger.info("list_files: cache HIT (%d файлов)", len(cached))
            return cached

        logger.info("list_files: cache MISS, запрос к Drive API")

        # Cache miss — invalidate file content cache for this folder
        self._invalidate_folder_files(folder_id)

        query = (
            f"'{folder_id}' in parents "
            "and mimeType != 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = _with_retry(
            self.service.files()
            .list(q=query, fields="files(id, name, mimeType)", orderBy="name")
            .execute
        )
        data = results.get("files", [])

        self._file_list_cache[folder_id] = data

        # Update file -> folder mapping
        for f in data:
            self._file_to_folder[f["id"]] = folder_id

        return data

    def download_file(self, file_id: str) -> tuple[bytes, str]:
        # No _check_for_changes here — already checked by list_files before download
        cached = self._file_content_cache.get(file_id)
        if cached:
            logger.info("download_file: cache HIT «%s»", cached["filename"])
            return cached["content"], cached["filename"]

        logger.info("download_file: cache MISS, скачиваю %s", file_id)
        service = self._get_thread_service()

        file_meta = _with_retry(
            service.files().get(fileId=file_id, fields="name").execute
        )
        filename = file_meta["name"]

        def _do_download():
            buf = io.BytesIO()
            req = service.files().get_media(fileId=file_id)
            dl = MediaIoBaseDownload(buf, req)
            done = False
            while not done:
                _, done = dl.next_chunk()
            return buf

        buffer = _with_retry(_do_download)

        content = buffer.getvalue()
        self._file_content_cache[file_id] = {
            "content": content,
            "filename": filename,
        }
        return content, filename

    def create_folder(self, name: str, parent_id: str) -> dict:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = _with_retry(
            self.service.files()
            .create(body=metadata, fields="id, name")
            .execute
        )

        # Invalidate + advance token so next _check_for_changes won't re-clear
        self._folder_list_cache.pop(parent_id, None)
        self._changes_token = self._get_start_page_token()
        logger.info("create_folder: «%s» создана, кеш папок сброшен", name)

        return {"id": folder["id"], "name": folder["name"]}

    def upload_file(
        self, file_content: bytes, filename: str, folder_id: str
    ) -> dict:
        metadata = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), mimetype="application/octet-stream"
        )
        result = _with_retry(
            self.service.files()
            .create(body=metadata, media_body=media, fields="id, name")
            .execute
        )

        # Invalidate + advance token so next _check_for_changes won't re-clear
        self._file_list_cache.pop(folder_id, None)
        self._invalidate_folder_files(folder_id)
        self._changes_token = self._get_start_page_token()
        logger.info("upload_file: «%s» загружен, кеш файлов сброшен", filename)

        return {"id": result["id"], "name": result["name"]}

    @staticmethod
    def get_folder_link(folder_id: str) -> str:
        return f"https://drive.google.com/drive/folders/{folder_id}"
