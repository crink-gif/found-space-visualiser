"""
Builds true-to-scale 3D models (.glb) of every Found—Space product size from
saunas.json, styled after the product photography:

  Nyssa    - horizontal cedar slats with black reveals, chamfered black corners,
             tinted window + full-height tinted glass door, red-lit interior.
  Nu-A     - pale timber frame, glass front and front corners, glass upper third
             on the sides, slatted lower walls, benches and red heater panels.
  Marrkan  - cedar barrel on twin cradles, black shingle roof, black straps,
             tinted glass door in the round end.
  Yirri    - Cedar: oval staved tub with two steel bands and a steel rim.
             Steel: brushed stainless tub with rounded corners.

Units are metres. Origin = centre of the footprint on the floor. The front of
every product faces +Z. The body matches the dimensions in saunas.json; small
fittings (handles, hinges) may sit a couple of cm proud, like the real thing.

Usage: python3 build_models.py ../saunas.json models
Needs: pip install trimesh pillow numpy
"""
import json, math, os, re, sys
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

RNG = np.random.default_rng(7)


# ---------------------------------------------------------------- textures --
def _smooth_noise(h, w, cells_h, cells_w, seed):
    r = np.random.default_rng(seed).random((cells_h, cells_w))
    img = Image.fromarray((r * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def wood_texture(base, dark, seed, w=512, h=256, staves=0, seam=(0, 0, 0)):
    """Grain runs along U (image x). base/dark are sRGB tuples."""
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    warp = _smooth_noise(h, w, 6, 4, seed) * 0.9 + _smooth_noise(h, w, 24, 12, seed + 1) * 0.15
    rings = np.sin((y * 38 + warp * 2.2) * math.pi * 2)
    lines = np.clip((rings - 0.55) / 0.45, 0, 1) ** 1.5
    fine = _smooth_noise(h, w, h // 2, w // 16, seed + 2)
    tone = _smooth_noise(h, w, 3, 2, seed + 3)
    t = np.clip(0.55 * lines + 0.18 * fine + 0.25 * tone, 0, 1)[..., None]
    b, d = np.array(base, np.float32), np.array(dark, np.float32)
    img = b * (1 - t) + d * t
    if staves:  # board seams across the grain (barrel ends)
        for i in range(1, staves):
            x = int(i * h / staves)
            img[max(0, x - 1):x + 1, :, :] = np.array(seam, np.float32)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def shingle_texture(seed=3, w=512, h=512):
    img = Image.new("RGB", (w, h), (24, 24, 26))
    d = ImageDraw.Draw(img)
    rows, cols = 8, 6
    rh, cw = h / rows, w / cols
    r = np.random.default_rng(seed)
    for row in range(rows + 1):
        off = (row % 2) * cw / 2
        for c in range(-1, cols + 1):
            x0, y0 = c * cw + off, row * rh
            g = int(30 + r.random() * 18)
            pts = [(x0 + 3, y0), (x0 + cw - 3, y0), (x0 + cw - 3, y0 + rh * 0.65),
                   (x0 + cw / 2, y0 + rh * 1.05), (x0 + 3, y0 + rh * 0.65)]
            d.polygon(pts, fill=(g, g, g + 3), outline=(12, 12, 14))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def brushed_texture(w=256, h=256):
    n = _smooth_noise(h, w, h, 6, 11) * 0.5 + _smooth_noise(h, w, h // 2, 3, 12) * 0.5
    v = (200 + (n - 0.5) * 30)[..., None].repeat(3, axis=2)
    return Image.fromarray(np.clip(v, 0, 255).astype(np.uint8))


def lin(rgb):
    return [round(((c / 255) ** 2.2) * 255) for c in rgb]


def mat(name, rgb=(255, 255, 255), alpha=1.0, metal=0.0, rough=0.8, tex=None, emissive=None):
    m = PBRMaterial(
        name=name,
        baseColorFactor=(lin(rgb) if tex is None else [255, 255, 255]) + [int(alpha * 255)],
        baseColorTexture=tex,
        metallicFactor=metal,
        roughnessFactor=rough,
        alphaMode="BLEND" if alpha < 1 else "OPAQUE",
        doubleSided=alpha < 1,
        emissiveFactor=[c / 255 for c in emissive] if emissive else None,
    )
    return m


def make_materials():
    M = {}
    M["cedar"] = mat("cedar", tex=wood_texture((210, 160, 112), (168, 116, 74), 1), rough=0.7)
    M["cedar_in"] = mat("cedar_interior", tex=wood_texture((120, 70, 48), (78, 40, 28), 2), rough=0.8, emissive=(95, 10, 6))
    M["pale"] = mat("pale_timber", tex=wood_texture((226, 196, 152), (196, 160, 112), 3), rough=0.7)
    M["cedar_dark"] = mat("cedar_dark", tex=wood_texture((70, 36, 26), (40, 18, 14), 8), rough=0.85)
    M["barrel"] = mat("barrel_cedar", tex=wood_texture((214, 160, 112), (176, 112, 74), 4), rough=0.75)
    M["barrel_end"] = mat("barrel_end", tex=wood_texture((214, 160, 112), (176, 112, 74), 5,
                                                           staves=14, seam=(120, 78, 50)), rough=0.75)
    M["yirri"] = mat("yirri_cedar", tex=wood_texture((232, 206, 166), (205, 172, 128), 6), rough=0.7)
    M["shingle"] = mat("shingle", tex=shingle_texture(), rough=0.9)
    M["black"] = mat("black_trim", (16, 15, 14), rough=0.6)
    M["reveal"] = mat("reveal", (8, 8, 8), rough=0.95)
    M["tint"] = mat("tinted_glass", (30, 24, 20), alpha=0.42, rough=0.05, metal=0.2)
    M["glass"] = mat("clear_glass", (225, 235, 236), alpha=0.07, rough=0.12)
    M["steel"] = mat("steel", (205, 207, 210), metal=1.0, rough=0.28)
    M["brushed"] = mat("brushed_steel", tex=brushed_texture(), metal=1.0, rough=0.35)
    M["red"] = mat("red_glow", (60, 4, 2), emissive=(255, 22, 12), rough=0.5)
    M["heater"] = mat("heater_panel", (40, 6, 4), emissive=(255, 20, 10), rough=0.4)
    M["water"] = mat("water", (40, 90, 110), alpha=0.75, rough=0.04)
    M["white"] = mat("plaque", (236, 233, 226), rough=0.5)
    return M


# ---------------------------------------------------------------- geometry --
class Builder:
    """Collects boxes per material, each with UVs in metres (grain along the
    chosen axis), then emits one mesh per material."""

    def __init__(self):
        self.parts = {}

    def _add(self, key, v, f, uv):
        p = self.parts.setdefault(key, [[], [], [], 0])
        p[0].append(v); p[1].append(f + p[3]); p[2].append(uv); p[3] += len(v)

    def box(self, key, size, centre, rot_y=0.0, rot_z=0.0, grain=None, uv_scale=1.0):
        ext = np.array(size, dtype=float) / 2
        verts, tris, uvs = [], [], []
        off = RNG.random(2) * 4  # vary grain per piece
        for axis in range(3):
            for sign in (1, -1):
                a, c = [i for i in range(3) if i != axis]
                g = grain if grain is not None and grain != axis else (a if ext[a] >= ext[c] else c)
                u_ax, v_ax = g, (c if g == a else a)
                quad = []
                for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    p = np.zeros(3)
                    p[axis], p[u_ax], p[v_ax] = sign * ext[axis], su * ext[u_ax], sv * ext[v_ax]
                    quad.append(p)
                quad = np.array(quad)
                n = np.zeros(3); n[axis] = sign
                idx = len(verts)
                verts.extend(quad)
                for p in quad:
                    uvs.append((p[u_ax] * uv_scale + off[0], p[v_ax] * 4.0 * uv_scale + off[1]))
                if np.dot(np.cross(quad[1] - quad[0], quad[2] - quad[0]), n) > 0:
                    tris += [(idx, idx + 1, idx + 2), (idx, idx + 2, idx + 3)]
                else:
                    tris += [(idx, idx + 2, idx + 1), (idx, idx + 3, idx + 2)]
        R = (trimesh.transformations.rotation_matrix(rot_y, [0, 1, 0]) @
             trimesh.transformations.rotation_matrix(rot_z, [0, 0, 1]))[:3, :3]
        v = np.array(verts) @ R.T + np.array(centre)
        self._add(key, v, np.array(tris), np.array(uvs))

    def mesh(self, key, m, uv):
        self._add(key, m.vertices.copy(), m.faces.copy(), uv)

    def disc(self, key, radius, centre, thickness, sections=72, uv_size=None):
        """Disc facing +Z with planar UVs (barrel ends: staves run vertically)."""
        m = trimesh.creation.cylinder(radius=radius, height=thickness, sections=sections)
        m.apply_translation(centre)
        s = uv_size or radius * 2
        uv = np.stack([(m.vertices[:, 1] - centre[1]) / s + 0.5,
                       (m.vertices[:, 0] - centre[0]) / s + 0.5], axis=1)
        self.mesh(key, m, uv)

    def path_wall(self, key, pts, height, y0, thickness, closed=True, grain=1, uv_scale=1.0, gap=0.0, stave=0.0):
        """Vertical wall segments following a 2D outline of (x, z) points."""
        n = len(pts)
        for i in range(n if closed else n - 1):
            (x1, z1), (x2, z2) = pts[i], pts[(i + 1) % n]
            L = math.hypot(x2 - x1, z2 - z1)
            if L < 1e-4:
                continue
            ang = math.atan2(-(z2 - z1), x2 - x1)
            if stave and L > stave * 1.5:
                k = int(round(L / stave))
                for j in range(k):
                    f0, f1 = j / k, (j + 1) / k
                    self.box(key, (L / k - gap, height, thickness),
                             (x1 + (x2 - x1) * (f0 + f1) / 2, y0 + height / 2, z1 + (z2 - z1) * (f0 + f1) / 2),
                             rot_y=ang, grain=grain, uv_scale=uv_scale)
                continue
            self.box(key, (max(L - gap, 0.002) + (0 if gap else thickness * 0.5), height, thickness),
                     ((x1 + x2) / 2, y0 + height / 2, (z1 + z2) / 2), rot_y=ang, grain=grain, uv_scale=uv_scale)

    def scene(self, M):
        s = trimesh.Scene()
        for key, (vs, fs, uvs, _) in self.parts.items():
            m = trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False)
            m.visual = TextureVisuals(uv=np.vstack(uvs), material=M[key])
            s.add_geometry(m, geom_name=key)
        return s


def stadium(L, W, n=16, inset=0.0):
    r = W / 2 - inset
    cx = L / 2 - W / 2
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((cx + r * math.cos(a), r * math.sin(a)))
    for i in range(n + 1):
        a = math.pi / 2 + math.pi * i / n
        pts.append((-cx + r * math.cos(a), r * math.sin(a)))
    return pts


def rounded_rect(L, W, r, n=8, inset=0.0):
    hx, hz, r = L / 2 - inset, W / 2 - inset, max(r - inset, 0.005)
    pts = []
    for cx, cz, a0 in ((hx - r, hz - r, 0), (-hx + r, hz - r, 90), (-hx + r, -hz + r, 180), (hx - r, -hz + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


# ---------------------------------------------------------------- products --
def nyssa(W, D, H):
    b = Builder()
    ch, cap, t = 0.06, 0.05, 0.04          # corner chamfer, top/bottom boards, slat depth
    pitch, slat = 0.118, 0.100             # slat rhythm from the photos
    wy0, wy1 = cap, H - cap
    hb, ym = wy1 - wy0, (wy0 + wy1) / 2
    # top and bottom boards with chamfered corners
    for y in (cap / 2, H - cap / 2):
        b.box("cedar", (W - 2 * ch, cap, D), (0, y, 0), grain=0)
        b.box("cedar", (W, cap, D - 2 * ch), (0, y, 0), grain=0)
    # black chamfered corner posts
    for sx in (-1, 1):
        for sz in (-1, 1):
            b.box("black", (ch * 1.41, hb, 0.02), (sx * (W / 2 - ch / 2 - 0.008), ym, sz * (D / 2 - ch / 2 - 0.008)),
                  rot_y=-sx * sz * math.pi / 4)
    # dark backing so the slat reveals read black
    b.box("reveal", (W - 2 * ch, hb, 0.01), (0, ym, -D / 2 + t + 0.005))
    for sx in (-1, 1):
        b.box("reveal", (0.01, hb, D - 2 * ch), (sx * (W / 2 - t - 0.005), ym, 0))

    # front openings, proportioned from the Nyssa IV front photo
    margin, mull = 0.11, 0.11
    door_w = min(0.66, (W - 2 * margin - mull) * 0.48)
    dx0, dx1 = W / 2 - margin - door_w, W / 2 - margin
    wx0, wx1 = -W / 2 + margin, dx0 - mull
    win_y0, win_y1 = 0.40 * H, H - 0.085 * H
    door_y0, door_y1 = 0.06 * H, win_y1
    fz = D / 2 - t / 2

    y = wy0 + (pitch - slat) / 2
    while y + slat <= wy1 + 1e-6:
        yc = y + slat / 2
        if win_y0 - 0.01 < yc < win_y1:
            segs = [(-W / 2 + ch, wx0), (wx1, dx0), (dx1, W / 2 - ch)]
        elif door_y0 < yc < door_y1:
            segs = [(-W / 2 + ch, dx0), (dx1, W / 2 - ch)]
        else:
            segs = [(-W / 2 + ch, W / 2 - ch)]
        gy, gap = y + slat + (pitch - slat) / 2, pitch - slat
        for a, c in segs:
            if c - a > 0.01:
                b.box("cedar", (c - a, slat, t), ((a + c) / 2, yc, fz), grain=0)
                if gy < wy1:
                    b.box("reveal", (c - a, gap, t - 0.008), ((a + c) / 2, gy, fz - 0.004))
        b.box("cedar", (W - 2 * ch, slat, t), (0, yc, -D / 2 + t / 2), grain=0)
        if gy < wy1:
            b.box("reveal", (W - 2 * ch, gap, t - 0.008), (0, gy, -D / 2 + t / 2 + 0.004))
        for sx in (-1, 1):
            b.box("cedar", (t, slat, D - 2 * ch), (sx * (W / 2 - t / 2), yc, 0), grain=2)
            if gy < wy1:
                b.box("reveal", (t - 0.008, gap, D - 2 * ch), (sx * (W / 2 - t / 2 - 0.004), gy, 0))
        y += pitch

    def framed(x0, x1, y0, y1):
        fw = 0.025
        b.box("tint", (x1 - x0, y1 - y0, 0.01), ((x0 + x1) / 2, (y0 + y1) / 2, fz))
        for yy in (y0 + fw / 2, y1 - fw / 2):
            b.box("black", (x1 - x0, fw, t + 0.006), ((x0 + x1) / 2, yy, fz))
        for xx in (x0 + fw / 2, x1 - fw / 2):
            b.box("black", (fw, y1 - y0, t + 0.006), (xx, (y0 + y1) / 2, fz))

    framed(wx0, wx1, win_y0, win_y1)
    framed(dx0, dx1, door_y0, door_y1)
    b.box("black", (0.022, 0.42, 0.025), (dx0 + 0.06, 0.52 * H, D / 2 + 0.008))  # handle
    for hy in (door_y0 + 0.18, door_y1 - 0.18):
        b.box("black", (0.02, 0.09, 0.012), (dx1 - 0.012, hy, D / 2 + 0.003))   # hinges

    # interior: dark cedar lining, slatted backrest grid, bench, red LED cove
    iw, idp = W - 2 * t - 0.04, D - 2 * t - 0.04
    b.box("cedar_in", (iw, hb, 0.01), (0, ym, -D / 2 + t + 0.02))
    for sx in (-1, 1):
        b.box("cedar_in", (0.01, hb, idp), (sx * (W / 2 - t - 0.02), ym, 0))
    b.box("cedar_in", (iw, 0.02, idp), (0, cap + 0.01, 0))
    b.box("cedar_in", (iw, 0.02, idp), (0, H - cap - 0.01, 0))
    zb = -D / 2 + t + 0.05
    cols = max(2, int(iw / 0.28))
    for i in range(cols + 1):
        b.box("cedar_dark", (0.05, 0.95, 0.03), (-iw / 2 + 0.05 + i * (iw - 0.1) / cols, 1.05, zb))
    for yy in np.arange(0.62, 1.52, 0.11):
        b.box("cedar_dark", (iw - 0.04, 0.05, 0.025), (0, yy, zb + 0.03), grain=0)
    bd = min(0.5, idp * 0.42)
    b.box("cedar_dark", (iw, 0.05, bd), (0, 0.47, -D / 2 + t + 0.04 + bd / 2), grain=0)
    b.box("cedar_in", (iw, 0.40, 0.025), (0, 0.25, -D / 2 + t + 0.04 + bd), grain=0)
    ly = H - cap - 0.09
    b.box("red", (iw, 0.025, 0.02), (0, ly, -D / 2 + t + 0.05))
    for sx in (-1, 1):
        b.box("red", (0.02, 0.025, idp), (sx * (W / 2 - t - 0.05), ly, 0))
    b.box("red", (iw, 0.025, 0.02), (0, ly, D / 2 - t - 0.05))
    # brand plaque on the right side
    b.box("white", (0.004, 0.12, 0.12), (W / 2 + 0.002, H * 0.66, -D * 0.18))
    return b


def nua(W, D, H):
    b = Builder()
    post, cap, base, t = 0.06, 0.08, 0.06, 0.04
    wy0, wy1 = base, H - cap
    hb, ym = wy1 - wy0, (wy0 + wy1) / 2
    glass_line = wy1 - 0.34 * H           # upper third of the sides is glass
    front_glass = max(0.26 * D, 0.28)     # glass strip at the front of each side
    b.box("pale", (W, cap, D), (0, H - cap / 2, 0), grain=0)
    b.box("pale", (W, base, D), (0, base / 2, 0), grain=0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            b.box("pale", (post, hb, post), (sx * (W / 2 - post / 2), ym, sz * (D / 2 - post / 2)), grain=1)
    # front: three glass panes (door in the middle) on slim steel seams
    fz = D / 2 - 0.02
    q = (W - 2 * post) / 4
    xs = [-W / 2 + post, -W / 2 + post + q, W / 2 - post - q, W / 2 - post]
    for i in range(3):
        b.box("glass", (xs[i + 1] - xs[i] - 0.01, hb, 0.012), ((xs[i] + xs[i + 1]) / 2, ym, fz))
    for x in xs[1:3]:
        b.box("steel", (0.016, hb, 0.02), (x, ym, fz))
    b.box("steel", (0.02, 0.6, 0.025), (xs[1] + 0.07, 1.0, D / 2 - 0.004))   # door handle
    for x in (-W / 2 + post / 2, xs[1], xs[2], W / 2 - post / 2):          # frame bolts
        for yy in (base / 2, H - cap / 2):
            b.box("steel", (0.03, 0.03, 0.006), (x, yy, D / 2 + 0.002))

    def slats_z(x, z0, z1, y0, y1):
        yy = y0 + 0.004
        while yy + 0.1 <= y1 + 1e-6:
            b.box("pale", (t, 0.1, z1 - z0), (x, yy + 0.05, (z0 + z1) / 2), grain=2)
            yy += 0.118

    for sx in (-1, 1):
        x = sx * (W / 2 - t / 2)
        zf = D / 2 - post - front_glass
        zb0 = -D / 2 + post
        b.box("reveal", (0.008, glass_line - wy0, zf - zb0), (x, (wy0 + glass_line) / 2, (zf + zb0) / 2))
        slats_z(x, zb0, zf, wy0, glass_line)
        b.box("glass", (0.012, hb, front_glass), (x, ym, zf + front_glass / 2))
        b.box("glass", (0.012, wy1 - glass_line, zf - zb0), (x, (glass_line + wy1) / 2, (zf + zb0) / 2))
        b.box("pale", (t + 0.01, hb, 0.04), (x, ym, zf))
    # back wall
    b.box("reveal", (W - 2 * post, hb, 0.008), (0, ym, -D / 2 + t / 2))
    yy = wy0 + 0.004
    while yy + 0.1 <= wy1 + 1e-6:
        b.box("pale", (W - 2 * post, 0.1, t), (0, yy + 0.05, -D / 2 + t / 2), grain=0)
        yy += 0.118
    n = 3 if W > 1.6 else 2
    for i in range(n):
        b.box("heater", (0.12, 0.62, 0.02), ((i - (n - 1) / 2) * 0.28, 1.15, -D / 2 + t + 0.012))
    # interior: floor, benches, under-bench heater, red floor glow, ceiling battens
    b.box("pale", (W - 2 * post, 0.02, D - 2 * post), (0, base + 0.01, 0), grain=0)
    bd = 0.42
    b.box("pale", (W - 2 * post - 0.02, 0.045, bd), (0, 0.48, -D / 2 + t + bd / 2), grain=0)
    for x in (-W / 2 + post + 0.12, W / 2 - post - 0.12):
        b.box("steel", (0.02, 0.42, 0.02), (x, 0.27, -D / 2 + t + bd - 0.05))
    b.box("heater", (W - 2 * post - 0.2, 0.25, 0.02), (0, 0.24, -D / 2 + t + 0.012))
    if D > 1.4:  # Nu-A IV: corner bench along the right side
        b.box("pale", (bd, 0.045, D - 2 * post - bd - 0.3), (W / 2 - post - bd / 2, 0.48, 0.15), grain=2)
    b.box("red", (W - 2 * post - 0.2, 0.006, bd), (0, base + 0.024, -D / 2 + t + bd / 2 + 0.02))
    for z in np.linspace(-D / 2 + 0.15, D / 2 - 0.15, 7):
        b.box("pale", (W - 2 * post, 0.03, 0.06), (0, H - cap - 0.05, z), grain=0)
    b.box("pale", (0.32, 0.26, 0.05), (-W / 2 + post + 0.25, 1.45, -D / 2 + t + 0.03), grain=0)
    return b


def marrkan(W, D, H):
    b = Builder()
    R = min(W, H - 0.12) / 2 - 0.03      # leave room for the roof
    L = D                                 # barrel runs front-to-back
    cy = H - R - 0.03
    st, n = 0.042, 56
    roof_a0, roof_a1 = math.radians(22), math.radians(158)
    w = 2 * math.pi * R / n
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        rz = a - math.pi / 2
        b.box("barrel", (w * 0.985, st, L - 0.08),
              ((R - st / 2) * math.cos(a), cy + (R - st / 2) * math.sin(a), 0), rot_z=rz, grain=2)
        if roof_a0 <= a <= roof_a1:
            b.box("shingle", (w * 1.03, 0.016, L - 0.1),
                  ((R + 0.012) * math.cos(a), cy + (R + 0.012) * math.sin(a), 0), rot_z=rz, grain=2, uv_scale=1.6)
        for z in (L / 2 - 0.02, -L / 2 + 0.02):        # end rims
            b.box("barrel", (w, 0.05, 0.04), ((R - 0.02) * math.cos(a), cy + (R - 0.02) * math.sin(a), z),
                  rot_z=rz, grain=0)
        if not (roof_a0 <= a <= roof_a1):              # black straps (under the roof they're hidden)
            for z in (-L * 0.22, L * 0.22):
                b.box("black", (w, 0.008, 0.035), ((R + 0.004) * math.cos(a), cy + (R + 0.004) * math.sin(a), z),
                      rot_z=rz)
    for z in (L / 2 - 0.06, -L / 2 + 0.06):            # end walls
        b.disc("barrel_end", R - 0.015, (0, cy, z), 0.05, uv_size=2 * R)
    # door: tinted glass in a cedar frame, centred in the front end
    fz = L / 2 - 0.035
    dw, dy0 = 0.62, cy - R + 0.22
    dy1 = min(cy + R - 0.25, dy0 + 1.72)
    b.box("barrel", (dw + 0.12, dy1 - dy0 + 0.12, 0.03), (0, (dy0 + dy1) / 2, fz + 0.005), grain=1)
    b.box("tint", (dw, dy1 - dy0, 0.012), (0, (dy0 + dy1) / 2, fz + 0.022))
    b.box("steel", (0.025, 0.34, 0.03), (-dw / 2 + 0.07, (dy0 + dy1) / 2 + 0.05, fz + 0.045))
    b.box("red", (dw - 0.1, dy1 - dy0 - 0.3, 0.01), (0, (dy0 + dy1) / 2, fz - 0.06))
    # twin cradles + base rails
    for z in (-L * 0.3, L * 0.3):
        cw = R * 1.45
        hgt = cy - R + 0.2
        b.box("barrel", (cw, hgt, 0.09), (0, hgt / 2, z), grain=0)
    for x in (-R * 0.55, R * 0.55):
        b.box("barrel", (0.08, 0.07, L * 0.8), (x, 0.035, 0), grain=2)
    return b


def yirri_cedar(L, Wd, H):
    b = Builder()
    b.path_wall("yirri", stadium(L - 0.035, Wd - 0.035, n=14), H - 0.025, 0.0, 0.035, grain=1, gap=0.003, stave=0.075)
    b.path_wall("reveal", stadium(L, Wd, n=14, inset=0.03), H - 0.04, 0.02, 0.01)
    b.path_wall("steel", stadium(L, Wd, n=14, inset=0.035), H - 0.05, 0.05, 0.006)    # liner
    b.path_wall("steel", stadium(L - 0.04, Wd - 0.04, n=14), 0.025, H - 0.025, 0.04)   # rolled rim
    for y in (0.16, H - 0.17):                                                            # two bands
        b.path_wall("steel", stadium(L, Wd, n=14), 0.045, y - 0.022, 0.005)
    b.box("steel", (L - 0.4, 0.03, Wd - 0.1), (0, 0.04, 0))
    b.box("water", (L - Wd + 0.02, 0.01, Wd - 0.08), (0, H - 0.16, 0))
    for x in (-1, 1):
        m = trimesh.creation.cylinder(radius=Wd / 2 - 0.04, height=0.01, sections=24)
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        m.apply_translation((x * (L / 2 - Wd / 2), H - 0.16, 0))
        b.mesh("water", m, np.zeros((len(m.vertices), 2)))
    b.box("steel", (0.3, 0.07, 0.004), (-L * 0.15, 0.09, Wd / 2 + 0.001))   # plaque
    b.box("black", (0.04, 0.05, 0.012), (0, H * 0.55, Wd / 2 + 0.004))      # drain cap
    return b


def yirri_steel(L, Wd, H):
    b = Builder()
    r = 0.07
    b.path_wall("brushed", rounded_rect(L - 0.025, Wd - 0.025, r), H - 0.03, 0.0, 0.025, grain=1)
    b.path_wall("steel", rounded_rect(L, Wd, r, inset=0.03), H - 0.04, 0.03, 0.006)
    b.path_wall("brushed", rounded_rect(L - 0.012, Wd - 0.012, r), 0.03, H - 0.03, 0.012, grain=1)   # top lip
    b.box("steel", (L - 0.06, 0.03, Wd - 0.06), (0, 0.03, 0))
    b.box("water", (L - 0.08, 0.01, Wd - 0.08), (0, H - 0.16, 0))
    for x in (-0.32, 0.32):
        b.box("black", (0.035, 0.05, 0.008), (x * L, H * 0.6, Wd / 2 - 0.002))
    b.box("reveal", (0.36, 0.022, 0.002), (-L * 0.22, 0.05, Wd / 2 - 0.004))   # wordmark
    return b


# ---------------------------------------------------------------- main --
def parse_dims(s):
    found = dict((k, float(v)) for v, k in re.findall(r"([\d.]+)\s*m\s*([LWDH])", s))
    if "L" in found:
        return found["L"], found["W"], found["H"]
    return found["W"], found["D"], found["H"]


BUILDERS = {"nyssa": nyssa, "nua": nua, "marrkan": marrkan,
            "yirri-cedar": yirri_cedar, "yirri-steel": yirri_steel}


def main(src, out):
    os.makedirs(out, exist_ok=True)
    data = json.load(open(src))
    M = make_materials()
    for p in data["products"]:
        for size in p["sizes"]:
            a, b, h = parse_dims(size["dimensions"])
            scene = BUILDERS[p["id"]](a, b, h).scene(M)
            lo, hi = scene.bounds          # sit on the floor, centred
            T = np.eye(4); T[:3, 3] = [0, -lo[1], 0]
            scene.apply_transform(T)
            fname = f"{p['id']}-{size['id']}.glb"
            path = os.path.join(out, fname)
            scene.export(path)
            ext = np.round(scene.extents, 3)
            print(f"{fname:24s} spec {a:.2f}W {b:.2f}D {h:.2f}H | model {ext[0]}W {ext[2]}D {ext[1]}H | {os.path.getsize(path)//1024}KB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
