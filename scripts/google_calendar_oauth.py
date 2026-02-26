"""Google Calendar OAuth2 token acquisition script.

Automates the OAuth2 flow:
1. Reads client credentials from .env
2. Opens the authorization URL in a browser
3. Receives the callback on a local HTTP server
4. Exchanges the authorization code for tokens
5. Prints access_token and refresh_token

Usage:
    uv run python scripts/google_calendar_oauth.py
    uv run python scripts/google_calendar_oauth.py --port 9090

Prerequisites:
    - Set GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET in .env
    - Add http://localhost:8080 (or your --port) as an authorized redirect URI
      in Google Cloud Console > APIs & Services > Credentials
"""

import argparse
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import dotenv_values

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


def load_credentials() -> tuple[str, str]:
    env = dotenv_values(".env")
    client_id = env.get("GOOGLE_CALENDAR_CLIENT_ID", "")
    client_secret = env.get("GOOGLE_CALENDAR_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print(
            "Error: GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET "
            "must be set in .env",
            file=sys.stderr,
        )
        sys.exit(1)
    return client_id, client_secret


def build_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_tokens(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict:
    response = httpx.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()
    return response.json()


def wait_for_callback(port: int, expected_state: str) -> str:
    """Start a local HTTP server and wait for the OAuth2 callback.

    Returns the authorization code.
    """
    authorization_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            nonlocal authorization_code
            query = parse_qs(urlparse(self.path).query)

            error = query.get("error", [None])[0]
            if error:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"<h1>Authorization failed</h1><p>{error}</p>".encode()
                )
                authorization_code = ""
                return

            state = query.get("state", [None])[0]
            if state != expected_state:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Invalid state parameter</h1>")
                authorization_code = ""
                return

            code = query.get("code", [None])[0]
            if not code:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>No authorization code received</h1>")
                authorization_code = ""
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<h1>Authorization successful!</h1>"
                b"<p>You can close this tab and return to the terminal.</p>"
            )
            authorization_code = code

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = HTTPServer(("localhost", port), CallbackHandler)
    while authorization_code is None:
        server.handle_request()
    server.server_close()

    if not authorization_code:
        print("Error: Failed to receive authorization code.", file=sys.stderr)
        sys.exit(1)

    return authorization_code


def main():
    parser = argparse.ArgumentParser(description="Obtain Google Calendar OAuth2 tokens")
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Local server port for OAuth2 callback (default: 8080)",
    )
    args = parser.parse_args()

    client_id, client_secret = load_credentials()
    redirect_uri = f"http://localhost:{args.port}"
    state = secrets.token_urlsafe(32)

    auth_url = build_authorization_url(client_id, redirect_uri, state)

    print("Opening browser for authorization...")
    print(f"If the browser doesn't open, visit this URL manually:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print(f"Waiting for callback on {redirect_uri} ...")
    code = wait_for_callback(args.port, state)

    print("Exchanging authorization code for tokens...")
    tokens = exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    print("\n" + "=" * 50)
    print("Tokens obtained successfully!")
    print("=" * 50)
    print(f"\nGOOGLE_CALENDAR_ACCESS_TOKEN={access_token}")
    print(f"GOOGLE_CALENDAR_REFRESH_TOKEN={refresh_token}")
    print("\nCopy these values to your .env or deployment environment.")
    if not refresh_token:
        print(
            "\nWarning: No refresh_token received. "
            "You may need to revoke access at "
            "https://myaccount.google.com/permissions "
            "and re-run this script with prompt=consent."
        )


if __name__ == "__main__":
    main()
