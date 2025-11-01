# Google Cloud Vision API Setup

## Prerequisites

The reverse image search feature uses Google Cloud Vision API's Web Detection feature.

## Setup Steps

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your Project ID

### 2. Enable the Vision API

1. In the Cloud Console, go to **APIs & Services** > **Library**
2. Search for "Cloud Vision API"
3. Click **Enable**

### 3. Create a Service Account

1. Go to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Name: `document-validator-vision` (or your choice)
4. Role: **Cloud Vision API User** or **Owner** (for testing)
5. Click **Create and Continue**
6. Click **Done**

### 4. Create and Download Key

1. Click on the service account you just created
2. Go to **Keys** tab
3. Click **Add Key** > **Create new key**
4. Select **JSON** format
5. Click **Create**
6. Save the downloaded JSON file securely (e.g., `vision-credentials.json`)

### 5. Set Environment Variable

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your JSON key file:

**MacOS/Linux:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/vision-credentials.json"
```

**Or add to your shell profile (~/.zshrc or ~/.bashrc):**
```bash
echo 'export GOOGLE_APPLICATION_CREDENTIALS="/path/to/vision-credentials.json"' >> ~/.zshrc
source ~/.zshrc
```

**Windows:**
```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\vision-credentials.json
```

### 6. Restart the Backend Server

After setting the environment variable, restart your backend:

```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

## Verify Setup

To verify the API is working:

1. Upload an image document to the validator
2. Check the authenticity section for "Reverse Image Search" results
3. If configured correctly, you'll see matches from the web

## Pricing

Google Cloud Vision API pricing (as of 2024):
- First 1,000 Web Detection requests per month: **FREE**
- After that: $3.50 per 1,000 requests

For a hackathon with limited testing, you'll likely stay within the free tier.

## Troubleshooting

**Error: "Could not automatically determine credentials"**
- Ensure `GOOGLE_APPLICATION_CREDENTIALS` is set correctly
- Verify the JSON file path is absolute and accessible
- Restart your terminal/IDE after setting the variable

**Error: "Permission denied"**
- Check that the Vision API is enabled in your project
- Verify the service account has the correct role

**No results returned:**
- The implementation gracefully fails if credentials aren't configured
- Check backend logs for any Vision API errors
- Verify your image is being uploaded correctly

## For Hackathon Demo Without API

If you don't want to set up Google Cloud for the hackathon:
- The system will work without reverse image search
- It will return empty results (graceful degradation)
- All other features (EXIF, pHash, ELA, AI detection, risk scoring) work independently
