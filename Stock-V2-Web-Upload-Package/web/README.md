# Stock V2.0 Web

Vue 3 + Vite browser application for the Stock V2.0 migration.

## Local development

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173` in Chrome or Edge.

## Production build

```bash
npm run build
npm run preview
```

The output is `web/dist/`. Cloudflare Pages should use `web` as the project root, `npm run build` as the build command, and `dist` as the output directory.

## Privacy and runtime

- PDF files are transferred only to the browser's dedicated Web Worker and Pyodide virtual filesystem.
- The Worker runs the Python PDF import and three-statement parsing modules copied from the Windows application.
- Original PDFs are deleted from the in-memory Pyodide filesystem after the import/parse stage.
- No PDF, financial data, manual correction, or analysis result is sent to a server.
- No project persistence, history, or PDF archive is implemented.
- Service Worker caches static site assets and the version-pinned Pyodide runtime. It does not cache user documents or analysis results.

## Current migration boundary

This is the first formal development increment. It establishes the five-page UI, multi-PDF workflow, browser-local Python runtime, original three-statement parser integration, data confirmation, and rule-engine result rendering.

The original requirement's non-financial annual-report extraction and the full supplemental indicator coverage still require migration/implementation. The UI reports this boundary explicitly; it does not fabricate results. The original requirement's Excel/PDF export is excluded by the user's latest decision.

## License gate

PyMuPDF is distributed under AGPL v3 or a commercial licensing path. Public deployment must not proceed until the project has a documented compliant license route or a validated alternative PDF engine. Local development integration does not remove this requirement.
