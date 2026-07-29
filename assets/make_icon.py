"""Erzeugt das Umzugstool-Programmicon (assets/icon.ico) + eine PNG-Vorschau.

Reproduzierbar und Git-freundlich: das Icon wird per Pillow gezeichnet, nicht
als Binaerblob "von Hand" abgelegt. Aenderungen einfach hier vornehmen und
neu ausfuehren:

    python assets/make_icon.py

Motiv: blaues App-Badge (Farbverlauf) mit einem weissen Browser-Fenster
(Ampel-Punkte + Seiteninhalt) und einem gruenen "Backup"-Badge mit
Download-Pfeil unten rechts.
"""

from pathlib import Path

from PIL import Image, ImageDraw

S = 1024  # Supersampling-Aufloesung (wird am Ende auf 256 herunterskaliert)

HERE = Path(__file__).resolve().parent
ICO_PATH = HERE / "icon.ico"
PNG_PATH = HERE / "icon_preview.png"


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # --- Badge-Hintergrund mit vertikalem Blau-Verlauf ---
    top, bottom = (59, 130, 246), (26, 54, 120)
    grad = Image.new("RGB", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        gd.line([(0, y), (S, y)], fill=_lerp(top, bottom, y / (S - 1)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.23), fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)

    # --- Browser-Fenster (weiss) ---
    wx0, wy0, wx1, wy1 = int(S * 0.19), int(S * 0.23), int(S * 0.81), int(S * 0.70)
    rad = int(S * 0.045)
    d.rounded_rectangle([wx0, wy0, wx1, wy1], radius=rad, fill=(255, 255, 255, 255))

    # Kopfleiste
    hb = int(S * 0.11)
    d.rounded_rectangle([wx0, wy0, wx1, wy0 + hb], radius=rad, fill=(224, 231, 239, 255))
    d.rectangle([wx0, wy0 + hb - rad, wx1, wy0 + hb], fill=(224, 231, 239, 255))

    # Ampel-Punkte
    cy = wy0 + hb // 2
    dotr = int(S * 0.014)
    dot_colors = [(239, 68, 68), (245, 158, 11), (34, 197, 94)]
    for k, dx in enumerate((0.045, 0.088, 0.131)):
        cx = wx0 + int(S * dx)
        d.ellipse([cx - dotr, cy - dotr, cx + dotr, cy + dotr], fill=dot_colors[k] + (255,))

    # Seiteninhalt (Zeilen)
    lx0, lx1 = wx0 + int(S * 0.05), wx1 - int(S * 0.05)
    ly = wy0 + hb + int(S * 0.055)
    lh = int(S * 0.030)
    gap = int(S * 0.058)
    for frac in (1.0, 0.82, 0.92, 0.6):
        d.rounded_rectangle([lx0, ly, lx0 + int((lx1 - lx0) * frac), ly + lh],
                            radius=lh // 2, fill=(203, 213, 225, 255))
        ly += gap

    # --- Gruenes Backup-Badge (Download-Pfeil) unten rechts ---
    bcx, bcy, br = int(S * 0.75), int(S * 0.72), int(S * 0.155)
    ring = int(S * 0.022)
    d.ellipse([bcx - br - ring, bcy - br - ring, bcx + br + ring, bcy + br + ring],
              fill=(255, 255, 255, 255))
    d.ellipse([bcx - br, bcy - br, bcx + br, bcy + br], fill=(34, 197, 94, 255))

    # Download-Pfeil (Stiel + Spitze) in Weiss
    sw = int(br * 0.28)
    d.rectangle([bcx - sw // 2, bcy - int(br * 0.52), bcx + sw // 2, bcy + int(br * 0.10)],
                fill=(255, 255, 255, 255))
    d.polygon([(bcx - int(br * 0.5), bcy - int(br * 0.08)),
               (bcx + int(br * 0.5), bcy - int(br * 0.08)),
               (bcx, bcy + int(br * 0.52))], fill=(255, 255, 255, 255))

    return img


def main() -> None:
    master = build().resize((256, 256), Image.LANCZOS)
    master.save(ICO_PATH, format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    master.save(PNG_PATH)
    print(f"Icon geschrieben: {ICO_PATH}")
    print(f"Vorschau:         {PNG_PATH}")


if __name__ == "__main__":
    main()
