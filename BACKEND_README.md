# CYBER-GRID INTEL Terminal - Barchart Backend

## Backend Setup (Local Testing)

### Prerequisites
- Python 3.7+
- pip

### Installation

1. **Install Dependencies:**
```bash
cd "/Users/newuser/AG\$NT 3 /"
pip3 install -r requirements.txt
```

2. **Run Local Server:**
```bash
cd api
python3 -m http.server 8000 --bind 127.0.0.1
```

Or use Python's built-in server with the handler:
```bash
python3 -c "from http.server import HTTPServer; from index import handler; HTTPServer(('localhost', 8000), handler).serve_forever()"
```

3. **Update Frontend:**
   - Change the fetch URL in `app.js` from `/api/index` to `http://localhost:8000/api/index`
   - Open `index.html` in your browser

---

## Production Deployment (Vercel - FREE)

### Setup Vercel

1. **Install Vercel CLI:**
```bash
npm install -g vercel
```

2. **Deploy:**
```bash
cd "/Users/newuser/AG\$NT 3 /"
vercel
```

3. **Follow Prompts:**
   - Link to your Vercel account
   - Name your project
   - Deploy!

Your API will be live at: `https://your-project.vercel.app/api/index`

---

## How It Works

**Backend (`api/index.py`):**
- Scrapes Barchart's "Unusual Options Activity" page
- Extracts XSRF token for authentication
- Fetches live data from their internal API
- Returns JSON to frontend

**Frontend (`app.js`):**
- Fetches from `/api/index` every 60 seconds
- Maps Barchart data to our widget format
- Falls back to mock data if the API fails

---

## Troubleshooting

**CORS Errors?**
- Make sure the backend is serving with `Access-Control-Allow-Origin: *`

**No Data?**
- Check browser console for errors
- The backend will fallback to mock data automatically

**Barchart Blocked You?**
- The scraper uses realistic headers and cookies
- If blocked, the fallback mock data keeps the UI working
