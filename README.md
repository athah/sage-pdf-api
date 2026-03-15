# Sage Media PDF Report API

Flask API that generates branded Instagram performance reports as PDF files.

## Deploy to Render.com (Free)

1. Create a GitHub repo and push these 3 files: `app.py`, `requirements.txt`, `Procfile`
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 60`
   - **Instance Type**: Free
5. Click Deploy → wait ~2 min → get your URL (e.g. `https://sage-pdf-api.onrender.com`)

## API Reference

### POST /generate

Generates a PDF report.

**Request body (JSON):**
```json
{
  "brand_name": "Tatvadhan Jaipur",
  "month": "March 2026",
  "account_manager": "Athah Mittal",
  "report_date": "15 March 2026",
  "reach": "50314",
  "interactions": "1211",
  "accounts_engaged": "832",
  "profile_views": "1159",
  "website_clicks": "94",
  "new_followers": "0",
  "story_replies": "5",
  "eng_rate": "1.65%",
  "ai_summary": "Your AI summary text here..."
}
```

**Response:** PDF file download

### GET /health

Returns `{"status": "ok"}`

## Make.com Integration (Delivery Scenario)

In the approval scenario (8860878), add an HTTP module before the email:

1. **Module**: HTTP → Make a Request
2. **URL**: `https://YOUR-APP.onrender.com/generate`
3. **Method**: POST
4. **Headers**: `Content-Type: application/json`
5. **Body (Raw JSON)**:
```json
{
  "brand_name": "{{1.`Brand Name`}}",
  "month": "{{1.Month}}",
  "account_manager": "{{1.`Account Manager`}}",
  "report_date": "{{formatDate(now; \"D MMMM YYYY\")}}",
  "reach": "{{1.Reach}}",
  "interactions": "{{1.Interactions}}",
  "accounts_engaged": "{{1.`Accounts Engaged`}}",
  "profile_views": "{{1.`Profile Views`}}",
  "website_clicks": "{{1.`Website Clicks`}}",
  "new_followers": "{{1.`New Followers`}}",
  "story_replies": "{{1.`Story Replies`}}",
  "eng_rate": "{{round(1.`Accounts Engaged` / 1.Reach * 100; 2)}}%",
  "ai_summary": "{{1.`AI Summary`}}"
}
```
6. **Parse response**: The response `data` field contains the raw PDF bytes — use as email attachment.
