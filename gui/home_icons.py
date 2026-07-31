"""Mit Pillow gezeichnete Icons für den Startbildschirm.

Pillow ist über customtkinter (CTkImage) bereits vorhanden -> kein externes
Bildmaterial nötig. Jede Zeichenfunktion liefert ein RGBA-Image; ctk_icon()
verpackt es für die GUI.
"""

import math

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Icons liegen auf dem Lila-Verlauf der Startkacheln -> nahezu weiße Formen mit
# kräftig-lila Aussparungen für guten Kontrast.
_ACCENT = (245, 242, 255, 255)   # nahezu weiß
_LIGHT = (98, 42, 178, 255)      # kräftiges Lila (Detail-Aussparungen)


def _canvas(size: int):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    """Lineare Farbinterpolation zwischen zwei RGB-Tupeln."""
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_image(width: int, height: int, radius: int,
                   top: tuple, bottom: tuple) -> Image.Image:
    """Vertikaler Farbverlauf (top->bottom) mit abgerundeten Ecken (RGBA)."""
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    denom = max(height - 1, 1)
    for y in range(height):
        draw.line([(0, y), (width, y)], fill=_lerp(top, bottom, y / denom))
    img = base.convert("RGBA")
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, width - 1, height - 1],
                                           radius=radius, fill=255)
    img.putalpha(mask)
    return img


def ctk_gradient(width: int, height: int, radius: int,
                 top: tuple, bottom: tuple) -> ctk.CTkImage:
    img = gradient_image(width, height, radius, top, bottom)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))


# ---------------------------------------------------------------------------
# Komplette Kachel als ein Bild (Panel + Rand + Icon + Text)
#
# Wird als EINE Grafik gerendert, damit kein überlagertes "transparentes"
# Text-Label die dunkle Fensterfarbe durchscheinen lässt (schwarzer Kasten).
# Gerendert wird in doppelter Auflösung (Supersampling) für scharfen Text.
# ---------------------------------------------------------------------------

_SS = 2  # Supersampling-Faktor

# Panel-Verlauf (dunkles, edles Lila) - normal und beim Ueberfahren etwas heller.
_PANEL_TOP = (74, 52, 138)
_PANEL_BOTTOM = (40, 24, 74)
_PANEL_TOP_HOVER = (94, 68, 168)
_PANEL_BOTTOM_HOVER = (54, 34, 96)
_BORDER = (140, 104, 220, 220)
_BORDER_HOVER = (180, 146, 255, 255)
_TITLE_COLOR = (245, 242, 255, 255)
_SUBTITLE_COLOR = (190, 176, 224, 255)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Lädt eine System-Schrift (Segoe UI, sonst Arial); Fallback Default."""
    candidates = ([r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
                  if bold else
                  [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"])
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(text: str, font, max_width: float) -> list[str]:
    """Bricht Text an Wortgrenzen so um, dass jede Zeile in max_width passt."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and font.getlength(trial) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _draw_centered_block(draw, lines, font, cx: float, top_y: float,
                         fill, gap: int) -> float:
    """Zeichnet zentrierte Textzeilen ab top_y; liefert das untere y zurück."""
    ascent, descent = font.getmetrics()
    y = top_y
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text((cx - w / 2, y), line, font=font, fill=fill)
        y += ascent + descent + gap
    return y


def card_image(width: int, height: int, kind: str, title: str, subtitle: str,
               *, hover: bool = False) -> Image.Image:
    """Rendert eine komplette Startkachel (dunkles Lila-Panel mit Leucht-Rand,
    hellem Icon, weißem Titel, gedämpftem Untertitel) als ein RGBA-Bild."""
    ss = _SS
    w, h = width * ss, height * ss
    radius = round(0.11 * height) * ss

    top = _PANEL_TOP_HOVER if hover else _PANEL_TOP
    bottom = _PANEL_BOTTOM_HOVER if hover else _PANEL_BOTTOM
    img = gradient_image(w, h, radius, top, bottom)
    draw = ImageDraw.Draw(img)

    # Dezenter Leucht-Rand.
    border = _BORDER_HOVER if hover else _BORDER
    draw.rounded_rectangle([ss, ss, w - 1 - ss, h - 1 - ss],
                           radius=radius, outline=border, width=max(2, ss))

    # Icon zentriert im oberen Drittel.
    icon_px = round(0.30 * height) * ss
    icon = draw_icon(kind, icon_px)
    img.alpha_composite(icon, (round(w / 2 - icon_px / 2), round(0.10 * h)))

    # Titel + Untertitel (echte Schrift), zentriert.
    cx = w / 2
    max_text = w - 24 * ss
    title_font = _load_font(round(0.12 * height) * ss, bold=True)
    sub_font = _load_font(round(0.072 * height) * ss, bold=False)

    y = _draw_centered_block(draw, _wrap(title, title_font, max_text),
                             title_font, cx, round(0.46 * h), _TITLE_COLOR, 2 * ss)
    _draw_centered_block(draw, _wrap(subtitle, sub_font, max_text),
                         sub_font, cx, y + 2 * ss, _SUBTITLE_COLOR, 1 * ss)
    return img


def ctk_card(width: int, height: int, kind: str, title: str, subtitle: str,
             *, hover: bool = False) -> ctk.CTkImage:
    img = card_image(width, height, kind, title, subtitle, hover=hover)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))


# ---------------------------------------------------------------------------
# Kreativer Lila-Hintergrund für den Startbildschirm
# ---------------------------------------------------------------------------

# Weiche Leucht-"Blobs": (x-Anteil, y-Anteil, Radius-Anteil, RGBA).
_GLOW_BLOBS = (
    (0.16, 0.20, 0.34, (150, 70, 230, 95)),    # Violett oben links
    (0.86, 0.30, 0.32, (200, 60, 165, 85)),    # Magenta oben rechts
    (0.72, 0.90, 0.38, (96, 62, 224, 80)),     # Blau-Violett unten
    (0.30, 0.82, 0.30, (168, 58, 210, 70)),    # Purpur unten links
)
_BG_INNER = (60, 36, 104)   # helleres Lila (Zentrum)
_BG_OUTER = (16, 9, 30)     # sehr dunkles Lila (Ränder)


def _radial_gradient(width: int, height: int, inner: tuple, outer: tuple,
                     cx_frac: float, cy_frac: float) -> Image.Image:
    """Radialer Verlauf inner->outer. Wird klein berechnet und hochskaliert
    (schnell und trotzdem weich)."""
    sw = max(2, width // 4)
    sh = max(2, height // 4)
    small = Image.new("RGB", (sw, sh))
    px = small.load()
    cx, cy = sw * cx_frac, sh * cy_frac
    maxd = math.hypot(max(cx, sw - cx), max(cy, sh - cy)) or 1.0
    for y in range(sh):
        for x in range(sw):
            t = min(1.0, math.hypot(x - cx, y - cy) / maxd)
            px[x, y] = _lerp(inner, outer, t)
    return small.resize((width, height), Image.BICUBIC)


def home_background(width: int, height: int, title: str = "") -> Image.Image:
    """Rendert den Startbildschirm-Hintergrund: dunkler Lila-Radialverlauf mit
    weichen, leuchtenden Farb-Blobs (Violett/Magenta) und optionalem Titel."""
    width = max(width, 2)
    height = max(height, 2)
    out = _radial_gradient(width, height, _BG_INNER, _BG_OUTER, 0.5, 0.28).convert("RGBA")

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    reach = max(width, height)
    for fx, fy, fr, color in _GLOW_BLOBS:
        r = fr * reach
        cx, cy = fx * width, fy * height
        gdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=reach * 0.07))
    out.alpha_composite(glow)

    if title:
        draw = ImageDraw.Draw(out)
        font = _load_font(max(16, round(height * 0.05)), bold=True)
        tw = draw.textlength(title, font=font)
        draw.text(((width - tw) / 2, height * 0.06), title,
                  font=font, fill=(240, 235, 255, 255))
    return out.convert("RGB")


def _save(size: int) -> Image.Image:
    img, d = _canvas(size)
    m = size * 0.14
    d.rounded_rectangle([m, m, size - m, size - m], radius=size * 0.10, fill=_ACCENT)
    d.rectangle([size * 0.34, m, size * 0.66, size * 0.34], fill=_LIGHT)          # Schieber
    d.rectangle([size * 0.54, size * 0.16, size * 0.62, size * 0.30], fill=_ACCENT)
    d.rounded_rectangle([size * 0.30, size * 0.52, size * 0.70, size - m * 1.2],  # Etikett
                        radius=size * 0.04, fill=_LIGHT)
    return img


def _restore(size: int) -> Image.Image:
    img, d = _canvas(size)
    m = size * 0.18
    d.arc([m, m, size - m, size - m], start=70, end=360, fill=_ACCENT, width=int(size * 0.11))
    d.polygon([(size * 0.50, size * 0.06), (size * 0.50, size * 0.30),
               (size * 0.72, size * 0.18)], fill=_ACCENT)                          # Pfeilspitze
    return img


def _reinstall(size: int) -> Image.Image:
    img, d = _canvas(size)
    d.rectangle([size * 0.44, size * 0.16, size * 0.56, size * 0.50], fill=_ACCENT)
    d.polygon([(size * 0.32, size * 0.46), (size * 0.68, size * 0.46),
               (size * 0.50, size * 0.70)], fill=_ACCENT)                          # Download-Pfeil
    d.rounded_rectangle([size * 0.22, size * 0.74, size * 0.78, size * 0.86],
                        radius=size * 0.03, fill=_LIGHT)                           # Ablage
    return img


def _remove(size: int) -> Image.Image:
    img, d = _canvas(size)
    # Mülltonne: Deckel + Griff + Körper + Rillen
    d.rectangle([size * 0.42, size * 0.14, size * 0.58, size * 0.22], fill=_ACCENT)   # Griff
    d.rounded_rectangle([size * 0.22, size * 0.22, size * 0.78, size * 0.30],
                        radius=size * 0.02, fill=_ACCENT)                              # Deckel
    d.rounded_rectangle([size * 0.30, size * 0.32, size * 0.70, size * 0.84],
                        radius=size * 0.05, fill=_ACCENT)                              # Körper
    for x in (0.40, 0.50, 0.60):
        d.rectangle([size * x, size * 0.40, size * (x + 0.03), size * 0.76], fill=_LIGHT)
    return img


_DRAWERS = {"save": _save, "restore": _restore, "reinstall": _reinstall, "remove": _remove}


def draw_icon(kind: str, size: int = 64) -> Image.Image:
    try:
        return _DRAWERS[kind](size)
    except KeyError:
        raise ValueError(f"Unbekanntes Icon: {kind!r}")


def ctk_icon(kind: str, size: int = 64) -> ctk.CTkImage:
    img = draw_icon(kind, size)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
