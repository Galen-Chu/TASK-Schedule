#!/usr/bin/env python3
"""Google Drive upload — OAuth-user or service-account implementation.

Two auth paths, checked in this order:

1. **OAuth user credentials** (free Gmail friendly): set the env vars
   ``GOOGLE_OAUTH_CLIENT_ID`` / ``GOOGLE_OAUTH_CLIENT_SECRET`` /
   ``GOOGLE_REFRESH_TOKEN``. Files are owned by the USER (who has storage
   quota), so uploads to the user's own Drive folders work. The refresh
   token comes from a one-time consent — run ``scripts/drive_oauth_setup.py``.
2. **Service account** (Workspace shared drives only): a JSON key pointed at
   by ``GOOGLE_APPLICATION_CREDENTIALS``. SAs have NO storage quota on
   personal My-Drive folders (HTTP 403 storageQuotaExceeded by design), so
   this path only works for folders inside a 共用雲端硬碟.

Layout: one root folder (env ``DRIVE_FOLDER_ID`` / config ``drive_folder_id``,
else the account's own root), with a subfolder per report created lazily
(Financial / Global / Spiritual / Macro). Files are named ``<date>_<report>.pdf``.

With no credentials configured, every call is a safe no-op so the pipeline
still completes in CI.
"""
import os
import logging

log = logging.getLogger("dispatch.drive")

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_service = None
_tried_init = False

# Cache: subfolder name -> folder id, so we don't query/create per upload.
_subfolder_cache = {}


def _credentials():
    """OAuth-user credentials when configured, else the service-account key."""
    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    csec = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    rt = os.environ.get("GOOGLE_REFRESH_TOKEN")
    if cid and csec and rt:
        try:
            from google.oauth2.credentials import Credentials as UserCredentials
            log.info("Drive 使用 OAuth 使用者憑證（檔案歸使用者帳號）。")
            return UserCredentials(
                token=None, refresh_token=rt, client_id=cid, client_secret=csec,
                token_uri="https://oauth2.googleapis.com/token", scopes=_SCOPES,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Drive OAuth 憑證建立失敗 (%s)。", exc)
            return None
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path or not os.path.isfile(path):
        return None
    try:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(path, scopes=_SCOPES)
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive 憑證載入失敗 (%s)。", exc)
        return None


def _service_obj():
    """Lazily build the Drive v3 service. Returns None if unavailable."""
    global _service, _tried_init
    if _tried_init:
        return _service
    _tried_init = True
    creds = _credentials()
    if creds is None:
        return None
    try:
        from googleapiclient.discovery import build
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive service 建立失敗 (%s)。", exc)
        return None


def is_configured():
    """True only if credentials resolve AND the Drive service built."""
    return _service_obj() is not None


def _ensure_subfolder(parent_id, name):
    """Find or create a subfolder ``name`` under ``parent_id``. Returns its id."""
    if name in _subfolder_cache:
        return _subfolder_cache[name]
    svc = _service_obj()
    if svc is None:
        return None
    # Search for an existing folder with this name under the parent.
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
         f"and trashed=false")
    if parent_id:
        q += f" and '{parent_id}' in parents"
    try:
        res = svc.files().list(q=q, spaces="drive", fields="files(id,name)",
                               supportsAllDrives=True,
                               includeItemsFromAllDrives=True).execute()
        files = res.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                body["parents"] = [parent_id]
            created = svc.files().create(body=body, fields="id").execute()
            folder_id = created.get("id")
        _subfolder_cache[name] = folder_id
        return folder_id
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive 子資料夾建立/查詢失敗 (%s)。", exc)
        return None


def upload_to_drive(file_path, folder_id=None, subfolder=None, report_id=None):
    """Upload ``file_path`` to Drive. Returns the share link, or None.

    ``folder_id``: root folder id (else the account's own Drive root).
    ``subfolder``/``report_id``: if given, place the file under a per-report
        subfolder (created lazily) named by ``subfolder or report_id``.
    """
    svc = _service_obj()
    if svc is None:
        log.info("Drive 上傳未設定（缺少 GOOGLE_APPLICATION_CREDENTIALS），略過。")
        return None

    # Fall back to the DRIVE_FOLDER_ID env var when no explicit folder_id is
    # passed, so the CI workflow only needs a secret (not a spark.yaml).
    if folder_id is None:
        folder_id = os.environ.get("DRIVE_FOLDER_ID")

    name = subfolder or report_id
    parent = folder_id
    if name:
        parent = _ensure_subfolder(folder_id, name) or folder_id

    try:
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(file_path, resumable=True)
        body = {"name": os.path.basename(file_path)}
        if parent:
            body["parents"] = [parent]
        meta = svc.files().create(body=body, media_body=media, fields="id,webViewLink",
                                  supportsAllDrives=True).execute()
        link = meta.get("webViewLink")
        log.info("Drive 上傳成功：%s -> %s", os.path.basename(file_path), link)
        return link
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive 上傳失敗 (%s)。", exc)
        return None
