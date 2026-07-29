"""
Delivers the report via Gmail API in live mode. In demo mode, writes the HTML
to reports/output/latest_report.html instead so the pipeline is fully
testable with zero Google credentials.
"""
import os
import config


def send_report(html_content, subject=None):
    subject = subject or f"{config.STORE_NAME} — Weekly Marketing Intelligence Report"
    if config.DEMO_MODE:
        return _write_to_file(html_content)
    return _send_live(html_content, subject)


def _write_to_file(html_content):
    os.makedirs(config.REPORT_OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(config.REPORT_OUTPUT_DIR, "latest_report.html")
    with open(out_path, "w") as f:
        f.write(html_content)
    print(f"[DEMO MODE] Report written to {out_path} (no email sent).")
    return out_path


def _send_live(html_content, subject):
    """
    TODO once credentials exist: build a MIME message, base64-encode, send via
    Gmail API using GMAIL_CREDENTIALS_PATH / GMAIL_TOKEN_PATH OAuth flow,
    to config.REPORT_RECIPIENTS.
    """
    raise NotImplementedError(
        "Live Gmail sending not yet wired. Set DEMO_MODE=True in config.py, "
        "or implement _send_live() with real Gmail API credentials."
    )
