from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"
IMAGE_MIMES = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}


class GoogleDriveClient:
    def __init__(self, credentials_path: Path, token_path: Path):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = build("drive", "v3", credentials=self._credentials(), cache_discovery=False)

    def _credentials(self) -> Credentials:
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"Google OAuth credentials file not found: {self.credentials_path}")
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def account_identity(self) -> dict:
        return self.service.about().get(fields="user(displayName,emailAddress,photoLink)").execute().get("user", {})

    def folder_metadata(self, folder_id: str) -> dict:
        return self.service.files().get(
            fileId=folder_id,
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()

    def download_file(self, file_id: str) -> bytes:
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        output = BytesIO()
        downloader = MediaIoBaseDownload(output, request, chunksize=4 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return output.getvalue()

    def walk_images(self, root_folder_id: str) -> Iterator[dict]:
        pending = [root_folder_id]
        while pending:
            parent_id = pending.pop()
            page_token = None
            while True:
                response = self.service.files().list(
                    q=f"'{parent_id}' in parents and trashed = false",
                    spaces="drive",
                    fields="nextPageToken,files(id,name,mimeType,modifiedTime,size,webViewLink,parents)",
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                for item in response.get("files", []):
                    if item.get("mimeType") == FOLDER_MIME:
                        pending.append(item["id"])
                    elif item.get("mimeType") in IMAGE_MIMES:
                        yield item
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
