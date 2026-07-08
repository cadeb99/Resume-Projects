"""
Shared Google OAuth handling for Calendar, Tasks, and Gmail.

First run: opens a browser for you to log in and approve access.
After that: reuses a saved token, refreshing it silently as needed.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import config

# One set of scopes covers all three APIs — requested together so you
# only have to go through the browser approval flow once.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def get_credentials():
    """Returns valid Google API credentials, running the OAuth flow if needed."""
    creds = None

    if os.path.exists(config.GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(config.GOOGLE_TOKEN_PATH), exist_ok=True)
        with open(config.GOOGLE_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds
