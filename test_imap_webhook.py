#!/usr/bin/env python3
"""
Minimal proof-of-concept: IMAP polling → webhook forwarding
Tests YunoHost-compatible email processing without Postfix changes
"""
import imaplib
import email
from email import policy
import requests
import json
import sys

# ===== CONFIGURATION =====
# Edit these values for your setup
IMAP_SERVER = "localhost"  # or your YunoHost server IP/domain
IMAP_PORT = 143
EMAIL_ADDRESS = "doorsery@lib.navanudi.com"
EMAIL_PASSWORD = "your_password_here"  # Replace with actual password
WEBHOOK_URL = "https://153648c10220.ngrok-free.app/webhooks/email/inbound"
# =========================

def test_imap_connection():
    """Test basic IMAP connection"""
    print(f"🔌 Connecting to IMAP server: {IMAP_SERVER}:{IMAP_PORT}")
    try:
        mail = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)
        print("✅ IMAP connection established")
        return mail
    except Exception as e:
        print(f"❌ IMAP connection failed: {e}")
        sys.exit(1)

def test_login(mail):
    """Test IMAP login"""
    print(f"🔐 Logging in as: {EMAIL_ADDRESS}")
    try:
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        print("✅ IMAP login successful")
    except Exception as e:
        print(f"❌ IMAP login failed: {e}")
        print("   Check your email address and password")
        sys.exit(1)

def fetch_emails(mail):
    """Fetch all emails from inbox"""
    print("📬 Selecting INBOX...")
    mail.select('INBOX')
    
    print("🔍 Searching for emails...")
    status, messages = mail.search(None, 'ALL')
    
    if status != 'OK':
        print("❌ Failed to search emails")
        return []
    
    email_ids = messages[0].split()
    print(f"📨 Found {len(email_ids)} email(s)")
    
    emails = []
    for email_id in email_ids:
        print(f"   Fetching email ID: {email_id.decode()}")
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status == 'OK':
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email, policy=policy.default)
            
            # Extract basic info
            email_info = {
                "id": email_id.decode(),
                "from": msg.get("From"),
                "to": msg.get("To"),
                "subject": msg.get("Subject"),
                "date": msg.get("Date"),
                "body": extract_body(msg)
            }
            emails.append(email_info)
            
            print(f"      From: {email_info['from']}")
            print(f"      Subject: {email_info['subject']}")
    
    return emails

def extract_body(msg):
    """Extract email body (text/plain preferred)"""
    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == 'text/plain':
                return part.get_content()
    else:
        if msg.get_content_type() == 'text/plain':
            return msg.get_content()
    return "(no text body found)"

def post_to_webhook(email_data):
    """Post email data to webhook"""
    print(f"\n🚀 Posting to webhook: {WEBHOOK_URL}")
    
    payload = {
        "email": email_data,
        "test": True,
        "message": "Proof-of-concept IMAP polling test"
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Webhook POST successful")
        else:
            print(f"⚠️  Webhook returned non-200 status")
            
    except requests.exceptions.Timeout:
        print("❌ Webhook request timed out")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Failed to connect to webhook: {e}")
    except Exception as e:
        print(f"❌ Webhook POST failed: {e}")

def main():
    print("=" * 60)
    print("🧪 IMAP → Webhook Proof-of-Concept Test")
    print("=" * 60)
    print()
    
    # Step 1: Connect
    mail = test_imap_connection()
    
    # Step 2: Login
    test_login(mail)
    
    # Step 3: Fetch emails
    emails = fetch_emails(mail)
    
    # Step 4: Post to webhook
    if emails:
        print(f"\n📤 Testing webhook with {len(emails)} email(s)...")
        for i, email_data in enumerate(emails, 1):
            print(f"\n--- Email {i}/{len(emails)} ---")
            post_to_webhook(email_data)
    else:
        print("\n📭 No emails found in mailbox")
        print("   Send a test email to verify delivery works")
    
    # Cleanup
    mail.close()
    mail.logout()
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. If this works, your YunoHost setup is ready")
    print("2. Install the full Kaburu app for production use")
    print("3. The app will run this check every minute via cron")

if __name__ == "__main__":
    # Quick validation
    if EMAIL_PASSWORD == "your_password_here":
        print("❌ ERROR: Please edit the script and set EMAIL_PASSWORD")
        print("   Open this file and update the configuration section at the top")
        sys.exit(1)
    
    main()
