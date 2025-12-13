# Inbound Email Webhook (YunoHost App)

This app allows you to:

- Receive inbound email on a selected YunoHost domain
- Parse attachments
- Forward metadata to a webhook endpoint
- Send a status email back to the sender

## Requirements

- YunoHost >= 11
- Working email domain

## Configuration

During install you choose:
- Domain
- Email address (local part)
- Webhook URL
- API secret

## Security

Webhook requests are signed using HMAC-SHA256.

The signature is sent in the `X-Email-Signature` header.
The API secret is used as the HMAC key.

Verify signatures on your webhook endpoint before processing requests.

## Installation

Install directly from the Git repository:

```bash
sudo yunohost app install https://github.com/yourusername/email-api
```