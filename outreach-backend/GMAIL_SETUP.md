# Gmail API Setup Guide

## File Locations

### 1. `credentials.json` (OAuth Client Credentials)
- **Location**: `outreach-backend/credentials.json`
- **Purpose**: Contains your OAuth 2.0 client ID and secret from Google Cloud Console
- **Security**: Keep this file secure and never commit it to git
- **One-time setup**: Download from Google Cloud Console

**Your credentials.json should contain:**
```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID_HERE",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET_HERE",
    "redirect_uris": ["http://localhost"]
  }
}

```

### 2. `token.json` (OAuth Access/Refresh Token)
- **Location**: `outreach-backend/token.json` (or `.storage/token.json`)
- **Purpose**: Contains the user's access token and refresh token (generated after OAuth flow)
- **Security**: Keep this file secure and never commit it to git
- **Auto-generated**: Created automatically when you run the OAuth flow
- **Auto-refresh**: Automatically refreshes when expired (if refresh_token is present)

## Setup Steps

### Step 1: Create credentials.json
1. Create the file `outreach-backend/credentials.json`
2. Paste your OAuth credentials (the JSON content you provided)
3. Save the file

### Step 2: Run OAuth Flow to Generate token.json
```bash
cd outreach-backend
python setup_gmail_oauth.py
```

This will:
- Open a browser window
- Ask you to sign in to Google
- Request Gmail send permissions
- Save the token to `token.json`

### Step 3: Test Gmail API
```bash
# Set your test email
$env:TEST_EMAIL = "your-email@example.com"

# Run the test
python -m outreach-backend.email_sender
```

Or test directly:
```python
from outreach-backend.email_sender import send_gmail_html
send_gmail_html("test@example.com", "Test Subject", "<p>Test body</p>")
```

## How It Works

1. **First Run**: 
   - `credentials.json` is loaded
   - OAuth flow starts (browser opens)
   - User signs in and grants permissions
   - `token.json` is created with access & refresh tokens

2. **Subsequent Runs**:
   - `token.json` is loaded
   - If expired, refresh token is used to get a new access token
   - Token is automatically saved back to `token.json`

3. **Token Expired/Invalid**:
   - If refresh fails, OAuth flow runs again
   - New token is saved to `token.json`

## Troubleshooting

### Error: "credentials.json not found"
- Make sure `credentials.json` is in `outreach-backend/` directory
- Check the file name is exactly `credentials.json`

### Error: "Token expired and refresh failed"
- Delete `token.json` and run the OAuth flow again
- Run: `python setup_gmail_oauth.py`

### Error: "Permission denied" (403)
- Check Gmail API is enabled in Google Cloud Console
- Verify OAuth scopes include `gmail.send`
- Make sure you granted permissions during OAuth flow

### Error: "Authentication failed" (401)
- Token may be invalid or revoked
- Delete `token.json` and run OAuth flow again

## File Structure

```
outreach-backend/
├── credentials.json       # OAuth client credentials (you create this)
├── token.json            # OAuth access token (auto-generated)
├── email_sender.py       # Email sending code
└── setup_gmail_oauth.py  # OAuth setup script
```

## Security Notes

- **Never commit `credentials.json` or `token.json` to git**
- These files contain sensitive authentication information
- Add to `.gitignore`:
  ```
  credentials.json
  token.json
  *.json
  ```

