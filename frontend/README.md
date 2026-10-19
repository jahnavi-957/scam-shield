# Scam Shield — Frontend

A calm, premium frontend for the Scam Shield fraud-detection backend.
Built with Vite + React + TypeScript + Tailwind CSS.

## Design

Minimalist, generous whitespace, restrained palette:

- **Base** — warm off-white `#fbfaf7` background, near-black `#1c1b19` text.
- **Accent** — deep indigo `#3b3f8c`, used sparingly for primary actions.
- **Status** — calm red `#b3402f` for scam verdicts, calm green `#2f7d5a` for
  safe verdicts. These appear rarely and meaningfully.
- **Typography** — system font stack (SF Pro-adjacent), explicit type scale
  from `xs` to `5xl`, generous line heights.
- **Motion** — 140–260ms ease transitions, `prefers-reduced-motion` respected.

See `src/styles/tokens.css` for the single source of truth.

## Running locally

```bash
npm install
npm run dev
```

The dev server runs on `http://localhost:5173`. Point it at the backend by
setting `VITE_API_URL` in the environment or a `.env` file:

```
VITE_API_URL=http://localhost:8000
```

In production the frontend and backend share an origin behind the ALB, so no
env var is needed there.

## Build

```bash
npm run build
```

Outputs a static site in `dist/`.

## Type checking

```bash
npm run typecheck
```

## Project structure

```
src/
  api/              # Typed fetch client + React Query config
  components/
    layout/         # AppShell, Header, Footer
    ui/             # Button, Input, Textarea, Card, StatusIndicator,
                    # EntityListItem, LoadingState, EmptyState
  hooks/            # useAnalyzeText, useAnalyzeScreenshot, useEntityHistory
  lib/              # cn utility
  pages/            # AnalyzePage, UploadPage, ResultPage,
                    # ErrorPage, LookupPage
  styles/           # tokens.css, global.css
  store.ts          # Zustand UI state (view, pending file/text)
  App.tsx           # View router
```

## Screenshot flow

1. User drops a PNG/JPG onto the dropzone.
2. `useAnalyzeScreenshot` requests a presigned PUT URL from
   `/uploads/presigned-url`.
3. The file is uploaded **directly to S3** — image bytes never touch the
   backend.
4. `/analyze/screenshot` is called with the resulting `s3_key`.
5. The result is shown on the verdict page.