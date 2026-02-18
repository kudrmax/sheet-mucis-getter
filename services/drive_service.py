import io
import logging
import threading

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
logger = logging.getLogger(__name__)


class DriveService:
    def __init__(self, credentials_path: str):
        self._credentials_path = credentials_path
        self.service = self._build_service()
        self._local = threading.local()

        # Cache: {folder_id: {"modified_time": str, "data": list}}
        self._folder_list_cache: dict[str, dict] = {}
        self._file_list_cache: dict[str, dict] = {}

        # File content cache: {file_id: {"content": bytes, "filename": str}}
        self._file_content_cache: dict[str, dict] = {}

        # Mapping file_id -> folder_id (populated by list_files)
        self._file_to_folder: dict[str, str] = {}

    def _build_service(self):
        creds = service_account.Credentials.from_service_account_file(
            self._credentials_path, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds)

    def _get_thread_service(self):
        if not hasattr(self._local, "service"):
            self._local.service = self._build_service()
        return self._local.service

    def _get_modified_time(self, folder_id: str) -> str:
        """Lightweight API call to get folder's modifiedTime."""
        result = (
            self.service.files()
            .get(fileId=folder_id, fields="modifiedTime")
            .execute()
        )
        return result["modifiedTime"]

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
        modified_time = self._get_modified_time(parent_folder_id)

        cached = self._folder_list_cache.get(parent_folder_id)
        if cached and cached["modified_time"] == modified_time:
            logger.debug("list_folders cache HIT for %s", parent_folder_id)
            return cached["data"]

        logger.debug("list_folders cache MISS for %s", parent_folder_id)
        query = (
            f"'{parent_folder_id}' in parents "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = (
            self.service.files()
            .list(q=query, fields="files(id, name)", orderBy="name")
            .execute()
        )
        data = results.get("files", [])

        self._folder_list_cache[parent_folder_id] = {
            "modified_time": modified_time,
            "data": data,
        }
        return data

    def list_files(self, folder_id: str) -> list[dict]:
        modified_time = self._get_modified_time(folder_id)

        cached = self._file_list_cache.get(folder_id)
        if cached and cached["modified_time"] == modified_time:
            logger.debug("list_files cache HIT for %s", folder_id)
            return cached["data"]

        logger.debug("list_files cache MISS for %s", folder_id)

        # Cache miss — invalidate file content cache for this folder
        self._invalidate_folder_files(folder_id)

        query = (
            f"'{folder_id}' in parents "
            "and mimeType != 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = (
            self.service.files()
            .list(q=query, fields="files(id, name, mimeType)", orderBy="name")
            .execute()
        )
        data = results.get("files", [])

        self._file_list_cache[folder_id] = {
            "modified_time": modified_time,
            "data": data,
        }

        # Update file -> folder mapping
        for f in data:
            self._file_to_folder[f["id"]] = folder_id

        return data

    def download_file(self, file_id: str) -> tuple[bytes, str]:
        cached = self._file_content_cache.get(file_id)
        if cached:
            logger.debug("download_file cache HIT for %s", file_id)
            return cached["content"], cached["filename"]

        logger.debug("download_file cache MISS for %s", file_id)
        service = self._get_thread_service()

        file_meta = (
            service.files().get(fileId=file_id, fields="name").execute()
        )
        filename = file_meta["name"]

        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

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
        folder = (
            self.service.files()
            .create(body=metadata, fields="id, name")
            .execute()
        )

        # Invalidate folder list cache for parent
        self._folder_list_cache.pop(parent_id, None)
        logger.debug("Invalidated folder_list cache for %s after create_folder", parent_id)

        return {"id": folder["id"], "name": folder["name"]}

    def upload_file(
        self, file_content: bytes, filename: str, folder_id: str
    ) -> dict:
        metadata = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), mimetype="application/octet-stream"
        )
        result = (
            self.service.files()
            .create(body=metadata, media_body=media, fields="id, name")
            .execute()
        )

        # Invalidate file list cache and file content cache for this folder
        self._file_list_cache.pop(folder_id, None)
        self._invalidate_folder_files(folder_id)
        logger.debug("Invalidated file_list cache for %s after upload_file", folder_id)

        return {"id": result["id"], "name": result["name"]}

    @staticmethod
    def get_folder_link(folder_id: str) -> str:
        return f"https://drive.google.com/drive/folders/{folder_id}"
