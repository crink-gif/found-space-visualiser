"""
Found—Space Visualiser — core rendering logic (Python standard library only).

Takes an uploaded photo of a customer's space + a chosen Found—Space product,
and asks Google's Gemini image model to render the product into the scene.

If GEMINI_API_KEY is not set, it runs in DEMO mode so the whole experience
still works (it returns the product image as a placeholder render).

No third-party packages required.
"""

import os
import re
import json
import time
import base64
import urllib.request
import urllib.error
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = ROOT                       # static files (index.html, saunas/) live at repo root
SAUNA_DIR = os.path.join(PUBLIC, "saunas")

# Gemini "Nano Banana" image model — strong at fusing a product into a scene.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-image")
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

MIME_BY_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


# ---------------------------------------------------------------- catalog
def load_catalog():
    with open(os.path.join(PUBLIC, "saunas.json"), "r") as f:
        return json.load(f).get("products", [])


def find_product(sauna_id):
    for p in load_catalog():
        if p["id"] == sauna_id:
            return p
    return None


def find_size(product, size_id):
    sizes = product.get("sizes", []) if product else []
    for s in sizes:
        if s["id"] == size_id:
            return s
    return sizes[0] if sizes else None     # sensible default


# ---------------------------------------------------------------- helpers
def parse_data_url(data_url):
    """Return (mime, raw_bytes) from a 'data:image/...;base64,...' string."""
    m = re.match(r"data:(?P<mime>[^;]+);base64,(?P<data>.+)$", data_url, re.DOTALL)
    if not m:
        raise ValueError("Image must be a base64 data URL.")
    return m.group("mime"), base64.b64decode(m.group("data"))


def to_data_url(mime, raw_bytes):
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw_bytes).decode("ascii"))


def read_product_image(product, size=None):
    """
    Read the reference image file and return (mime, bytes). Prefers the chosen
    size's own image (e.g. Nua II vs Nua IV) so the AI renders the exact variant;
    falls back to the product-level image.
    """
    rel = ((size or {}).get("image") or product["image"]).lstrip("/")
    path = os.path.join(PUBLIC, rel)
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        return MIME_BY_EXT.get(ext, "image/jpeg"), f.read()


def build_prompt(product, size):
    persons = size.get("persons") if size else None
    dims = (size.get("dimensions") if size else "") or ""
    spec = "%s (%s)" % (product["name"], product["type"].lower())
    bits = []
    if persons:
        bits.append("seats %s" % persons)
    if dims:
        bits.append("has a real-world external size of approximately %s" % dims)
    scale_line = ""
    if bits:
        scale_line = (
            "- This variant %s. Render it at the correct true-to-scale size relative to the space, "
            "so the customer can judge how it fits.\n" % (" and ".join(bits))
        )
    return (
        "You are a photorealistic architectural visualiser for a premium wellness brand.\n"
        "IMAGE 1 is a real, front-on photo of a customer's space.\n"
        "IMAGE 2 is the EXACT Found—Space %s to place — treat it as the absolute ground truth "
        "for the product's appearance.\n\n"
        "Composite the product from IMAGE 2 into IMAGE 1 as if it were professionally installed there.\n\n"
        "PRODUCT FIDELITY (most important):\n"
        "- Reproduce the product EXACTLY as it appears in IMAGE 2: identical silhouette, proportions, "
        "timber grain and colour, the exact glass door and panelling, the slat/board count and spacing, "
        "the frame, hinges and hardware. This is the same physical product — do not redesign, restyle, "
        "simplify, stretch, add or remove any detail.\n"
        "- Use only the product itself from IMAGE 2; ignore IMAGE 2's own background and lighting.\n"
        "%s"
        "SCENE INTEGRATION:\n"
        "- Estimate the room's true scale from real-world references visible in IMAGE 1 — doorways (~2.04m "
        "tall), internal doors, power points/light switches (~115mm), skirting boards (~90mm), standard "
        "floorboard widths, benches and steps — and size the product against them so it sits believably "
        "true-to-scale, neither toy-sized nor oversized.\n"
        "- Match IMAGE 1's perspective, eye level, ground plane, scale and colour temperature; relight the "
        "product to suit IMAGE 1 and add realistic contact shadows and reflections.\n"
        "- Keep everything else in IMAGE 1 unchanged, and keep IMAGE 1's exact framing and aspect ratio.\n"
        "- Output one single, sharp, high-resolution, photorealistic photograph. No text or labels.\n"
        "Return only the image." % (spec, scale_line)
    )


# ---------------------------------------------------------------- Gemini
def call_gemini(api_key, scene_mime, scene_bytes, prod_mime, prod_bytes, prompt):
    url = "%s/%s:generateContent?key=%s" % (API_BASE, MODEL, api_key)
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": scene_mime, "data": base64.b64encode(scene_bytes).decode("ascii")}},
                {"inline_data": {"mime_type": prod_mime, "data": base64.b64encode(prod_bytes).decode("ascii")}},
            ],
        }],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    data = json.dumps(body).encode("utf-8")

    # Retry briefly on transient "busy" responses (429 rate limit, 5xx) so a
    # momentary limit doesn't surface as an error to the customer. Rate-limit
    # responses come back fast, so the backoff waits are the only added time.
    attempts = 3
    payload = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            transient = e.code == 429 or 500 <= e.code < 600
            if transient and i < attempts - 1:
                wait = 1.5 * (i + 1)
                print("[VISUALISE] gemini %s — retrying in %.1fs (%d/%d)" % (e.code, wait, i + 1, attempts - 1))
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if i < attempts - 1:
                print("[VISUALISE] gemini network error — retrying:", e)
                time.sleep(1.5 * (i + 1))
                continue
            raise

    for cand in payload.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return to_data_url(mime, base64.b64decode(inline["data"]))
    raise RuntimeError("The AI did not return an image. Please try a different photo.")


# ---------------------------------------------------------------- entry point
def render(image_data_url, sauna_id, size_id=None):
    """
    Main entry. Returns {"image": <data url>, "mode": "ai"|"demo"}.
    Raises ValueError for bad input, RuntimeError for render problems.
    """
    product = find_product(sauna_id)
    if not product:
        raise ValueError("Unknown product selected.")
    size = find_size(product, size_id)

    scene_mime, scene_bytes = parse_data_url(image_data_url)
    if not scene_mime.startswith("image/"):
        raise ValueError("Uploaded file must be an image.")

    prod_mime, prod_bytes = read_product_image(product, size)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        # DEMO mode — no key configured. Return the product image so the
        # full flow is testable; the UI labels this as a demo preview.
        return {"image": to_data_url(prod_mime, prod_bytes), "mode": "demo"}

    image = call_gemini(api_key, scene_mime, scene_bytes, prod_mime, prod_bytes, build_prompt(product, size))
    bbox = detect_bbox(api_key, image)        # for the on-image dimension lines
    return {"image": image, "mode": "ai", "bbox": bbox}


# ---------------------------------------------------------------- bbox detection
DETECT_MODEL = os.environ.get("GEMINI_DETECT_MODEL", "gemini-2.5-flash")


def detect_bbox(api_key, image_data_url):
    """
    Ask a vision model for the placed product's bounding box so the front-end can
    draw dimension lines that hug it. Returns [x0, y0, x1, y1] normalised 0..1,
    or None on any failure (front-end then falls back to a caption strip).
    """
    try:
        mime, raw = parse_data_url(image_data_url)
    except Exception:
        return None

    prompt = (
        "Find the sauna or ice bath (the wooden cabin, barrel, or tub) in this image. "
        "Respond with ONLY compact JSON: {\"box_2d\":[ymin,xmin,ymax,xmax]} using integers "
        "0-1000 normalised to the image size. No other text."
    )
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode("ascii")}},
            ],
        }],
    }
    url = "%s/%s:generateContent?key=%s" % (API_BASE, DETECT_MODEL, api_key)
    try:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = "".join(
            p.get("text", "")
            for c in payload.get("candidates", [])
            for p in c.get("content", {}).get("parts", [])
        )
        m = re.search(r"\[\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\]", text)
        if not m:
            return None
        ymin, xmin, ymax, xmax = [int(v) for v in re.findall(r"\d+", m.group(0))]
        box = [xmin / 1000.0, ymin / 1000.0, xmax / 1000.0, ymax / 1000.0]
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        return box
    except Exception as e:
        print("[VISUALISE] bbox detect failed:", repr(e))
        return None


# Custom HubSpot contact property that holds the model + size the customer
# visualised. Created once in the portal (see README). Override via env if needed.
HUBSPOT_INTEREST_PROP = os.environ.get("HUBSPOT_INTEREST_PROP", "visualiser_interest")


def push_to_hubspot(token, record):
    """
    Create or update a HubSpot contact (upsert by email — no duplicates).
    Uses the stable v1 createOrUpdate endpoint with a Private App token.
    Writes the chosen model + size into a custom property; if that property
    doesn't exist yet, it retries with only the standard fields so a lead is
    never lost.
    """
    email = record.get("email", "").strip()
    if not email:
        return
    interest = " · ".join([p for p in [record.get("product"), record.get("size")] if p])
    if record.get("hasRender"):
        interest += " · rendered in the Visualiser"

    base_props = [
        {"property": "email", "value": email},
        {"property": "firstname", "value": record.get("firstName", "")},
        {"property": "lastname", "value": record.get("lastName", "")},
        {"property": "phone", "value": record.get("phone", "")},
        {"property": "zip", "value": record.get("postcode", "")},
        {"property": "hs_lead_status", "value": "NEW"},
    ]
    url = "https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/%s/" % urllib.parse.quote(email)

    def _send(props):
        req = urllib.request.Request(
            url, data=json.dumps({"properties": props}).encode("utf-8"),
            headers={"Authorization": "Bearer %s" % token, "Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=20).read()

    try:
        _send(base_props + [{"property": HUBSPOT_INTEREST_PROP, "value": interest}])
        print("[LEAD] hubspot: contact upserted with interest")
    except urllib.error.HTTPError as e:
        # Most likely the custom property doesn't exist yet. Try to create it
        # once (needs crm.schemas.contacts.write), then retry with it; if that
        # still fails, fall back to standard fields so the lead is never lost.
        print("[LEAD] hubspot: interest write failed (%s) — creating property" % e.code)
        created = ensure_interest_property(token)
        try:
            if created:
                _send(base_props + [{"property": HUBSPOT_INTEREST_PROP, "value": interest}])
                print("[LEAD] hubspot: contact upserted with interest (property created)")
            else:
                _send(base_props)
                print("[LEAD] hubspot: contact upserted (standard fields only)")
        except Exception as e2:
            print("[LEAD] hubspot failed:", repr(e2))
    except Exception as e:
        print("[LEAD] hubspot failed:", repr(e))


def ensure_interest_property(token):
    """
    Best-effort create of the custom contact property used to store the chosen
    model + size. Returns True if it now exists (created or already present).
    Needs the crm.schemas.contacts.write scope on the Private App; if missing,
    returns False and the caller falls back to standard fields only.
    """
    definition = {
        "name": HUBSPOT_INTEREST_PROP,
        "label": "Visualiser interest",
        "type": "string",
        "fieldType": "text",
        "groupName": "contactinformation",
        "description": "Model + size the contact rendered in the Found—Space Visualiser.",
    }
    req = urllib.request.Request(
        "https://api.hubapi.com/crm/v3/properties/contacts",
        data=json.dumps(definition).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=20).read()
        return True
    except urllib.error.HTTPError as e:
        if e.code == 409:        # already exists
            return True
        print("[LEAD] hubspot: could not create property (%s) — check scopes" % e.code)
        return False
    except Exception as e:
        print("[LEAD] hubspot: property create error:", repr(e))
        return False


def save_lead(lead):
    """
    Send a captured lead to HubSpot (if HUBSPOT_TOKEN is set) and/or a generic
    LEAD_WEBHOOK_URL. Always logs to the server console as a fallback. The full
    render data URL is never forwarded — only a flag noting one was produced.
    """
    product = find_product(lead.get("saunaId")) or {}
    size = find_size(product, lead.get("sizeId")) or {}
    record = {
        "firstName": lead.get("firstName", ""),
        "lastName": lead.get("lastName", ""),
        "email": lead.get("email", ""),
        "phone": lead.get("phone", ""),
        "postcode": lead.get("postcode", ""),
        "product": product.get("name", lead.get("saunaId", "")),
        "size": size.get("label", lead.get("sizeId", "")),
        "hasRender": bool(lead.get("render")),
        "source": "Found—Space Visualiser",
    }
    print("[LEAD]", json.dumps(record))

    token = os.environ.get("HUBSPOT_TOKEN", "").strip()
    if token:
        push_to_hubspot(token, record)

    url = os.environ.get("LEAD_WEBHOOK_URL", "").strip()
    if url:
        try:
            req = urllib.request.Request(
                url, data=json.dumps(record).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            print("[LEAD] webhook failed:", e)
    return {"ok": True}


def gemini_error_message(exc):
    """Turn a Gemini HTTPError into a human-friendly message + log detail."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        if exc.code in (401, 403):
            return "The AI key is missing or invalid. Check GEMINI_API_KEY."
        if exc.code == 429:
            return "The AI service is busy right now — please try again in a moment."
        return "AI render failed (%s). %s" % (exc.code, detail)[:200]
    return "Could not reach the AI service. Please try again."
