# MediaSphere server

NestJS API for constituency news, daily reports, WhatsApp, and the JanaVignanam workspace.

## Layout

```
src/
  main.ts                 process entry
  app.module.ts           module wiring
  admin/                  admin login and manual fetch
  ai/                     Groq analysis
  common/                 shared dates and helpers
  config/                 environment configuration
  database/               Neon document store and repositories
  health/                 /api/health
  news/                   article read API
  notifications/          email and WhatsApp status
  pipeline/               scheduler, lock, and the native fetch cycle
    data/                 Narasaraopet location dictionary
    native/               Lokal, YouTube, and Sakshi cycle
  reports/                daily report email
  sources/                Lokal, Sakshi, and YouTube collectors
  whatsapp/               webhook and outbound messages
  workspace/              JanaVignanam accounts and records
```

The client calls this API through `/api`. Settings live in `.env` (see `.env.example`). The database is Neon (`NEON_DATABASE_URL`). The news cycle runs in this process when `PIPELINE_EXECUTOR=native`.

## Run

```bash
npm install
npm run start:dev
```

Production:

```bash
npm run build
npm run start:prod
```

Default local port is `5000`. In production the process listens on `PORT`.

## Deploy on Railway

Create a service from this repo and set the Root Directory to `server`. The Dockerfile builds the API and Railway checks `GET /api/health`.

Set the variables from `.env.example` in the Railway service. Required:

- `NEON_DATABASE_URL`
- `CORS_ORIGINS` — the Vercel origin, for example `https://your-app.vercel.app`
- `PIPELINE_ON_API=true`
- `PIPELINE_EXECUTOR=native`
- `PIPELINE_CATCHUP_ON_START=false`
- `REPORT_CATCHUP_ON_START=false`

Do not set `PORT`. Railway provides it. Do not set `API_PORT` on Railway.

Copy `GROQ_API_KEY`, `YOUTUBE_API_KEY`, and the email or WhatsApp variables only if those channels should run. A restart does not send them while catch-up is false.

WhatsApp webhooks must target the Railway host, `https://YOUR-RAILWAY-DOMAIN/webhook`, not the Vercel app. That same callback also answers inbound chats from `WHATSAPP_RECIPIENTS` when `CHATBOT_ENABLED=true`. No separate tunnel is required. News alerts stay on templates. The bot does not reply when the recipient list is empty.
