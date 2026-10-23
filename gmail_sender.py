"""Gmail API OAuth with the minimal gmail.send scope."""

import base64
from email.message import EmailMessage
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
BASE = Path(__file__).resolve().parent


def authorized_gmail():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    credentials_path = BASE / 'credentials.json'
    token_path = BASE / 'token.json'
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise RuntimeError(
                    'Missing credentials.json. See README.md for Google Cloud setup.'
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding='utf-8')
        try:
            token_path.chmod(0o600)
        except OSError:
            pass
    return build('gmail', 'v1', credentials=creds)


def send_using_service(service, recipient: str, subject: str, body: str) -> str:
    # Recipient/subject/body must already be approved and validated by the graph.
    msg = EmailMessage()
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.set_content(body)
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode('ascii')
    result = service.users().messages().send(
        userId='me', body={'raw': encoded}
    ).execute()
    return str(result['id'])
