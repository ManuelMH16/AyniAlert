# AyniAlert dashboard

Vue 3 and TypeScript dashboard for location-scoped environmental conditions, informational alert states, and recent history.

## Local development

Use Node.js 24 LTS (`.nvmrc`) and run:

```bash
npm install
npm run typecheck
npm run test:run
npm run dev
```

Vite proxies `/api` to the deployed development API. Override `VITE_API_BASE_URL` only when the target environment requires a different API origin.

## Structure

```text
src/
├── components/   # Presentational condition, freshness, alert, and history views
├── composables/  # View-state orchestration
├── services/     # HTTP boundary and runtime response checks
└── types/        # Public API response types
```

The dashboard labels project thresholds as informational and never presents AyniAlert as an official warning system.
