# Companies House API Integration Guide

## 🎯 Overview

This enhancement adds **live Companies House API search** to Control Room without removing any existing functionality. The local JSON search remains fully operational.

## 🔐 Setup Instructions

### 1. Get Your API Key

1. Visit https://developer.company-information.service.gov.uk/
2. Create a free account
3. Generate an API key (it's instant and free)

### 2. Configure Environment

1. Open `.env` file in the project root
2. Replace `your_api_key_here` with your actual API key:
   ```
   CH_API_KEY=your_actual_api_key_here
   ```
3. Save the file

**IMPORTANT:** The `.env` file is already in `.gitignore` - your API key will never be committed to version control.

### 3. Start the Server

```bash
python scripts/dev_server.py
```

Or specify a custom port:

```bash
python scripts/dev_server.py 8080
```

The server will confirm it's running:
```
Serving + proxy on http://localhost:8000
Proxy base: /ch  -> https://api.company-information.service.gov.uk
```

### 4. Open in Browser

Navigate to:
```
http://localhost:8000
```

## 📋 How to Use

### Local Search (Existing - Unchanged)

In the **Companies** tab:

1. Use the first section with fields:
   - Company Name
   - Company Number
   - Postcode
   - Post Town
2. Click **Plot all** to search local JSON files
3. Results appear in the list below
4. Click any result to plot on map

### API Search (NEW)

In the same **Companies** tab, scroll to the **"OR SEARCH LIVE API"** section:

1. Type company name in the **Live Company Search** field
2. Suggestions appear automatically as you type (debounced 400ms)
3. Click any suggestion to:
   - Fetch full company profile
   - Display company details
   - Plot on map using registered office postcode

**Features:**
- ✅ As-you-type suggestions (max 20 results)
- ✅ Automatic debouncing (reduces API calls)
- ✅ Smart caching (2 min for search, 10 min for profiles)
- ✅ Distinct green markers for API results
- ✅ Postcode geocoding using existing infrastructure
- ✅ Popup shows: Name, Number, Address, Status

## 🏗️ Architecture

```
Browser (Leaflet UI)
    ↓
JavaScript (ch_api.js)
    ↓
Local Proxy (dev_server.py at localhost:8000/ch)
    ↓
Companies House API (with Basic Auth)
```

**Why a proxy?**
- ✅ Prevents CORS errors
- ✅ Keeps API key secret (server-side only)
- ✅ Enables caching and throttling
- ✅ Allows request logging

## 🔒 Security Features

1. **API key never exposed to browser** - stored in `.env` on server
2. **Environment file protected** - `.gitignore` prevents commits
3. **Basic Auth handled server-side** - credentials never in JavaScript
4. **CORS properly configured** - proxy adds correct headers
5. **Error handling** - graceful failures with clear messages

## 🧪 Quick Test

### Test Case: Bristol City FC Ltd

1. Start the server with your API key configured
2. Go to Companies tab → Live Company Search
3. Type: `bristol city`
4. You should see suggestions including "BRISTOL CITY FOOTBALL CLUB LIMITED"
5. Click it
6. Verify:
   - Company details appear in green card
   - Marker appears on map (Bristol area)
   - Popup shows correct information
   - Marker is green (API result indicator)

### Test Case: Known Company Number

1. Type: `tesco`
2. Look for "TESCO PLC"
3. Company number should be: 00445790
4. Address: Welwyn Garden City or Hertfordshire

## 📁 Files Added (Zero Removals)

### New Files
- `.env` - API key storage (not committed)
- `.gitignore` - Security protection
- `js/ch_api.js` - API client module
- `COMPANIES_HOUSE_API.md` - This documentation

### Modified Files (Additive Only)
- `index.html` - Added API search UI section + script tag
- `css/style.css` - Added styles for suggestions dropdown

### Unchanged Files
- `scripts/dev_server.py` - Already had proxy endpoints
- `js/map.js` - No modifications
- `js/config.js` - No modifications

## 🎨 UI Changes

### Companies Tab

```
┌─────────────────────────────┐
│ EXISTING LOCAL SEARCH       │
│ - Company Name              │
│ - Company Number            │
│ - Postcode                  │
│ - Post Town                 │
│ [Plot all] [Clear]          │
│ Results: ...                │
├─────────────────────────────┤
│ ── OR SEARCH LIVE API ──    │ ← NEW
│ Live Company Search         │ ← NEW
│ [Type here...]              │ ← NEW
│ Suggestions dropdown ↓      │ ← NEW
│ Selected company card       │ ← NEW
└─────────────────────────────┘
```

### Map Markers

- **Purple/Indigo**: Local search results (existing)
- **Green**: API search results (NEW) - easily distinguishable

## 🚀 API Endpoints Used

### 1. Search Companies
```
GET /ch/search/companies?q={query}&items_per_page={limit}
```

Returns:
```json
{
  "items": [
    {
      "title": "COMPANY NAME",
      "company_number": "12345678",
      "address_snippet": "City, Postcode"
    }
  ]
}
```

### 2. Company Profile
```
GET /ch/company/{company_number}
```

Returns:
```json
{
  "company_name": "FULL NAME",
  "company_number": "12345678",
  "company_status": "active",
  "registered_office_address": {
    "address_line_1": "...",
    "locality": "...",
    "postal_code": "..."
  }
}
```

## ⚡ Performance Optimizations

1. **Debouncing**: 400ms delay prevents excessive API calls while typing
2. **Result limiting**: Max 20 suggestions (configurable)
3. **Two-tier caching**:
   - Search results: 2 minutes TTL
   - Company profiles: 10 minutes TTL
4. **LRU eviction**: Prevents unlimited memory growth (50 search, 100 profiles)
5. **Postcode area caching**: Reuses existing postcode lookup infrastructure

## 🛠️ Troubleshooting

### "CH_API_KEY env var not set"

**Problem:** Server can't find API key

**Solution:**
1. Check `.env` file exists in project root
2. Verify it contains: `CH_API_KEY=your_key_here`
3. Restart the dev_server.py

### No suggestions appear

**Problem:** API calls failing

**Solution:**
1. Open browser DevTools (F12) → Console
2. Look for error messages
3. Check Network tab for failed `/ch/` requests
4. Verify API key is valid at https://developer.company-information.service.gov.uk/

### "Postcode not found in database"

**Problem:** Company postcode not in local geocoding data

**Solution:**
- This is expected for some postcodes
- Local postcode database may not be complete
- Company still displays in info card
- Just can't be plotted on map

### CORS errors

**Problem:** Direct API calls without proxy

**Solution:**
- This should never happen if setup correctly
- Verify you're accessing via `http://localhost:8000`
- Check ch_api.js is using `/ch/` endpoints (not direct URLs)

## 📚 API Documentation

Full Companies House API documentation:
- Guide: https://chguide.co.uk/
- Official Docs: https://developer.company-information.service.gov.uk/api/docs/

## 🔄 Rate Limits

Companies House API (as of 2026):
- 600 requests per 5 minutes
- No daily limit

Our caching strategy ensures you stay well within limits for normal usage.

## ✅ Verification Checklist

- [ ] `.env` file created with valid API key
- [ ] `.gitignore` includes `.env`
- [ ] Server starts without errors
- [ ] Browser console shows no errors
- [ ] Typing in API search shows suggestions
- [ ] Clicking suggestion loads company details
- [ ] Company plots on map with green marker
- [ ] Existing local search still works
- [ ] All existing features unchanged

## 🎓 Code Quality

- ✅ Zero removals - all existing code intact
- ✅ Clear separation - API module is independent
- ✅ Commented code - explains "why" not just "what"
- ✅ Error handling - graceful degradation
- ✅ Security first - API key never exposed
- ✅ Performance optimized - smart caching & debouncing
- ✅ UI consistent - matches existing dark theme

---

**Questions?** Check the code comments in `js/ch_api.js` and `scripts/dev_server.py` for detailed explanations.
