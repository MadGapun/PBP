# -*- coding: utf-8 -*-
"""Erzeugt das Social-Preview-Bild (1280x640) fuer das GitHub-Repo.

Baustelle 3 (#843): Die Kachel erscheint, wenn der Repo-Link in LinkedIn,
Slack oder WhatsApp geteilt wird. Aufbau: PBP-Logo + Name + Einzeiler
links, dezent das Dashboard (aktueller Screenshot mit Musterdaten) rechts.

Verwendung:
    python docs/assets/make_social_preview.py

Ausgabe:
    docs/social-preview.png            (1280x640, Upload-Format)
    docs/assets/web/social-preview.png (800 px breite Kopie)

Der Einzeiler kommt inhaltlich aus docs/assets/texte.md — bei Aenderungen
dort auch hier nachziehen.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
LOGO = ROOT / "docs" / "pbp.png"
DASHBOARD = ROOT / "docs" / "screenshots" / "01_dashboard.png"
OUT = ROOT / "docs" / "social-preview.png"
OUT_WEB = ROOT / "docs" / "assets" / "web" / "social-preview.png"

W, H = 1280, 640


def _font(size, bold=False):
    kandidaten = (
        ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
    )
    for name in kandidaten:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    # Heller Hintergrund mit sanftem Verlauf
    img = Image.new("RGB", (W, H), "#f4f7fb")
    verlauf = Image.new("L", (1, H))
    for y in range(H):
        verlauf.putpixel((0, y), int(12 * y / H))
    blau = Image.new("RGB", (W, H), "#dbe7f5")
    img = Image.composite(blau, img, verlauf.resize((W, H)))
    draw = ImageDraw.Draw(img)

    # Dashboard rechts, leicht angeschnitten, mit weichem Schatten
    dash = Image.open(DASHBOARD).convert("RGB")
    dash_h = 520
    ratio = dash_h / dash.height
    dash = dash.resize((int(dash.width * ratio), dash_h), Image.LANCZOS)
    dx, dy = 704, 80
    schatten = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(schatten).rounded_rectangle(
        [dx - 6, dy - 6, dx + dash.width + 10, dy + dash.height + 14],
        radius=18, fill=(30, 45, 70, 90),
    )
    schatten = schatten.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img.convert("RGBA"), schatten).convert("RGB")
    # dezent: Screenshot leicht Richtung Hintergrund aufhellen
    weiss = Image.new("RGB", dash.size, "#f4f7fb")
    dash = Image.blend(dash, weiss, 0.12)
    maske = Image.new("L", dash.size, 255)
    ImageDraw.Draw(maske).rounded_rectangle(
        [0, 0, dash.width, dash.height], radius=12, fill=255
    )
    img.paste(dash, (dx, dy), maske)
    draw = ImageDraw.Draw(img)

    # Logo + Texte links
    logo = Image.open(LOGO).convert("RGBA")
    logo_h = 96
    logo = logo.resize((int(logo.width * logo_h / logo.height), logo_h), Image.LANCZOS)
    img.paste(logo, (72, 96), logo)

    draw.text((72 + logo.width + 24, 106), "PBP", font=_font(72, bold=True), fill="#12263f")

    draw.text((72, 232), "Persönliches Bewerbungs-Portal",
              font=_font(38, bold=True), fill="#12263f")
    draw.text((72, 300), "Der Bewerbungs-Helfer für den\ndeutschsprachigen Raum",
              font=_font(33), fill="#2e4562", spacing=10)

    draw.text((72, 416), "Geführt. Lokal. Einfach.",
              font=_font(28, bold=True), fill="#1f6f57")
    draw.text((72, 462), "Kostenlos und Open Source.",
              font=_font(24), fill="#3f5a78")
    draw.text((72, 498), "Deine Daten bleiben auf deinem Rechner.",
              font=_font(24), fill="#3f5a78")

    draw.text((72, 548), "github.com/MadGapun/PBP", font=_font(24, bold=True),
              fill="#1f6f57")

    img.save(OUT, optimize=True)

    web = img.resize((800, 400), Image.LANCZOS)
    OUT_WEB.parent.mkdir(parents=True, exist_ok=True)
    web.save(OUT_WEB, optimize=True)
    print(f"OK: {OUT} ({OUT.stat().st_size // 1024} KB) + {OUT_WEB}")


if __name__ == "__main__":
    main()
