#!/usr/bin/env python3
"""Story-video renderer.

Pakai:  python render.py stories/malam-pertama.json
Hasil:  output/malam-pertama.mp4  (9:16, 576x1024, 30 fps)

Alur: story JSON -> (opsional) tts.py bikin suara + timing kata -> render.py
menggambar tiap frame (latar, karakter, kamera, subtitle kata-per-kata, HUD,
kartu pilihan) lalu ffmpeg menggabungkannya dengan audio.
"""
import argparse, json, math, pathlib, random, shutil, subprocess, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = pathlib.Path(__file__).parent
W, H, FPS = 576, 1024, 30
BW, BH = int(W * 1.4), int(H * 1.2)          # kanvas latar lebih besar dari layar (untuk kamera)
LIME = (200, 240, 37)
INK = (26, 20, 16)
SKIN = (243, 223, 196)


# ----------------------------------------------------------------- util
def font(size, bold=True):
    for p in [ROOT / "assets/fonts/Poppins-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if pathlib.Path(p).exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease(p):
    return p * p * (3 - 2 * p)


def glow_map(cx, cy, r, strength):
    yy, xx = np.mgrid[0:BH, 0:BW].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    return (np.clip(1 - d, 0, 1) ** 2 * strength)[..., None]


# ----------------------------------------------------------------- latar
def gradient(top, bot, h=BH, w=BW):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    a = np.array(top, np.float32) * (1 - t) + np.array(bot, np.float32) * t
    return np.repeat(a, w, axis=1).astype(np.uint8)


def pil(arr):
    return Image.fromarray(arr).convert("RGBA")


def build_room():
    back = pil(gradient((92, 80, 60), (122, 100, 68)))
    d = ImageDraw.Draw(back)
    d.rectangle([0, int(BH * .60), BW, BH], fill=(66, 50, 38, 255))                # lantai
    d.rectangle([0, int(BH * .585), BW, int(BH * .60)], fill=(48, 36, 28, 255))   # plint
    # pintu kayu
    d.rectangle([int(BW * .05), int(BH * .12), int(BW * .21), int(BH * .59)], fill=(104, 58, 30, 255), outline=INK, width=5)
    for k in range(3):
        y = int(BH * (.17 + k * .14))
        d.rectangle([int(BW * .075), y, int(BW * .185), y + int(BH * .10)], outline=(70, 38, 20, 255), width=4)
    # kalender
    cx0, cy0 = int(BW * .30), int(BH * .12)
    d.rectangle([cx0, cy0, cx0 + 110, cy0 + 150], fill=(236, 224, 196, 255), outline=INK, width=4)
    d.rectangle([cx0 + 8, cy0 + 8, cx0 + 102, cy0 + 70], fill=(120, 150, 110, 255))
    d.polygon([(cx0 + 8, cy0 + 70), (cx0 + 40, cy0 + 34), (cx0 + 70, cy0 + 56), (cx0 + 102, cy0 + 28), (cx0 + 102, cy0 + 70)], fill=(176, 96, 58, 255))
    for r in range(4):
        for c in range(6):
            d.rectangle([cx0 + 10 + c * 15, cy0 + 82 + r * 15, cx0 + 18 + c * 15, cy0 + 90 + r * 15], fill=(90, 80, 70, 255))
    # jam dinding
    ccx, ccy = int(BW * .50), int(BH * .10)
    d.ellipse([ccx - 44, ccy - 44, ccx + 44, ccy + 44], fill=(240, 232, 210, 255), outline=INK, width=5)
    d.line([ccx, ccy, ccx + 6, ccy - 28], fill=INK, width=4)
    d.line([ccx, ccy, ccx + 24, ccy + 10], fill=INK, width=4)
    # rak + toples
    d.rectangle([int(BW * .44), int(BH * .27), int(BW * .74), int(BH * .285)], fill=(70, 46, 30, 255), outline=INK, width=3)
    for i, col in enumerate([(190, 60, 50), (210, 205, 190), (150, 150, 140)]):
        x = int(BW * (.47 + i * .09))
        d.rounded_rectangle([x, int(BH * .21), x + 52, int(BH * .27)], 8, fill=col + (255,), outline=INK, width=3)
    # jendela + tirai
    wx0, wy0, wx1, wy1 = int(BW * .79), int(BH * .15), int(BW * .95), int(BH * .50)
    d.rectangle([wx0, wy0, wx1, wy1], fill=(236, 150, 70, 255), outline=INK, width=5)
    d.line([(wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2, wy1], fill=INK, width=4)
    d.rectangle([wx0 - 40, wy0 - 10, wx0 + 18, wy1 + 10], fill=(120, 30, 28, 255), outline=INK, width=4)

    front = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    f = ImageDraw.Draw(front)
    ty = int(BH * .66)
    f.rectangle([0, ty, BW, BH], fill=(176, 84, 26, 255))
    f.rectangle([0, ty, BW, ty + 26], fill=(226, 138, 58, 255))
    f.line([0, ty + 26, BW, ty + 26], fill=(120, 54, 16, 255), width=4)
    # radio
    rx = int(BW * .26)
    f.rounded_rectangle([rx, ty - 78, rx + 150, ty + 8], 8, fill=(140, 52, 36, 255), outline=INK, width=4)
    f.rectangle([rx + 12, ty - 62, rx + 78, ty - 30], fill=(222, 150, 80, 255), outline=INK, width=3)
    f.ellipse([rx + 100, ty - 60, rx + 128, ty - 32], fill=(60, 40, 30, 255))
    # botol air
    bx = int(BW * .50)
    f.rounded_rectangle([bx, ty - 190, bx + 62, ty + 10], 16, fill=(214, 232, 240, 170), outline=(240, 245, 250, 255), width=3)
    f.rectangle([bx + 18, ty - 214, bx + 44, ty - 188], fill=(240, 245, 250, 255))
    f.rounded_rectangle([bx + 4, ty - 90, bx + 58, ty + 6], 10, fill=(120, 170, 210, 200))
    # gelas
    gx = int(BW * .66)
    f.polygon([(gx, ty - 84), (gx + 62, ty - 84), (gx + 54, ty + 8), (gx + 8, ty + 8)], fill=(220, 232, 238, 90), outline=(240, 245, 250, 230))
    # lampu minyak
    lx = int(BW * .80)
    f.polygon([(lx, ty + 6), (lx + 46, ty + 6), (lx + 38, ty - 74), (lx + 8, ty - 74)], fill=(250, 220, 150, 150), outline=(255, 240, 200, 255))
    f.ellipse([lx + 12, ty - 130, lx + 34, ty - 70], fill=(255, 190, 70, 255))
    f.ellipse([lx + 18, ty - 112, lx + 28, ty - 80], fill=(255, 240, 180, 255))

    lamp = (lx + 23, ty - 100)
    g = glow_map(lamp[0], lamp[1], W * 1.1, 1.0)
    return back, front, g, (1.0, .72, .38), (.40, .42, .52)


def build_street():
    arr = gradient((8, 12, 34), (30, 40, 78))
    back = pil(arr)
    d = ImageDraw.Draw(back)
    rnd = random.Random(4)
    for _ in range(40):
        x, y = rnd.randint(0, BW), rnd.randint(0, int(BH * .3))
        d.ellipse([x, y, x + 3, y + 3], fill=(220, 225, 255, 255))
    d.ellipse([int(BW * .72), int(BH * .08), int(BW * .72) + 50, int(BH * .08) + 50], fill=(240, 240, 225, 255))
    # rumah tetangga
    x = -20
    while x < BW:
        w = rnd.randint(150, 230)
        h = rnd.randint(190, 300)
        top = int(BH * .62) - h
        d.rectangle([x, top, x + w, int(BH * .70)], fill=(26, 24, 40, 255), outline=(12, 10, 24, 255), width=3)
        d.polygon([(x - 8, top), (x + w // 2, top - 50), (x + w + 8, top)], fill=(20, 16, 30, 255))
        for k in range(2):
            wx = x + 26 + k * (w // 2 - 6)
            col = (240, 150, 70, 255) if rnd.random() < .6 else (40, 40, 60, 255)
            d.rectangle([wx, top + 50, wx + 36, top + 96], fill=col, outline=(12, 10, 24, 255), width=3)
        x += w + rnd.randint(10, 40)
    d.rectangle([0, int(BH * .70), BW, BH], fill=(24, 22, 30, 255))
    d.rectangle([0, int(BH * .70), BW, int(BH * .715)], fill=(44, 40, 52, 255))
    # pohon kelapa
    px = int(BW * .88)
    d.line([px, int(BH * .70), px + 18, int(BH * .30)], fill=(14, 12, 22, 255), width=10)
    for ang in (200, 235, 270, 305, 340):
        ex = px + 18 + int(110 * math.cos(math.radians(ang)))
        ey = int(BH * .30) + int(60 * math.sin(math.radians(ang))) + 30
        d.line([px + 18, int(BH * .30), ex, ey], fill=(14, 12, 22, 255), width=6)
    front = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    f = ImageDraw.Draw(front)
    # bingkai pintu + jeruji (dilihat dari dalam rumah)
    f.rectangle([int(BW * .17), 0, int(BW * .17) + 46, BH], fill=(60, 26, 22, 255), outline=INK, width=4)
    f.rectangle([int(BW * .83) - 46, 0, int(BW * .83), BH], fill=(60, 26, 22, 255), outline=INK, width=4)
    f.rectangle([int(BW * .17), 0, int(BW * .83), 40], fill=(60, 26, 22, 255), outline=INK, width=4)
    g = glow_map(BW * .5, BH * .45, W * 1.4, .15)
    return back, front, g, (.5, .6, 1.0), (.62, .66, .86)


def build_door():
    back = pil(gradient((84, 72, 52), (112, 92, 62)))
    d = ImageDraw.Draw(back)
    d.rectangle([0, int(BH * .78), BW, BH], fill=(50, 38, 30, 255))
    x0, x1 = int(BW * .28), int(BW * .72)
    d.rectangle([x0 - 22, int(BH * .08), x1 + 22, int(BH * .78)], fill=(52, 30, 18, 255), outline=INK, width=5)
    d.rectangle([x0, int(BH * .11), x1, int(BH * .78)], fill=(120, 66, 34, 255), outline=INK, width=5)
    for k in range(2):
        for j in range(2):
            xa = x0 + 26 + j * ((x1 - x0) // 2 - 6)
            ya = int(BH * (.16 + k * .30))
            d.rectangle([xa, ya, xa + (x1 - x0) // 2 - 58, ya + int(BH * .24)], outline=(80, 44, 22, 255), width=5)
    d.ellipse([x1 - 50, int(BH * .46), x1 - 22, int(BH * .46) + 28], fill=(220, 180, 80, 255), outline=INK, width=3)
    d.rectangle([x0 + 4, int(BH * .775), x1 - 4, int(BH * .785)], fill=(255, 200, 110, 255))   # celah cahaya
    front = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    g = glow_map(BW * .5, int(BH * .78), W * 1.0, .9)
    return back, front, g, (1.0, .72, .4), (.34, .36, .46)


BUILDERS = {"room": build_room, "street": build_street, "door": build_door}
_bg_cache = {}


def get_bg(name):
    if name not in _bg_cache:
        _bg_cache[name] = BUILDERS.get(name, build_room)()
    return _bg_cache[name]


# ----------------------------------------------------------------- karakter
_sprites = {}


def sprite(kind, color, talk, blink):
    key = (kind, color, talk, blink)
    if key in _sprites:
        return _sprites[key]
    ss = 3
    cw, ch = 240, 540
    im = Image.new("RGBA", (cw * ss, ch * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = lambda v: int(v * ss)
    ow = S(4)
    col = rgb(color)
    pants = (42, 37, 33)

    def rr(b, r, fill):
        d.rounded_rectangle([S(b[0]), S(b[1]), S(b[2]), S(b[3])], S(r), fill=fill, outline=INK, width=ow)

    def el(b, fill):
        d.ellipse([S(b[0]), S(b[1]), S(b[2]), S(b[3])], fill=fill, outline=INK, width=ow)

    if kind == "woman":
        d.polygon([(S(64), S(130)), (S(176), S(130)), (S(196), S(520)), (S(44), S(520))], fill=col, outline=INK, width=ow)
        rr((30, 140, 58, 300), 12, col)
        rr((182, 140, 210, 300), 12, col)
        el((36, 290, 62, 316), SKIN)
        el((178, 290, 204, 316), SKIN)
        el((44, 6, 196, 150), col)                 # hijab
        d.polygon([(S(60), S(110)), (S(180), S(110)), (S(196), S(190)), (S(44), S(190))], fill=col)
        el((74, 24, 166, 126), SKIN)
        face_y = 76
    else:
        rr((76, 318, 116, 520), 8, pants)
        rr((124, 318, 164, 520), 8, pants)
        rr((60, 132, 180, 330), 26, col)
        rr((34, 140, 62, 300), 12, col)
        rr((178, 140, 206, 300), 12, col)
        el((36, 290, 62, 316), SKIN)
        el((178, 290, 204, 316), SKIN)
        d.rectangle([S(108), S(112), S(132), S(142)], fill=SKIN, outline=INK, width=ow)
        el((64, 6, 176, 112), (28, 24, 22))        # rambut
        el((68, 22, 172, 126), SKIN)
        face_y = 78
    # wajah
    ey = face_y
    for ex in (101, 139):
        if blink:
            d.line([S(ex - 7), S(ey), S(ex + 7), S(ey)], fill=INK, width=S(3))
        else:
            d.ellipse([S(ex - 5), S(ey - 6), S(ex + 5), S(ey + 6)], fill=INK)
    d.line([S(90), S(ey - 16), S(110), S(ey - 22)], fill=INK, width=S(3))     # alis cemas
    d.line([S(130), S(ey - 22), S(150), S(ey - 16)], fill=INK, width=S(3))
    if talk:
        d.ellipse([S(110), S(ey + 20), S(130), S(ey + 36)], fill=(120, 30, 30), outline=INK, width=S(2))
    else:
        d.arc([S(108), S(ey + 24), S(132), S(ey + 38)], 200, 340, fill=INK, width=S(3))
    out = im.resize((cw, ch), Image.LANCZOS)
    _sprites[key] = out
    return out


def draw_characters(back, chars, t):
    for i, c in enumerate(chars):
        kind = c.get("type", "man")
        sp = sprite(kind, c.get("color", "#6b6a3a"), bool(c.get("_talk")), (int(t * 30) % 110) < 4)
        sc = {"kid": .68}.get(kind, 1.0) * c.get("scale", 1.0)
        if sc != 1.0:
            sp = sp.resize((int(sp.width * sc), int(sp.height * sc)), Image.LANCZOS)
        cx = (BW - W) / 2 + c.get("x", .5) * W
        bob = math.sin(t * 2.2 + i) * 4
        top = BH * (.50 if kind == "kid" else .36) + bob
        if c.get("y") is not None:
            top = BH * c["y"] + bob
        back.alpha_composite(sp, (int(cx - sp.width / 2), int(top)))
        if c.get("tag"):
            f = font(17)
            d = ImageDraw.Draw(back)
            tw = d.textlength(c["tag"], font=f)
            x0, y0 = int(cx - tw / 2 - 12), int(top + 22 * sc)
            d.rounded_rectangle([x0, y0, x0 + tw + 24, y0 + 30], 8, fill=(222, 142, 40, 255), outline=INK, width=3)
            d.text((x0 + 12, y0 + 4), c["tag"], font=f, fill=(255, 245, 225, 255))


# ----------------------------------------------------------------- kamera
def camera(kind, p, t):
    p = ease(min(max(p, 0), 1))
    cx, cy, z = BW / 2, BH * .5, 1.0
    if kind == "zoom_in":
        z = 1.0 + .13 * p
    elif kind == "zoom_out":
        z = 1.13 - .13 * p
    elif kind == "pan_right":
        z, cx = 1.08, BW * (.44 + .12 * p)
    elif kind == "pan_left":
        z, cx = 1.08, BW * (.56 - .12 * p)
    elif kind == "shake":
        z = 1.06
        cx += math.sin(t * 60) * 7 * (1 - p)
        cy += math.cos(t * 53) * 5 * (1 - p)
    return cx, cy, z


def warp(img, cx, cy, z):
    cx = min(max(cx, W / (2 * z)), BW - W / (2 * z))
    cy = min(max(cy, H / (2 * z)), BH - H / (2 * z))
    M = np.float32([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ----------------------------------------------------------------- overlay
_cap_cache = {}


def clean(w):
    return "".join(ch for ch in w if ch not in ",.;:()").upper()


def chunk_words(words, max_chars=15, max_words=3):
    chunks, cur = [], []
    for i, w in enumerate(words):
        txt = clean(w["text"])
        if not txt:
            continue
        if cur and (len(cur) >= max_words or sum(len(clean(words[j]["text"])) + 1 for j in cur) + len(txt) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(i)
    if cur:
        chunks.append(cur)
    return chunks


def caption_layer(words, chunk, active, size=46):
    key = (id(words), tuple(chunk), active)
    if key in _cap_cache:
        return _cap_cache[key]
    f = font(size)
    lay = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    texts = [clean(words[i]["text"]) for i in chunk]
    sp = d.textlength(" ", font=f)
    total = sum(d.textlength(t, font=f) for t in texts) + sp * (len(texts) - 1)
    x = (W - total) / 2
    for i, t in zip(chunk, texts):
        fill = LIME + (255,) if i == active else (255, 255, 255, 255)
        d.text((x, 26), t, font=f, fill=fill, stroke_width=6, stroke_fill=(10, 8, 6, 255))
        x += d.textlength(t, font=f) + sp
    _cap_cache[key] = lay
    return lay


def pill(d, cx, cy, text, col, f, w=380, h=50, a=255):
    d.rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], h // 2, fill=(14, 16, 24, int(190 * a / 255)), outline=col + (a,), width=3)
    tw = d.textlength(text, font=f)
    d.text((cx - tw / 2, cy - h // 2 + 7), text, font=f, fill=(255, 255, 255, a))


def overlay(story, scene, words, chunks, t, T, is_first):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    # HUD (hanya scene pertama)
    if is_first and t < 5:
        a = int(255 * min(1, (5 - t) / .6, t / .3 + .01))
        d.ellipse([30, 62, 38, 70], fill=(230, 50, 40, a))
        d.text((46, 56), story.get("title", "").upper(), font=font(15), fill=(230, 80, 64, a))
        d.text((28, 82), story.get("clock", ""), font=font(36), fill=(245, 245, 245, a))
        d.text((30, 128), f'{story.get("series", "")}   EPISODE {story.get("episode", 1)}'.strip(), font=font(13), fill=(160, 160, 170, a))
    # lencana info
    b = scene.get("badge")
    if b:
        a = int(255 * min(1, t / .35))
        f1, f2 = font(15), font(34)
        d.text((W / 2 - d.textlength(b["label"], font=f1) / 2 - 0, 118 + (1 - a / 255) * 12), b["label"], font=f1, fill=(255, 255, 255, a))
        w1 = d.textlength(b["label"], font=f1)
        d.rounded_rectangle([W / 2 - w1 / 2 - 12, 112, W / 2 + w1 / 2 + 12, 140], 6, outline=(230, 50, 40, a), fill=(200, 40, 34, int(a * .9)), width=2)
        d.text((W / 2 - w1 / 2, 118), b["label"], font=f1, fill=(255, 255, 255, a))
        tw = d.textlength(b["text"], font=f2)
        d.text((W / 2 - tw / 2, 146), b["text"], font=f2, fill=(255, 255, 255, a))
        d.line([W / 2 - tw / 2, 192, W / 2 + tw / 2, 192], fill=(230, 50, 40, a), width=4)
    # kartu pilihan
    ch = scene.get("choices")
    if ch:
        a = int(255 * min(1, max(0, (t - .15) / .4)))
        f1 = font(46)
        q = ch["question"]
        d.text((W / 2 - d.textlength(q, font=f1) / 2, int(H * .27) + (1 - a / 255) * 20), q, font=f1, fill=(255, 255, 255, a), stroke_width=4, stroke_fill=(10, 8, 6, a))
        fp = font(21)
        cols = [(214, 74, 60), (74, 190, 220)]
        for i, o in enumerate(ch["options"][:2]):
            aa = int(255 * min(1, max(0, (t - .4 - i * .2) / .35)))
            pill(d, W // 2, int(H * .365) + i * 62, o, cols[i], fp, a=aa)
        ft = ch.get("footer")
        if ft:
            f3 = font(13)
            aa = int(200 * min(1, max(0, (t - 1.0) / .4)))
            d.text((W / 2 - d.textlength("\u2022 " + ft, font=f3) / 2, int(H * .365) + 2 * 62 - 6), "\u2022 " + ft, font=f3, fill=(160, 170, 185, aa))
    # subtitle kata-per-kata
    for chunk in chunks:
        s, e = words[chunk[0]]["start"], words[chunk[-1]]["end"] + .12
        if s <= t <= e:
            active = chunk[0]
            for i in chunk:
                if words[i]["start"] <= t:
                    active = i
            cl = caption_layer(words, chunk, active)
            k = min(1, (t - s) / .12)
            if k < 1:
                sc = .85 + .15 * ease(k)
                cl = cl.resize((int(W * sc), int(120 * sc)), Image.BILINEAR)
                lay.alpha_composite(cl, ((W - cl.width) // 2, int(H * .60) - cl.height // 2))
            else:
                lay.alpha_composite(cl, (0, int(H * .60) - 60))
            break
    h = story.get("handle")
    if h:
        f = font(14)
        d.text((W / 2 - d.textlength(h, font=f) / 2, H - 38), h, font=f, fill=(255, 255, 255, 110))
    return lay


# ----------------------------------------------------------------- timing
def estimate_words(text):
    words, t = [], .35
    for w in text.split():
        dur = .14 + .055 * len(clean(w))
        words.append({"text": w, "start": t, "end": t + dur})
        t += dur + (.28 if w[-1] in ".?!," else .02)
    return words


def load_timing(buildd, i, text):
    js = buildd / f"scene_{i}.json"
    mp3 = buildd / f"scene_{i}.mp3"
    if js.exists():
        words = json.loads(js.read_text())
        # edge-tts memberikan kata tanpa tanda baca; pakai apa adanya
        return words, (mp3 if mp3.exists() else None)
    return estimate_words(text), None


# ----------------------------------------------------------------- main
def run(path, out=None, hq=False):
    path = pathlib.Path(path)
    story = json.loads(path.read_text())
    name = path.stem
    buildd = ROOT / "build" / name
    buildd.mkdir(parents=True, exist_ok=True)
    scenes = [dict(s) for s in story["scenes"]]
    ch = story.get("choices")
    if ch:
        last = dict(scenes[-1])
        last.update({"narration": ch.get("narration", ""), "choices": ch, "camera": "static", "dim": True})
        last.pop("badge", None)
        last["characters"] = [dict(c) for c in last.get("characters", [])]
        scenes.append(last)

    # timing & durasi
    plan = []
    for i, s in enumerate(scenes):
        words, mp3 = load_timing(buildd, i, s.get("narration", ""))
        end = max([w["end"] for w in words] + [1.0])
        dur = end + (.7 if i < len(scenes) - 1 else 2.2)
        plan.append((s, words, chunk_words(words), mp3, dur))
    total = sum(p[4] for p in plan)

    # audio
    wavs = []
    for i, (s, words, chunks, mp3, dur) in enumerate(plan):
        wav = buildd / f"a{i}.wav"
        if mp3:
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-af", "apad", "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2", str(wav)]
        else:
            cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{dur:.3f}", str(wav)]
        subprocess.run(cmd, check=True)
        wavs.append(wav)
    lst = buildd / "audio.txt"
    lst.write_text("".join(f"file '{w.resolve()}'\n" for w in wavs))
    voice = buildd / "voice.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(voice)], check=True)
    audio = voice
    bgm = ROOT / "assets" / "bgm.mp3"
    if bgm.exists():
        mixed = buildd / "mixed.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(voice), "-stream_loop", "-1", "-i", str(bgm),
                        "-filter_complex", "[1:a]volume=0.12[b];[0:a][b]amix=inputs=2:duration=first:normalize=0",
                        "-t", f"{total:.3f}", str(mixed)], check=True)
        audio = mixed

    outp = pathlib.Path(out) if out else ROOT / "output" / f"{name}.mp4"
    outp.parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", str(audio), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                           "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(outp)], stdin=subprocess.PIPE)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = (1 - .38 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.1)[..., None]
    rng = np.random.default_rng(1)

    for i, (s, words, chunks, mp3, dur) in enumerate(plan):
        back0, front, gmap, gtint, base = get_bg(s.get("bg", "room"))
        n = int(round(dur * FPS))
        chars = [dict(c) for c in s.get("characters", [])]
        for fi in range(n):
            t = fi / FPS
            speaking = any(w["start"] <= t <= w["end"] for w in words)
            for c in chars:
                c["_talk"] = bool(c.get("speaks")) and speaking and (fi // 4) % 2 == 0
            comp = back0.copy()
            draw_characters(comp, chars, t)
            comp.alpha_composite(front)
            a = np.asarray(comp.convert("RGB"), np.float32)
            flick = 1 + .05 * math.sin(t * 9 + i) + .03 * math.sin(t * 23)
            lm = np.array(base, np.float32) + gmap * np.array(gtint, np.float32) * flick
            a = np.clip(a * lm, 0, 255).astype(np.uint8)
            cx, cy, z = camera(s.get("camera", "zoom_in"), t / dur, t)
            fr = warp(a, cx, cy, z)
            if s.get("dim"):
                fr = cv2.GaussianBlur(fr, (0, 0), 5)
                fr = (fr * .42).astype(np.uint8)
            f = fr.astype(np.float32) * vig
            f += rng.normal(0, 3, f.shape[:2])[..., None]
            fade = min(1, t / .2) * (1 if i < len(plan) - 1 else min(1, (dur - t) / .5 + .001))
            f = np.clip(f * fade, 0, 255).astype(np.uint8)
            base_img = Image.fromarray(f).convert("RGBA")
            base_img.alpha_composite(overlay(story, s, words, chunks, t, dur, i == 0))
            ff.stdin.write(np.asarray(base_img.convert("RGB")).tobytes())
        print(f"scene {i + 1}/{len(plan)} ok ({dur:.1f}s)", flush=True)
    ff.stdin.close()
    ff.wait()
    print("selesai:", outp, f"({total:.1f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    run(a.story, a.out)
