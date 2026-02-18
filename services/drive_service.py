import io
import threading

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveService:
    def __init__(self, credentials_path: str):
        self._credentials_path = credentials_path
        self.service = self._build_service()
        self._local = threading.local()

    def _build_service(self):
        creds = service_account.Credentials.from_service_account_file(
            self._credentials_path, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds)

    def _get_thread_service(self):
        if not hasattr(self._local, "service"):
            self._local.service = self._build_service()
        return self._local.service

    def list_folders(self, parent_folder_id: str) -> list[dict]:
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
        return results.get("files", [])

    def list_files(self, folder_id: str) -> list[dict]:
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
        return results.get("files", [])

    def download_file(self, file_id: str) -> tuple[bytes, str]:
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

        return buffer.getvalue(), filename

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
        return {"id": result["id"], "name": result["name"]}

    @staticmethod
    def get_folder_link(folder_id: str) -> str:
        return f"https://drive.google.com/drive/folders/{folder_id}"
