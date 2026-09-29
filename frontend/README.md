# AyniAlert dashboard

Vue 3 and TypeScript dashboard for location-scoped environmental conditions, informational alert states, and recent history.

## Local development

Use Node.js 24 LTS (`.nvmrc`) and run:

```bash
npm install
npm run typecheck
npm run test:run
npm run test:e2e
npm run dev
```

Install Chromium and its Linux dependencies once before running Playwright:

```bash
npx playwright install chromium
npx playwright install-deps chromium
```

Vite proxies `/api` to the deployed development API. Override `VITE_API_BASE_URL` only when the target environment requires a different API origin.

## Production build

The API base URL is public configuration compiled into the static JavaScript bundle:

```bash
VITE_API_BASE_URL="https://sjf63cndec.execute-api.us-east-1.amazonaws.com/dev" npm run build
```

Publish the contents of `dist/`, not the directory itself, at the root of the private S3 dashboard bucket. Use `Cache-Control: no-cache` for `index.html` and `Cache-Control: public, max-age=31536000, immutable` for hashed files under `assets/`. CloudFront serves the bucket through Origin Access Control; the bucket must remain private.

## Structure

```text
src/
├── components/   # Presentational condition, freshness, alert, and history views
├── composables/  # View-state orchestration
├── services/     # HTTP boundary and runtime response checks
└── types/        # Public API response types
```

The dashboard labels project thresholds as informational and never presents AyniAlert as an official warning system.
