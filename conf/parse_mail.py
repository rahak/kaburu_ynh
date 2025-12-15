#!/usr/bin/env python3
import sys
import os
import json
import hmac
import hashlib
import subprocess
import requests
import imaplib
import time
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / "config.json"
DATA_DIR = SCRIPT_DIR / "data"
PROCESSED_FILE = SCRIPT_DIR / "processed_uids.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def load_processed_uids():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            return set(json.load(f))
    return set()

def save_processed_uids(uids):
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(list(uids), f)

try:
    cfg = load_config()
except Exception as e:
    sys.stderr.write(f"Error loading config: {e}\n")
    sys.exit(1)

WEBHOOK_URL = cfg.get("webhook_url")
API_SECRET = cfg.get("api_secret")
EMAIL_ADDR = f"{cfg.get('local_part')}@{cfg.get('domain')}"
PARSE_ATTACHMENTS = bool(cfg.get("parse_attachments"))
IMAP_PASSWORD = cfg.get("imap_password")

# Handle relative webhook URL
if WEBHOOK_URL.startswith("/"):
    WEBHOOK_URL = f"http://127.0.0.1{WEBHOOK_URL}"

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

def process_email(raw):
    """Process a single email message"""
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    
    payload = {
        "from": msg.get("From"),
        "to": msg.get("To"),
        "subject": msg.get("Subject"),
        "date": msg.get("Date"),
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
    
    return status

IMAP_HOST = cfg.get("domain") or "localhost"
IMAP_PORT_SSL = 993
USERNAME_LOCAL = cfg.get("local_part")
USERNAME_EMAIL = f"{cfg.get('local_part')}@{cfg.get('domain')}"

def check_imap():
    """Check IMAP mailbox for new emails"""
    processed_uids = load_processed_uids()
    try:
        # Use SSL with the domain/FQDN to match the cert
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT_SSL)
        try:
            mail.login(USERNAME_LOCAL, IMAP_PASSWORD)
        except Exception:
            mail.login(USERNAME_EMAIL, IMAP_PASSWORD)
        mail.select('INBOX')
        
        # Search for all emails
        _, message_numbers = mail.search(None, 'ALL')
        
        for num in message_numbers[0].split():
            uid = num.decode()
            if uid in processed_uids:
                continue
                
            _, msg_data = mail.fetch(num, '(RFC822)')
            raw = msg_data[0][1]
            
            try:
                process_email(raw)
                processed_uids.add(uid)
                
                # Delete processed email
                mail.store(num, '+FLAGS', '\\Deleted')
            except Exception as e:
                sys.stderr.write(f"Error processing email {uid}: {e}\n")
        
        mail.expunge()
        mail.close()
        mail.logout()
        
        save_processed_uids(processed_uids)
        
    except Exception as e:
        sys.stderr.write(f"IMAP error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    # Check if running from pipe (stdin) or as cron job
    if not sys.stdin.isatty():
        # Running from pipe - process single email
        try:
            raw = sys.stdin.buffer.read()
            process_email(raw)
        except Exception as e:
            sys.stderr.write(f"Error parsing email: {e}\n")
            sys.exit(1)
    else:
        # Running as cron job - check IMAP
        check_imap()
