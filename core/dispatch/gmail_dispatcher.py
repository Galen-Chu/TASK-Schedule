"""Gmail digest — interface defined, send not yet implemented.

Configured via ``GOOGLE_APPLICATION_CREDENTIALS``. Without it the call is a
safe no-op.
"""
import os
import logging

log = logging.getLogger("dispatch.gmail")


def is_configured():
    return bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))


def send_digest(to_addr, subject, body, attachments=None):
    """Send a daily digest email; return the message id or None."""
    if not is_configured():
        log.info("Gmail 寄送未設定，略過。")
        return None
    # TODO: implement with googleapiclient Gmail v1 users().messages().send().
    log.warning("Gmail 介面已定義但未實作（需 google-api-python-client）。")
    return None
