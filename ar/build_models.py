"""
Builds true-to-scale 3D models (.glb) of every Found—Space product size
straight from saunas.json. Units are metres, origin = centre of the footprint
on the floor, front of the product faces the viewer (+Z).

These are dimensionally accurate placeholder models: right size, simplified
look. Swap any file in ar/models/ for a proper model (same file name) later.

Usage: python3 build_models.py path/to/saunas.json out_dir
"""
import json, re, sys, os
import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

def mat(name, rgb, alpha=1.0, metal=0.0, rough=0.8):
    return PBRMaterial(
        name=name,
        baseColorFactor=[round(((c / 255) ** 2.2) * 255) for c in rgb] + [int(alpha * 255)],  # sRGB -> linear
        metallicFactor=metal,
        roughnessFactor=rough,
        alphaMode="BLEND" if alpha < 1 else "OPAQUE",
        doubleSided=alpha < 1,
    )

CEDAR = mat("cedar", (176, 112, 66), rough=0.75)
CEDAR_IN = mat("cedar_interior", (214, 160, 108), rough=0.8)
CEDAR_DARK = mat("cedar_dark", (92, 58, 36), rough=0.7)
ROOF = mat("roof", (38, 34, 31), rough=0.6)
GLASS = mat("glass", (190, 215, 220), alpha=0.28, rough=0.05)
METAL = mat("handle", (30, 30, 30), metal=0.9, rough=0.3)
STEEL = mat("steel", (196, 198, 200), metal=0.95, rough=0.32)
WATER = mat("water", (70, 140, 170), alpha=0.7, rough=0.05)


def box(scene, name, size, centre, material):
    m = trimesh.creation.box(extents=size)
    m.apply_translation(centre)
    m.visual = TextureVisuals(material=material)
    scene.add_geometry(m, geom_name=name)


def parse_dims(s):
    # "1.44m W × 1.30m D × 1.99m H"  or  "tub 1.35m L × 0.65m W × 0.75m H"
    found = dict((k, float(v)) for v, k in re.findall(r"([\d.]+)\s*m\s*([LWDH])", s))
    if "L" in found:  # plunge: L is the long side (width across), W is depth
        return found["L"], found["W"], found["H"]
    return found["W"], found["D"], found["H"]


def sauna(W, D, H):
    s = trimesh.Scene()
    t, base, roof = 0.045, 0.06, 0.08
    wall_h = H - base - roof
    wy = base + wall_h / 2
    box(s, "plinth", (W, base, D), (0, base / 2, 0), CEDAR_DARK)
    box(s, "roof", (W, roof, D), (0, H - roof / 2, 0), ROOF)
    box(s, "back", (W, wall_h, t), (0, wy, -D / 2 + t / 2), CEDAR)
    box(s, "left", (t, wall_h, D - t), (-W / 2 + t / 2, wy, t / 2 - t / 2), CEDAR)
    box(s, "right", (t, wall_h, D - t), (W / 2 - t / 2, wy, 0), CEDAR)
    # interior lining so it looks warm through the glass
    box(s, "back_in", (W - 2 * t, wall_h, 0.01), (0, wy, -D / 2 + t + 0.005), CEDAR_IN)
    box(s, "floor_in", (W - 2 * t, 0.01, D - 2 * t), (0, base + 0.005, 0), CEDAR_IN)
    # front: corner posts, glass, door mullion and handle
    post = 0.07
    fz = D / 2 - t / 2
    box(s, "post_l", (post, wall_h, t), (-W / 2 + post / 2, wy, fz), CEDAR)
    box(s, "post_r", (post, wall_h, t), (W / 2 - post / 2, wy, fz), CEDAR)
    box(s, "glass", (W - 2 * post, wall_h, 0.012), (0, wy, fz), GLASS)
    door_w = min(0.62, (W - 2 * post) * 0.5)
    mx = W / 2 - post - door_w
    box(s, "mullion", (0.04, wall_h, t + 0.004), (mx, wy, fz), CEDAR)
    box(s, "handle", (0.025, 0.45, 0.03), (mx + 0.08, base + 1.0, fz + t / 2 + 0.02), METAL)
    # benches: main bench along the back, backrest slats
    bench_d = min(0.48, D * 0.4)
    inner_w = W - 2 * t
    box(s, "bench", (inner_w, 0.045, bench_d), (0, 0.48, -D / 2 + t + bench_d / 2), CEDAR_IN)
    box(s, "bench_front", (inner_w, 0.42, 0.02), (0, 0.27, -D / 2 + t + bench_d - 0.01), CEDAR_IN)
    for i, y in enumerate((0.70, 0.86, 1.02)):
        box(s, f"slat_{i}", (inner_w, 0.06, 0.025), (0, y, -D / 2 + t + 0.025), CEDAR_DARK)
    return s


def plunge(L, Wd, H, material):
    s = trimesh.Scene()
    t = 0.05
    y = H / 2
    box(s, "tub_floor", (L, 0.06, Wd), (0, 0.03, 0), material)
    box(s, "tub_front", (L, H, t), (0, y, Wd / 2 - t / 2), material)
    box(s, "tub_back", (L, H, t), (0, y, -Wd / 2 + t / 2), material)
    box(s, "tub_left", (t, H, Wd - 2 * t), (-L / 2 + t / 2, y, 0), material)
    box(s, "tub_right", (t, H, Wd - 2 * t), (L / 2 - t / 2, y, 0), material)
    box(s, "water", (L - 2 * t, 0.01, Wd - 2 * t), (0, H - 0.12, 0), WATER)
    return s


def main(src, out):
    os.makedirs(out, exist_ok=True)
    data = json.load(open(src))
    built = []
    for p in data["products"]:
        for size in p["sizes"]:
            a, b, h = parse_dims(size["dimensions"])
            if p["type"] == "Cold Plunge":
                scene = plunge(a, b, h, STEEL if "steel" in p["id"] else CEDAR)
            else:
                scene = sauna(a, b, h)
            fname = f"{p['id']}-{size['id']}.glb"
            scene.export(os.path.join(out, fname))
            ext = scene.extents
            built.append((fname, a, b, h, tuple(round(x, 3) for x in ext)))
    for b in built:
        print(b)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
