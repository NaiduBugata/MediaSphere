    # Deploy JanaVignanam

    The site is two services from one GitHub repo:

    | Piece | Host | What it runs |
    | --- | --- | --- |
    | News site | Vercel | The Vite app in `client/` |
    | API, news cycle, reports, WhatsApp | Railway | The Nest app in `server/` |

    Connect both hosts to `https://github.com/NaiduBugata/janavignanam`, branch `main`.

    Deploy Railway first. Vercel needs the Railway URL at build time, and Meta needs that same URL for WhatsApp.

    Do not commit `server/.env` or `client/.env`. Copy values into each host's variable screen. Railway and Vercel never read the local `.env` files.

    ## 1. Railway API

    ### Create the service

    1. In Railway, create a project and choose **Deploy from GitHub repo**.
    2. Select `NaiduBugata/janavignanam`.
    3. Open the service **Settings**.
    4. Set **Root Directory** to `server`. This is required. The Dockerfile copies `package.json` from that folder. A repo-root service will fail the build.
    5. Leave the builder on the Dockerfile. `server/railway.toml` already sets the builder, the health check `GET /api/health`, a 60 second timeout, and a restart after a failed deploy (3 tries).
    6. Leave **Watch Paths** empty so a push to `main` redeploys this service.

    Do not set `PORT` or `API_PORT`. Railway injects `PORT`, and the API listens on that value. `EXPOSE 5000` in the Dockerfile is only documentation.

    ### Variables

    Open the service **Variables** and add the names below. Use the values from your local `server/.env`. Paste each secret once into Railway. Do not put them in git, in the deployment logs, or in this file.

    Required for the site and the news cycle:

    | Name | Value |
    | --- | --- |
    | `NEON_DATABASE_URL` | Neon connection string for database `neondb` |
    | `MONGODB_COLLECTION` | `articles` |
    | `CORS_ORIGINS` | The exact Vercel origin, for example `https://your-app.vercel.app`. No trailing slash. Add a custom domain as a second origin, separated by a comma. |
    | `CORS_ALLOW_VERCEL_PREVIEWS` | `true` |
    | `ADMIN_USERNAME` | Admin sign-in name |
    | `ADMIN_PASSWORD` | Admin sign-in password |
    | `ADMIN_SESSION_SECRET` | A long random string, separate from the password |
    | `PIPELINE_ON_API` | `true` |
    | `PIPELINE_EXECUTOR` | `native` |
    | `PIPELINE_CATCHUP_ON_START` | `false` |
    | `PIPELINE_INTERVAL_HOURS` | `1` |
    | `PIPELINE_LOCK_TTL_SECONDS` | `2700` |
    | `PIPELINE_ADMIN_TOKEN` | A long random string used to start a cycle by hand |
    | `REPORT_ENABLED` | `true` |
    | `REPORT_SCHEDULER_ON_API` | `true` |
    | `REPORT_CATCHUP_ON_START` | `false` |
    | `REPORT_TIMEZONE` | `Asia/Kolkata` |
    | `REPORT_HOUR` | `7` |
    | `REPORT_MINUTE` | `0` |

    `PIPELINE_CATCHUP_ON_START=false` and `REPORT_CATCHUP_ON_START=false` keep a restart from fetching news and from sending email or WhatsApp. Production already defaults catch-up to off. Set both variables anyway so a later change of `NODE_ENV` cannot turn them on.

    Skip `MONGODB_URI`. The API stores articles in Neon. The health JSON field is still named `mongo`. `true` means Neon answered.

    Channels, only if that channel should run:

    | Name | When to set it |
    | --- | --- |
    | `GROQ_API_KEY_1` … or `GROQ_API_KEYS` | News analysis and the WhatsApp chatbot. The API reads numbered keys first, then `GROQ_API_KEYS`, then `GROQ_API_KEY`. |
    | `YOUTUBE_ENABLED` | `true` or `false` |
    | `YOUTUBE_API_KEY` | YouTube collection |
    | `SAKSHI_ENABLED` | `true` or `false` |
    | `EMAIL_ENABLED` | `true` only when daily report mail should send |
    | `EMAIL_PROVIDER` | `resend` |
    | `REPORT_RECIPIENTS` | Comma-separated report inboxes |
    | `RESEND_API_KEY` | Resend API key |

    WhatsApp and the inbound chatbot:

    | Name | Value |
    | --- | --- |
    | `WHATSAPP_ENABLED` | `true` when alerts and replies should run. `false` keeps both silent. |
    | `WHATSAPP_ACCESS_TOKEN` | Meta system user or temporary token |
    | `WHATSAPP_PHONE_NUMBER_ID` | Phone number ID from the WhatsApp API setup page, not the display number |
    | `WHATSAPP_RECIPIENTS` | Comma-separated numbers, country code, digits only. These numbers receive news templates and are the only numbers the chatbot will answer. |
    | `WHATSAPP_VERIFY_TOKEN` | A private string you invent. The same string goes in the Meta callback screen. |
    | `WHATSAPP_WEBHOOK_ENABLED` | `true` |
    | `CHATBOT_ENABLED` | `true`. If this variable is omitted, the chatbot still turns on whenever `WHATSAPP_ENABLED` is true. Set `false` to keep alerts and stop chat replies. |
| `CHATBOT_NAME` | Leave empty for `MediaSphere Assistant`, or another display name used in the prompt |
| `CHATBOT_LANGUAGE` | Leave empty to reply in the user's language, or force one such as `English` |
| `CHATBOT_ADDRESSEE` | Leave empty for `Sri Lavu Sri Krishna Devarayalu Sir`. The first reply of each conversation (after 4 hours of silence) starts with "Good morning/afternoon/evening, <addressee>! I'm your Media Assistant." using India time. |
    | `CHATBOT_GROQ_MODEL` | Leave empty to use `GROQ_MODEL`, then `openai/gpt-oss-20b` |

    An empty `WHATSAPP_RECIPIENTS` list makes the chatbot stay silent. News alerts stay on WhatsApp templates. Chat replies are ordinary session text, which Meta accepts after that person has messaged the business inside the last 24 hours.

    The chatbot facts file is `server/src/chatbot/data/knowledge.json`. Replace that file and redeploy when the answers should change. A missing file does not stop the API. The process logs a warning and answers without those facts.

    ### Public URL

    1. Open the service **Settings**, then **Networking**.
    2. Choose **Generate Domain**. Railway gives you a host such as `mediasphere-api.up.railway.app`.
    3. Wait until the deployment is **Success** and the health check is green.

    Confirm, in this order:

    1. `https://YOUR-RAILWAY-DOMAIN/api/health` returns HTTP 200 and `"mongo": true`. HTTP 200 with `"mongo": false` means the process is up and Neon is not.
    2. `https://YOUR-RAILWAY-DOMAIN/api/database/health` returns HTTP 200 and `"ok": true`. This route returns HTTP 500 when Neon is down.
    3. `https://YOUR-RAILWAY-DOMAIN/api/news` returns articles.

    If the health check fails, open the deploy logs. The usual causes are Root Directory left at the repo root, a missing `NEON_DATABASE_URL`, or `PORT` / `API_PORT` set to a fixed number.

    ## 2. Vercel site

    1. In Vercel, **Add New Project** and import `NaiduBugata/janavignanam`.
2. Leave the Root Directory as the repository root. Do not set it to `client`. The root `vercel.json` installs and builds inside `client/`, publishes `client/dist`, and rewrites every path to `index.html` so client-side routes work.
3. In Project Settings, clear any custom Install Command or Build Command so Vercel uses `vercel.json`. A command of `npm ci --prefix client` fails on Vercel even though `client/package-lock.json` is in the repo.
    4. Add one environment variable, then deploy:

    | Name | Value |
    | --- | --- |
    | `VITE_API_BASE_URL` | `https://YOUR-RAILWAY-DOMAIN` |

    No trailing slash. Do not append `/api`. Vite reads this while it builds, so changing it later does nothing until you redeploy Vercel.

    5. After the first Vercel deploy, copy the real site origin, such as `https://janavignanam.vercel.app`.
    6. Set Railway `CORS_ORIGINS` to that exact origin and redeploy the API if the first Railway deploy used a placeholder.

    Open the Vercel URL, go to `/news`, and confirm stories load. If the page is blank of stories, the browser network tab will show the Railway host. A CORS error means `CORS_ORIGINS` does not match the address in the browser bar, including `https` and any `www`.

    ## 3. WhatsApp callback

Meta must call Railway. The Vercel domain does not receive WhatsApp events. No tunnel is required once the Railway domain exists.

All Meta and WhatsApp traffic runs on the **NeuralTrix AI** app (id `1010944024633533`). `WHATSAPP_ACCESS_TOKEN` is a system user token for that app, and it is the only app that should be subscribed to the WhatsApp Business account. The account-level callback was set through the Graph API with `POST /{WABA_ID}/subscribed_apps` and `override_callback_uri`, so it points at Railway even if the app dashboard shows another URL.

1. In Meta for Developers, open **NeuralTrix AI**, then **WhatsApp**, then **Configuration**.
    2. Set the callback URL to `https://YOUR-RAILWAY-DOMAIN/webhook`.
    3. Set the verify token to the same value as Railway `WHATSAPP_VERIFY_TOKEN`.
    4. Save. Meta sends `GET /webhook`. Railway returns the challenge only when the token matches. A 403 means the two token values differ. A 503 means `WHATSAPP_WEBHOOK_ENABLED` is off.
    5. Subscribe the webhook field **messages**.

    ### See whether a reply is delivered

    1. From a phone whose number is in `WHATSAPP_RECIPIENTS`, send a text to the business WhatsApp number.
    2. In the Railway logs, look for `WhatsApp message/text` and then `Chatbot replied to`.
    3. The phone should receive a text reply within a few seconds.

    What the logs mean:

    | Log line | Meaning |
    | --- | --- |
    | `Chatbot replied to` | Meta accepted the session text. |
    | `Chatbot reply was not delivered` followed by `Graph API error` | Meta refused the send. Error **131047** means the 24-hour customer-care window is closed, so a free-text reply is not allowed until that person messages the business again. |
    | `Ignored chatbot message from` | The sender is not in `WHATSAPP_RECIPIENTS`. |
    | `Chatbot replies are off because WHATSAPP_RECIPIENTS is empty` | The allowlist is missing. |
    | No `WhatsApp message/text` line after you send a chat | Meta is not calling this URL. Recheck the callback URL, the verify token, and that **messages** is subscribed. |

    News alerts do not use this reply path. They stay on templates.

    ## 4. After the next code change

    1. Commit and push `main` to `https://github.com/NaiduBugata/janavignanam`.
    2. Railway redeploys from the `server` directory. Vercel redeploys the client when client files change.
    3. Redeploy Vercel yourself after any change to `VITE_API_BASE_URL`.
    4. Leave both catch-up variables `false` unless you intend a restart to fetch news and send notifications.

    ## Checklist

    - Railway Root Directory is `server`.
    - `PORT` and `API_PORT` are unset on Railway.
    - `NEON_DATABASE_URL` is set, and `/api/database/health` returns `"ok": true`.
    - Both catch-up variables are `false`.
    - `CORS_ORIGINS` is the exact Vercel origin.
    - `VITE_API_BASE_URL` is the Railway origin, with no trailing slash, and Vercel was redeployed after it was set.
    - `/news` on the Vercel URL shows articles.
    - Meta callback is `https://YOUR-RAILWAY-DOMAIN/webhook`, verify token matches, and **messages** is subscribed.
    - A text from an allowlisted phone produces `Chatbot replied to` in the Railway logs.
