"""Google Drive helpers."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

import config

LOGGER = logging.getLogger(__name__)


class DriveClient:
    """Thin wrapper around the Google Drive API."""

    SCOPES = ["https://www.googleapis.com/auth/drive"]
    FOLDER_MIME = "application/vnd.google-apps.folder"

    def __init__(self, credentials_path: Optional[str] = None) -> None:
        self.credentials = self._build_credentials(credentials_path)
        self.service = build(
            "drive", "v3", credentials=self.credentials, cache_discovery=False
        )

    def _build_credentials(self, credentials_path: Optional[str]):
        if config.GOOGLE_OAUTH_CLIENT_SECRETS:
            return self._build_oauth_credentials()
        creds_path = credentials_path or config.GOOGLE_APPLICATION_CREDENTIALS
        if not creds_path:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS must be set when OAuth secrets are missing"
            )
        return service_account.Credentials.from_service_account_file(
            creds_path, scopes=self.SCOPES
        )

    def _build_oauth_credentials(self):
        token_path: Path = config.GOOGLE_OAUTH_TOKEN_FILE
        creds: Optional[Credentials] = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.GOOGLE_OAUTH_CLIENT_SECRETS,
                    self.SCOPES,
                )
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())
        LOGGER.info("Using OAuth credentials stored in %s", token_path)
        return creds

    def list_files_in_folder(
        self, folder_id: str, *, recursive: bool = False
    ) -> List[Dict[str, str]]:
        """Return metadata for files located inside the folder.

        When ``recursive`` is True, descend into all nested folders.
        """

        def fetch(folder: str) -> List[Dict[str, str]]:
            query = f"'{folder}' in parents and trashed = false"
            fields = "nextPageToken, files(id, name, modifiedTime, mimeType)"
            entries: List[Dict[str, str]] = []
            page_token: Optional[str] = None
            while True:
                request = (
                    self.service.files()
                    .list(
                        q=query,
                        fields=fields,
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                )
                response = request.execute()
                entries.extend(response.get("files", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            return entries

        if not recursive:
            results = fetch(folder_id)
            LOGGER.debug("Retrieved %d files for folder %s", len(results), folder_id)
            return results

        files: List[Dict[str, str]] = []
        stack = [folder_id]
        visited = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            entries = fetch(current)
            for entry in entries:
                if entry.get("mimeType") == self.FOLDER_MIME:
                    stack.append(entry["id"])
                else:
                    files.append(entry)
        LOGGER.debug(
            "Retrieved %d files for folder %s recursively", len(files), folder_id
        )
        return files

    def download_file(self, file_id: str, local_path) -> None:
        """Download a Drive file to *local_path*."""
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        LOGGER.debug("Downloaded file %s to %s", file_id, local_path)

    def upload_file(
        self,
        local_path,
        folder_id: str,
        mime_type: str,
        file_name: Optional[str] = None,
    ) -> str:
        """Upload a local file and return the Drive file id."""
        metadata = {
            "name": file_name or getattr(local_path, "name", "report.md"),
            "parents": [folder_id],
        }
        media = MediaFileUpload(str(local_path), mimetype=mime_type)
        request = self.service.files().create(
            body=metadata, media_body=media, fields="id", supportsAllDrives=True
        )
        response = request.execute()
        drive_id = response["id"]
        LOGGER.debug("Uploaded %s as %s", local_path, drive_id)
        return drive_id
