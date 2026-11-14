# View in your room (AR)

IKEA-style AR for the Found—Space range. Customer opens the page on their phone,
taps **View in your room**, and a true-scale 3D model is placed on their floor
(iPhone: Apple AR Quick Look; Android: Google Scene Viewer). On a computer it shows
a 3D model they can spin, plus a QR code to hand off to their phone.

Deep link a specific product: `/ar/?model=nyssa&size=4`

## Files
| File | What it does |
|---|---|
| `index.html` | The page (reads `../saunas.json` for products + sizes) |
| `models/<model>-<size>.glb` | One 3D model per size, built from `saunas.json` dimensions |
| `build_models.py` | Rebuilds every model from `saunas.json` (`pip install trimesh`, then `python3 build_models.py ../saunas.json models`) |
| `model-viewer.min.js`, `qrcode.js` | Google's model-viewer 4.4.0 and a QR generator, bundled so nothing depends on a CDN |

## Important
- **AR only works on the live HTTPS site**, not on localhost. Android's Scene Viewer
  downloads the model from your public URL, so it must be deployed.
- The current models are **correct size, simplified look**. To upgrade, replace a
  `.glb` with a proper model of the same file name, origin at floor centre, front
  facing +Z, units in metres.
- `model-viewer.min.js` has a one-line patch: a null check in `onUpdateScene` so
  turning the model (Rotate 90°) outside AR doesn't throw an error in 4.4.0.
