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

Hosting on **Vercel** is free and keeps your API key secret on the server.

1. Create accounts at **github.com** and **vercel.com** (free).
2. Put this folder on GitHub (Zac — I can run these git steps for you).
3. In Vercel: **Add New → Project → Import** your GitHub repo.
4. Before deploying, open **Environment Variables** and add:
   - `GEMINI_API_KEY` = your key from step 2
   - *(optional)* `LEAD_WEBHOOK_URL` = a Zapier/Make/Slack/Sheets webhook to receive leads
5. Click **Deploy**. You'll get a link like `found-space-visualiser.vercel.app`.
6. *(optional)* Add a custom domain like `visualise.foundspace.au` in Vercel → Domains.

That link is what you send to clients.

---

## Where do the leads go?

When a client submits their details, the lead (name, email, phone, postcode,
chosen model) is:

- **logged** in the Vercel function logs, and
- **POSTed** to `LEAD_WEBHOOK_URL` if you set one.

Easiest setup: make a **Zapier** or **Make** webhook that drops each lead into a
Google Sheet or emails you at zac@koud.co, and paste its URL as `LEAD_WEBHOOK_URL`.

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
