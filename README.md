# Kaburu - Email to Webhook (YunoHost)

**Simple proof-of-concept:** Forward emails to webhooks using IMAP polling (YunoHost-compatible)

## How it works

1. Creates a YunoHost user/mailbox (e.g., `webhook@yourdomain.com`)
2. Polls the mailbox via IMAP every minute
3. Forwards email metadata + attachments to your webhook
4. No Postfix modifications needed!

## Installation

```bash
yunohost app install https://github.com/rahak/kaburu_ynh
```

You'll be asked:
- **Domain**: Where to receive email
- **Local part**: Username (e.g., "webhook" for webhook@domain.com)
- **Webhook URL**: Where to POST email data
- **API Secret**: For HMAC-SHA256 signature verification
- **Parse attachments**: Extract attachments? (true/false)

## Testing first

Test the concept before installing:

```bash
# Copy test script to server
scp test_imap_webhook.py root@your-server:/tmp/

# Edit credentials and run
python3 /tmp/test_imap_webhook.py
```

## Webhook payload

```json
{
  "from": "sender@example.com",
  "to": "webhook@yourdomain.com",
  "subject": "Test email",
  "date": "Fri, 13 Dec 2025 10:00:00 +0000",
  "attachments": [
    {"filename": "file.pdf", "size": 12345}
  ]
}
```

Headers:
- `X-Email-Signature`: HMAC-SHA256 signature
- `X-Email-Address`: Receiving email address

## Logs

```bash
tail -f /opt/kaburu/logs/cron.log
```

## Uninstall

```bash
yunohost app remove kaburu
```

Removes the mailbox, cron job, and all files.