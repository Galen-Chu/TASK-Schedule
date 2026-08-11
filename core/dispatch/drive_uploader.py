"""Google Drive upload — interface defined, upload not yet implemented.

Configured via ``GOOGLE_APPLICATION_CREDENTIALS`` (path to a service-account
JSON). With no credentials the call is a safe no-op so the pipeline still
completes in CI.
"""
import os
import logging

log = logging.getLogger("dispatch.drive")


def is_configured():
    return bool(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    )


def upload_to_drive(file_path, folder_id=None):
    """Upload ``file_path`` to Google Drive; return the share link or None."""
    if not is_configured():
        log.info("Drive 上傳未設定（缺少 GOOGLE_APPLICATION_CREDENTIALS），略過。")
        return None
    # TODO: implement with googleapiclient.http.MediaFileUpload + Drive v3 create.
    log.warning("Drive 上傳介面已定義但未實作（需 google-api-python-client）。")
    return None
