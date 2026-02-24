# Email Domain Setup Guide

This guide walks through verifying a custom domain with Resend for outreach email sending.

## Why Domain Verification?

Without a verified domain, emails are sent from Resend's shared domain and have poor deliverability. A verified custom domain (e.g., `eran-jobs.com`) ensures:

- Emails pass SPF, DKIM, and DMARC checks
- Higher inbox placement rates
- Professional sender address (e.g., `outreach@eran-jobs.com`)

## Step-by-Step Setup

### 1. Log in to Resend

Go to https://resend.com/domains and sign in.

### 2. Add your domain

Click **Add Domain** and enter your domain (e.g., `eran-jobs.com`).

### 3. Add DNS records

Resend will provide DNS records to add to your domain registrar. You'll need to add:

| Type | Name | Value | Purpose |
|------|------|-------|---------|
| MX | `feedback.eran-jobs.com` | (provided by Resend) | Bounce handling |
| TXT | `eran-jobs.com` | `v=spf1 include:amazonses.com ~all` | SPF — authorizes Resend to send on your behalf |
| TXT (DKIM) | (provided by Resend) | (provided by Resend) | DKIM — email signature verification |

**Where to add these records:**
- Log in to your domain registrar (e.g., Cloudflare, Namecheap, GoDaddy)
- Navigate to DNS settings for your domain
- Add each record exactly as Resend specifies

### 4. Wait for DNS propagation

DNS changes can take 15 minutes to 48 hours to propagate. You can check propagation status:

```bash
# Check SPF record
dig TXT eran-jobs.com +short

# Check MX record
dig MX feedback.eran-jobs.com +short
```

### 5. Verify in Resend

Return to https://resend.com/domains and click **Verify** next to your domain. Resend will check all DNS records.

Once verified, you'll see a green checkmark.

### 6. Update environment variables

Set these in your `.env` file:

```
SENDER_EMAIL=outreach@eran-jobs.com
RESEND_API_KEY=re_your_api_key_here
```

### 7. Test with a real outreach send

1. Start the backend
2. Create a candidate account and upload a resume
3. Discover and approve a company
4. Send a test outreach email from the Outreach page
5. Check the recipient inbox (and spam folder) to confirm delivery

## Troubleshooting

- **Emails going to spam:** Ensure all 3 DNS records (MX, SPF, DKIM) are correctly set. Use https://mxtoolbox.com to verify.
- **Verification stuck:** DNS propagation can take up to 48 hours. Try again later.
- **Bounce errors:** Check the Resend dashboard logs for bounce reasons. Common cause: typos in the MX record.

## DMARC (Optional but Recommended)

For maximum deliverability, add a DMARC record:

```
Type: TXT
Name: _dmarc.eran-jobs.com
Value: v=DMARC1; p=none; rua=mailto:dmarc@eran-jobs.com
```

Start with `p=none` (monitor only), then tighten to `p=quarantine` or `p=reject` once you're confident in your setup.
