# Client

The constituency workspace and news desk. The Nest API lives in `../server`.

```sh
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to http://127.0.0.1:5000.

## Deploy on Vercel

Import this repo. Set the project Root Directory to `client`, or leave it at the repo root (the root `vercel.json` builds this folder).

Set this environment variable, then redeploy. Vite bakes it into the build:

```
VITE_API_BASE_URL=https://YOUR-RAILWAY-DOMAIN
```

No trailing slash. Leave it empty for local dev. Add the same Vercel URL to the API `CORS_ORIGINS`.
