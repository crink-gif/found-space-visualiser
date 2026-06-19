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
import base64
import urllib.request
import urllib.error

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


def read_product_image(product):
    """Read the product's image file from /public and return (mime, bytes)."""
    rel = product["image"].lstrip("/")           # e.g. "saunas/marrkan.png"
    path = os.path.join(PUBLIC, rel)
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        return MIME_BY_EXT.get(ext, "image/jpeg"), f.read()


def build_prompt(product, size):
    size_label = size["label"] if size else ""
    persons = size.get("persons") if size else None
    dims = size.get("dimensions") if size else ""
    spec = "the %s %s (%s)" % (product["name"], size_label, product["type"].lower())
    scale_line = ""
    if persons or dims:
        scale_line = (
            "- This is the %s-person size, real-world footprint approximately %s. Render it at the "
            "correct true-to-scale size relative to the space, so the customer can judge how it fits.\n"
            % (persons, dims)
        )
    return (
        "You are a photorealistic architectural visualiser for a premium wellness brand.\n"
        "IMAGE 1 is a real, front-on photo of a customer's space (backyard, deck, courtyard or room).\n"
        "IMAGE 2 is %s product.\n\n"
        "Task: place the product from IMAGE 2 naturally into the scene of IMAGE 1, as if it were "
        "really installed there. Requirements:\n"
        "- Keep the product's exact design, materials (cedar timber), proportions and colour faithful to IMAGE 2.\n"
        "%s"
        "- Match the perspective, ground plane, scale, shadows and lighting/colour temperature of IMAGE 1 precisely.\n"
        "- Position it on a sensible, level surface with realistic contact shadows and reflections.\n"
        "- Do NOT change, distort or restyle the rest of the customer's space. Keep it photorealistic.\n"
        "- Output a single edited photograph of IMAGE 1 with the product convincingly added.\n"
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
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

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

    prod_mime, prod_bytes = read_product_image(product)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        # DEMO mode — no key configured. Return the product image so the
        # full flow is testable; the UI labels this as a demo preview.
        return {"image": to_data_url(prod_mime, prod_bytes), "mode": "demo"}

    image = call_gemini(api_key, scene_mime, scene_bytes, prod_mime, prod_bytes, build_prompt(product, size))
    return {"image": image, "mode": "ai"}


def save_lead(lead):
    """
    Forward a captured lead to LEAD_WEBHOOK_URL if configured (Zapier / Make /
    Slack incoming webhook / Google Apps Script all accept JSON POST).
    Always logs to the server console as a fallback. The full-res render data
    URL is dropped from the webhook payload to keep it small; a flag notes it.
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
