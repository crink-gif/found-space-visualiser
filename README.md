# Found—Space Visualiser

A simple, evergreen web tool you can send to clients. They **upload a front-on
photo of their space**, **choose a Found—Space model and size**, and the app
**renders it true-to-scale into their photo with AI** — then captures their
details so your team can follow up with a quote.

- **AI engine:** Google Gemini image model ("Nano Banana"), great at placing a real
  product into a real scene. ~a few cents per render.
- **Demo mode:** with no API key, the full experience still works (shows a demo
  preview). Add the key and it switches to live AI automatically.
- **No build tools.** Static front-end + tiny Python functions (standard library only).

---

## 1. Preview it on your Mac right now (no installs)

```bash
cd "/Users/zacpovolny/Desktop/OS/foundspace-visualiser"
python3 server.py
```

Open **http://localhost:8000**. This runs in **demo mode**.

To preview the *real* AI render locally, get a free key (step 2) and run:

```bash
GEMINI_API_KEY=your_key_here python3 server.py
```

---

## 2. Get your free AI key (2 minutes)

1. Go to **https://aistudio.google.com/app/apikey**
2. Sign in with a Google account → **Create API key**
3. Copy it. That's your `GEMINI_API_KEY`.

---

## 3. Put it online (a real link for clients)

Hosting on **Vercel** is free, fast (no cold-start delay when a client opens the
link), and keeps your API key secret on the server. It deploys with **zero
config** — no command line needed.

**A. Get the code onto GitHub (no terminal)**

1. Create free accounts at **github.com** and **vercel.com**.
2. On GitHub: **New repository** → name it `found-space-visualiser` → **Create**.
3. On the new repo page, click **uploading an existing file**, then drag in the
   entire contents of this `foundspace-visualiser` folder (including the `api`
   and `saunas` folders). Click **Commit changes**.

**B. Deploy on Vercel**

4. On Vercel: **Add New → Project → Import** the `found-space-visualiser` repo.
5. Expand **Environment Variables** and add:
   - `GEMINI_API_KEY` = your key from step 2  *(required for live AI)*
   - `HUBSPOT_TOKEN` = your HubSpot Private App token *(for leads — see below)*
   - *(optional)* `LEAD_WEBHOOK_URL` = a Zapier/Make/Slack/Sheets webhook
6. Click **Deploy**. You'll get a link like `found-space-visualiser.vercel.app`.
7. *(optional)* Add a custom domain like `visualise.foundspace.au` in
   Vercel → Settings → Domains.

That link is what you send to clients. To change anything later, edit the files
on GitHub and Vercel redeploys automatically.

---

## Leads → HubSpot

When a client submits their details, the app creates/updates a **HubSpot contact**
(deduped by email) with their name, email, phone, postcode, lead status = New, and
the **model + size they visualised** (in a "Visualiser interest" property).

### Set it up (one-time, ~3 minutes)

1. In HubSpot: **Settings → Integrations → Private Apps → Create a private app**.
2. Name it "Found—Space Visualiser". Under **Scopes**, tick:
   - `crm.objects.contacts.write`
   - `crm.schemas.contacts.write`  *(lets the app auto-create the "Visualiser interest" property — no manual property setup)*
3. **Create app** → copy the **access token** (starts with `pat-`).
4. In Vercel → your project → **Settings → Environment Variables**, add
   `HUBSPOT_TOKEN` = that token. Redeploy.

That's it. The custom property is created automatically on the first lead. If you
only grant the contacts scope (not schemas), leads still flow — they just won't
include the model/size property.

### Want leads elsewhere too?

Set `LEAD_WEBHOOK_URL` to any Zapier / Make / Slack / Google Sheets webhook and
each lead is also POSTed there as JSON. Leads are always logged in the Vercel
function logs as a backstop. The render image itself is never forwarded.

---

## Changing the products & sizes

Edit `saunas.json`. Each model has a `sizes` array (e.g. 2/3/4-person) with a
`dimensions` value — **these dimensions drive how big the AI renders it, so set
them to the real Found—Space specs.** Drop matching images into `saunas/`. The
grid, the size picker, and the AI all use this file automatically. A model with a
single size auto-selects it.

## Files

| File | What it does |
|------|--------------|
| `index.html`, `app.js` | The client-facing page |
| `saunas.json`, `saunas/` | Your product catalogue + images |
| `visualiser_core.py` | The AI render + lead logic |
| `api/visualise.py`, `api/lead.py` | Serverless endpoints (Vercel) |
| `server.py` | Local preview server |
