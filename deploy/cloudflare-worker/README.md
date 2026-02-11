# Control Room Cloudflare Worker Proxy

This Worker replaces `scripts/dev_server.py` for hosted/static deployments.

## 1) Prereqs

- Cloudflare account
- Node.js + npm
- Wrangler CLI:

```bash
npm i -g wrangler
```

## 2) Login

```bash
wrangler login
```

## 3) Deploy

From `deploy/cloudflare-worker`:

```bash
wrangler deploy
```

This creates a URL like:

`https://control-room-proxy.<your-subdomain>.workers.dev`

## 4) Set Worker secrets

Set only what you need:

```bash
wrangler secret put CH_API_KEY
wrangler secret put OS_PLACES_API_KEY
wrangler secret put SIGNALBOX_API_KEY
wrangler secret put AVIATIONSTACK_API_KEY
```

## 5) Point the frontend at Worker

In `js/api_keys.js` add:

```js
window.CONTROL_ROOM_API_BASE = "https://control-room-proxy.<your-subdomain>.workers.dev";
```

If this variable is set, frontend calls like `/tfl/*`, `/ch/*`, `/signalbox/*`, `/webtris/*` are routed to Worker instead of localhost.

## 6) Publish frontend

Push to GitHub Pages as normal. No local Python server needed.

## Notes

- WebTRIS is CORS-friendly and can run direct, but Worker unifies API routing.
- Signalbox generally needs Worker proxy due browser CORS/auth behavior.
- `/nre/stations` and `/geo/search` are implemented in Worker for rail UX support.
