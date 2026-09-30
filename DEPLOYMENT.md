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
    | `EMAIL_ENABLED` | `true`. All automatic alerts arrive by email: one digest per hourly cycle listing the new articles (critical first), an email when the automatic pipeline fails, and the daily report with its PDF. |
    | `NEWS_EMAIL_ENABLED` | Leave empty (on). `false` stops the new-articles digest and keeps the failure email and the daily report. |
    | `EMAIL_PROVIDER` | `resend` |
    | `REPORT_RECIPIENTS` | Comma-separated inboxes for every alert email, such as `desk@example.com,mp@example.com`. No quotes, no brackets. With the sender `onboarding@resend.dev`, Resend only delivers to the email address that owns the Resend account. |
    | `RESEND_API_KEY` | Resend API key |

    WhatsApp and the inbound chatbot:

    | Name | Value |
    | --- | --- |
    | `WHATSAPP_ENABLED` | `true` so the menu and chatbot reply. `false` keeps WhatsApp completely silent. |
    | `WHATSAPP_ALERTS_ENABLED` | Leave empty (off). Automatic alerts (new articles, pipeline failures, pipeline status, the daily summary) then go to email only. `true` also sends them as WhatsApp templates. |
    | `WHATSAPP_ACCESS_TOKEN` | Meta system user or temporary token |
    | `WHATSAPP_PHONE_NUMBER_ID` | Phone number ID from the WhatsApp API setup page, not the display number |
    | `WHATSAPP_RECIPIENTS` | Comma-separated numbers, country code, digits only. These numbers receive news templates and are the only numbers the chatbot will answer. |
    | `WHATSAPP_VERIFY_TOKEN` | A private string you invent. The same string goes in the Meta callback screen. |
    | `WHATSAPP_WEBHOOK_ENABLED` | `true` |
    | `CHATBOT_ENABLED` | `true`. If this variable is omitted, the chatbot still turns on whenever `WHATSAPP_ENABLED` is true. Set `false` to keep alerts and stop chat replies. |
| `CHATBOT_NAME` | Leave empty for `MediaSphere Assistant`, or another display name used in the prompt |
| `CHATBOT_LANGUAGE` | Leave empty to reply in the user's language, or force one such as `English` |
| `CHATBOT_ADDRESSEE` | Leave empty for `Sri. Lavu Sri Krishna Devarayalu Sir`. A bare greeting such as "Hi" gets "Good morning/afternoon/evening, <addressee>! I'm your Media Assistant." followed by "How can I help you with the latest news?", using India time. A question that starts a conversation (after 4 hours of silence) gets the same first line, then the answer. |
    | `CHATBOT_GROQ_MODEL` | Leave empty to use `GROQ_MODEL`, then `openai/gpt-oss-20b` |

    Pipeline alerts on WhatsApp:

| Name | Value |
| --- | --- |
| `WHATSAPP_PIPELINE_STATUS` | Leave empty (off). `true` sends a status message after every hourly cycle, only when `WHATSAPP_ALERTS_ENABLED` is `true`. |
| `PIPELINE_ALERT_REPEAT_HOURS` | `12`. A failed cycle alerts once by email. The same problem is alerted again only after this many hours, or at once when the problem changes. The logs show `[NOTIFY_FAILURE_EMAIL]` and `[NOTIFY_NEWS_EMAIL]` with `sent`, `skipped`, or `failed`. |

An empty `WHATSAPP_RECIPIENTS` list makes the chatbot stay silent. With `WHATSAPP_ALERTS_ENABLED` off, WhatsApp is used only for the menu and chat replies. Chat replies are ordinary session text, which Meta accepts after that person has messaged the business inside the last 24 hours.

    The chatbot facts file is `server/src/chatbot/data/knowledge.json`. Replace that file and redeploy when the answers should change. A missing file does not stop the API. The process logs a warning and answers without those facts.

### Which news is kept

Only news from the seven assembly segments of the Narasaraopet Parliamentary Constituency is fetched and stored: Pedakurapadu, Chilakaluripet, Narasaraopet, Sattenapalle (also spelled Sattenapalli or Sattenpalli), Vinukonda, Gurazala, and Macherla.

Every article must map to one of those seven segments by the segment name, one of its mandals, or a landmark. The article is stored with `assembly_segment` set to that segment. An article that maps to none of them is dropped, and the log shows `[SEGMENT_GATE] dropped`. The district name (Palnadu), "Narasaraopet MP", and names shared with other places (such as Nadendla or Amaravati) do not map an article on their own. The news page and the chatbot show only stored articles that carry a segment.

The places for each segment live in `server/src/pipeline/data/location_dictionary.json`. The API refuses to load that file if it names a segment outside the seven.

| Name | Value |
| --- | --- |
| `SAKSHI_TAG_URLS` | Leave empty. Sakshi is read from the tag page of each segment. A comma-separated list replaces those pages. |

### When YouTube or Sakshi block Railway

YouTube captions and the Sakshi website sometimes refuse cloud server addresses. Railway can hand a new deployment a new outgoing address, so a source that worked can fail after a redeploy. The logs then show `youtube_blocked:…` or `sakshi_http_403`, and the `[YOUTUBE]` line shows the reason per video.

Send only those two sources through a residential or ISP proxy. Node 24 reads the proxy from environment variables, so no code change is needed:

| Name | Value |
| --- | --- |
| `NODE_USE_ENV_PROXY` | `1` |
| `HTTPS_PROXY` | `http://USER:PASSWORD@PROXY-HOST:PORT` from the proxy provider |
| `NO_PROXY` | `api.groq.com,graph.facebook.com,api.resend.com,www.googleapis.com,telugu.getlokalapp.com,localhost` |

`NO_PROXY` keeps Groq, Meta, Resend, the YouTube search API, and Lokal on the direct connection. Neon does not use HTTP, so it never goes through the proxy.

### Visits

Sign in at `/@admin` and choose **Visits**. The page offers two ways to add visits.

**Upload all visits (one file).** One Excel (`.xlsx`), Word (`.docx`), or PDF file with a table of all visits, one row per visit. The page has **Download Excel template** and **Download Word template** buttons (`GET /api/visits/template/xlsx` and `/docx`) with the exact columns: `S.No`, `Date (DD-MM-YYYY)`, `Time (10:30 AM)`, `Place`, `Purpose / Title`, `Details`.
- Headers are matched by meaning, so `Date`/`తేదీ`, `Time`/`సమయం`, `Place`/`Village`/`ప్రదేశం`, `Purpose`/`Subject`/`Title`/`విషయం`, and `Details`/`Description`/`Remarks`/`వివరాలు` all work.
- Dates are read day first, as in 28-09-2026, 28/09/2026, or 28 Sep 2026.
- Time is optional. It accepts 10:30 AM, 2 PM, 14:30, ఉదయం 10:30, Excel time cells, and ranges such as 10 AM - 12:30 PM. A date and time in the Date cell (28-09-2026 10:30 AM) also works.
- A row with no title uses "Visit to <place>".
- Uploads add to the existing visits. A row with the same date, place, and title as a visit already on the site, or as another row in the file, is skipped, so the same file can be uploaded again after adding rows.
- Rows that cannot be read, such as a bad date, are listed with their row number and are not saved.
- Old `.xls` and `.doc` files are refused with a message to save them as `.xlsx` or `.docx`.
- PDF reading works on table PDFs exported from Word or Excel. Scanned PDFs have no text and are refused. Excel and Word are the most reliable.
- Imported visits have no attached file.

**Add a single visit.** A title, optional date, time, place, and details, and an optional PDF, Word (`.doc`, `.docx`), or Excel (`.xls`, `.xlsx`) attachment. The API checks the file contents as well as the extension, so a renamed image is refused.

Attachments are stored in Neon in the `mediasphere.visit_files` table, which the API creates on first use. Each visit is a `jv_records` row with section `visits`. Visits appear on the news page below the news and in the WhatsApp assistant's **Visits** button. When a visit has an attachment, a PDF opens in the browser and Word or Excel files download. Deleting a visit in the admin page removes the row and its file.

`npm test` reads the test PDFs in a separate Node process because `pdfjs-dist` is ESM-only and Jest runs as CommonJS.

| Name | Value |
| --- | --- |
| `VISITS_MAX_UPLOAD_MB` | Leave empty for 10. The admin page also refuses files over 10 MB before uploading. |

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
