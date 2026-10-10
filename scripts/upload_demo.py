"""Upload a CodeGraph demo cast to asciinema.org without the asciinema CLI.

``asciinema`` itself cannot run on Windows (its recorder needs a Unix
pseudo-terminal), but the upload step is plain HTTP. This script mirrors what
``asciinema upload`` does:

* keeps an installation ID under ``%APPDATA%\\asciinema\\install-id`` (or
  ``~/.config/asciinema/install-id`` on Unix),
* POSTs the cast to ``https://asciinema.org/api/v1/recordings``,
* prints the recording URL and the link that claims it to your account.

Recordings uploaded from an unrecognised installation are deleted after 7 days
unless the claim link is opened, so this prints it prominently.

Usage:
    python scripts/upload_demo.py            # uploads demo.cast
    python scripts/upload_demo.py other.cast
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://asciinema.org/api/v1/recordings"


def install_id_path() -> Path:
    """Return the asciinema CLI's install-id location for this platform."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "asciinema" / "install-id"


def load_install_id() -> str:
    """Read the install ID, creating one on first use (like `asciinema auth`)."""
    path = install_id_path()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    return value


def build_body(cast_path: Path) -> tuple[bytes, str]:
    """Return a multipart/form-data body plus its boundary."""
    boundary = "----CodeGraphBoundary" + uuid.uuid4().hex
    data = cast_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{cast_path.name}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, boundary


def main() -> None:
    cast_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo.cast"
    if not cast_path.exists():
        sys.exit(f"Cast file not found: {cast_path}")

    install_id = load_install_id()
    token = base64.b64encode(f":{install_id}".encode()).decode()
    body, boundary = build_body(cast_path)

    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        sys.exit(f"Upload failed ({exc.code}): {exc.read().decode('utf-8', 'replace')}")

    url = payload.get("url") or payload.get("file_url", "")
    print(f"\nRecording: {url}")
    print(f"Claim this installation (keeps uploads past 7 days):")
    print(f"  https://asciinema.org/connect/{install_id}")


if __name__ == "__main__":
    main()