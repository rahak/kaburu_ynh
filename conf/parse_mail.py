#!/usr/bin/env python3
import sys
import os
import json
import hmac
import hashlib
import subprocess
import requests
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / "config.json"
DATA_DIR = SCRIPT_DIR / "data"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

try:
    cfg = load_config()
except Exception as e:
    sys.stderr.write(f"Error loading config: {e}\n")
    sys.exit(1)

WEBHOOK_URL = cfg.get("webhook_url")
API_SECRET = cfg.get("api_secret")
EMAIL_ADDR = f"{cfg.get('local_part')}@{cfg.get('domain')}"
PARSE_ATTACHMENTS = bool(cfg.get("parse_attachments"))

# Handle relative webhook URL
if WEBHOOK_URL.startswith("/"):
    WEBHOOK_URL = f"http://127.0.0.1{WEBHOOK_URL}"

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# --- Parse email ---
try:
    raw = sys.stdin.buffer.read()
    msg = BytesParser(policy=policy.default).parsebytes(raw)
except Exception as e:
    sys.stderr.write(f"Error parsing email: {e}\n")
    sys.exit(1)

payload = {
    "from": msg.get("From"),
    "to": msg.get("To"),
    "subject": msg.get("Subject"),
    "attachments": []
}

# --- Attachments ---
if PARSE_ATTACHMENTS:
    for part in msg.iter_attachments():
        filename = part.get_filename()
        if not filename:
            continue
        
        data = part.get_payload(decode=True)
        if data:
            # Save to disk (optional, but good for debugging or if webhook needs to fetch)
            # We overwrite files with same name for now, or could use unique names
            path = os.path.join(DATA_DIR, filename)
            with open(path, "wb") as f:
                f.write(data)
            
            payload["attachments"].append({
                "filename": filename,
                "size": len(data)
            })

# --- Sign payload ---
body = json.dumps(payload).encode()
signature = hmac.new(
    API_SECRET.encode(), body, hashlib.sha256
).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-Email-Signature": signature,
    "X-Email-Address": EMAIL_ADDR
}

# --- Send to Webhook ---
status = "error"
try:
    response = requests.post(WEBHOOK_URL, data=body, headers=headers, timeout=10)
    if response.status_code == 200:
        try:
            resp_json = response.json()
            status = resp_json.get("status", "accepted")
        except:
            status = "accepted"
    else:
        sys.stderr.write(f"Webhook returned {response.status_code}\n")
        status = "error"

except Exception as e:
    sys.stderr.write(f"Error contacting webhook: {e}\n")
    status = "error"

# --- Send status email back ---
sender = msg.get("From")
if sender:
    _, sender_addr = parseaddr(sender)
    if sender_addr:
        subject = f"Email delivery status: {status}"
        body_text = f"Your email to {EMAIL_ADDR} was processed.\n\nStatus: {status}\n"
        
        if status == "error":
            body_text += "There was an error processing your email.\n"
        elif status == "ignored":
            body_text += "Your email was ignored by the system.\n"
        
        full_msg = f"From: {EMAIL_ADDR}\nTo: {sender_addr}\nSubject: {subject}\n\n{body_text}"
        
        sendmail_cmd = ["/usr/sbin/sendmail", "-f", EMAIL_ADDR, sender_addr]
        try:
            p = subprocess.Popen(sendmail_cmd, stdin=subprocess.PIPE)
            p.communicate(input=full_msg.encode())
        except Exception as e:
            sys.stderr.write(f"Error sending status email: {e}\n")
