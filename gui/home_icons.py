"""Mit Pillow gezeichnete Icons fuer den Startbildschirm.

Pillow ist ueber customtkinter (CTkImage) bereits vorhanden -> kein externes
Bildmaterial noetig. Jede Zeichenfunktion liefert ein RGBA-Image; ctk_icon()
verpackt es fuer die GUI.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

# Icons liegen auf dem Lila-Verlauf der Startkacheln -> nahezu weisse Formen mit
# kraeftig-lila Aussparungen fuer guten Kontrast.
_ACCENT = (245, 242, 255, 255)   # nahezu weiss
_LIGHT = (98, 42, 178, 255)      # kraeftiges Lila (Detail-Aussparungen)


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
# Wird als EINE Grafik gerendert, damit kein ueberlagertes "transparentes"
# Text-Label die dunkle Fensterfarbe durchscheinen laesst (schwarzer Kasten).
# Gerendert wird in doppelter Aufloesung (Supersampling) fuer scharfen Text.
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
    """Laedt eine System-Schrift (Segoe UI, sonst Arial); Fallback Default."""
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
    """Zeichnet zentrierte Textzeilen ab top_y; liefert das untere y zurueck."""
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
    hellem Icon, weissem Titel, gedaempftem Untertitel) als ein RGBA-Bild."""
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
    # Muelltonne: Deckel + Griff + Koerper + Rillen
    d.rectangle([size * 0.42, size * 0.14, size * 0.58, size * 0.22], fill=_ACCENT)   # Griff
    d.rounded_rectangle([size * 0.22, size * 0.22, size * 0.78, size * 0.30],
                        radius=size * 0.02, fill=_ACCENT)                              # Deckel
    d.rounded_rectangle([size * 0.30, size * 0.32, size * 0.70, size * 0.84],
                        radius=size * 0.05, fill=_ACCENT)                              # Koerper
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
