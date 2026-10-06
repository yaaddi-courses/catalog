"""Original flat deck covers drawn with Pillow, for decks that would otherwise share a generic image.

    python tools/make_covers.py

Draws the covers listed in COVERS (path -> drawing). Fonts: JetBrains Mono (SIL Open Font License).
Nothing is traced from or based on third-party artwork. Add a new entry when a course needs another cover.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.environ.get(
    "YAADDI_FONT",
    r"D:\ai\Artifcats\Software\Yaaddi\app\node_modules\@expo-google-fonts\jetbrains-mono\800ExtraBold\JetBrainsMono_800ExtraBold.ttf",
)
SIZE = 256
BG, BLUE, DARK_BLUE, WHITE, GREEN = (232, 244, 253), (33, 130, 214), (20, 84, 150), (255, 255, 255), (38, 160, 96)


def canvas():
    img = Image.new("RGB", (SIZE, SIZE), BG)
    return img, ImageDraw.Draw(img)


def checkpoint(number):
    """A card with a big number and a tick: 'checkpoint N'."""
    img, d = canvas()
    d.ellipse([34, 150, 222, 230], fill=(214, 232, 247))
    d.rounded_rectangle([62, 44, 194, 188], radius=22, fill=WHITE, outline=BLUE, width=6)
    font = ImageFont.truetype(FONT, 78)
    text = str(number)
    d.text((128 - d.textlength(text, font=font) / 2, 66), text, font=font, fill=BLUE)
    d.ellipse([150, 140, 206, 196], fill=GREEN)
    d.line([(162, 168), (175, 181), (196, 154)], fill=WHITE, width=8, joint="curve")
    return img


def recap():
    """Two matching cards joined by a line: 'match the key terms'."""
    img, d = canvas()
    d.ellipse([30, 160, 226, 232], fill=(214, 232, 247))
    for x in (34, 148):
        d.rounded_rectangle([x, 70, x + 74, 160], radius=14, fill=WHITE, outline=BLUE, width=6)
        d.line([(x + 16, 100), (x + 58, 100)], fill=BLUE, width=7)
        d.line([(x + 16, 124), (x + 44, 124)], fill=(150, 190, 230), width=7)
    d.line([(108, 115), (148, 115)], fill=DARK_BLUE, width=7)
    d.ellipse([100, 107, 116, 123], fill=DARK_BLUE)
    d.ellipse([140, 107, 156, 123], fill=DARK_BLUE)
    return img


def database():
    """A database drum (three stacked discs)."""
    img, d = canvas()
    d.ellipse([40, 190, 216, 236], fill=(214, 232, 247))
    for top in (150, 108, 66):
        d.rectangle([68, top, 188, top + 40], fill=BLUE)
        d.ellipse([68, top - 18, 188, top + 18], fill=(80, 160, 232))
        d.ellipse([68, top + 22, 188, top + 58], fill=BLUE)
        d.rectangle([68, top, 188, top + 40], fill=BLUE)
        d.ellipse([68, top - 18, 188, top + 18], fill=(110, 178, 238), outline=DARK_BLUE, width=3)
    d.ellipse([154, 168, 166, 180], fill=WHITE)
    return img


def coin():
    """A coin with a bold bar symbol: cryptocurrency."""
    img, d = canvas()
    d.ellipse([40, 190, 216, 236], fill=(214, 232, 247))
    d.ellipse([56, 40, 200, 184], fill=(246, 190, 60), outline=(200, 130, 20), width=8)
    d.ellipse([78, 62, 178, 162], outline=(255, 232, 150), width=6)
    font = ImageFont.truetype(FONT, 84)
    d.text((128 - d.textlength("B", font=font) / 2, 74), "B", font=font, fill=(200, 130, 20))
    return img


def phone_alert():
    """A phone showing a caller number and a warning triangle: spoofed caller id."""
    img, d = canvas()
    d.ellipse([40, 196, 216, 238], fill=(214, 232, 247))
    d.rounded_rectangle([82, 28, 174, 212], radius=18, fill=WHITE, outline=BLUE, width=7)
    d.rounded_rectangle([96, 56, 160, 82], radius=6, fill=(214, 232, 247))
    d.polygon([(128, 104), (156, 154), (100, 154)], fill=(240, 170, 40))
    d.line([(128, 120), (128, 138)], fill=WHITE, width=6)
    d.ellipse([124, 143, 132, 151], fill=WHITE)
    d.rounded_rectangle([104, 176, 152, 190], radius=7, fill=(150, 190, 230))
    return img


def fake_profile():
    """Two overlapping profile cards, one with a question mark: a cloned account."""
    img, d = canvas()
    d.ellipse([30, 190, 226, 238], fill=(214, 232, 247))
    for x, fill in ((40, (150, 190, 230)), (96, WHITE)):
        d.rounded_rectangle([x, 56, x + 120, 190], radius=18, fill=fill, outline=BLUE, width=6)
        d.ellipse([x + 38, 76, x + 82, 120], fill=BLUE)
        d.pieslice([x + 20, 118, x + 100, 190], 180, 360, fill=BLUE)
    font = ImageFont.truetype(FONT, 60)
    d.text((176 - d.textlength("?", font=font) / 2, 112), "?", font=font, fill=(240, 170, 40))
    return img


COVERS = {
    "day-trading-plan/source/images/deck27.png": lambda: checkpoint(2),
    "day-trading-plan/source/images/deck28.png": lambda: checkpoint(3),
    "day-trading-plan/source/images/deck29.png": lambda: checkpoint(4),
    "day-trading-plan/source/images/deck25.png": recap,
    "kubernetes-fundamentals/source/images/unit43.png": database,
    "scam-tashkhis-farsi/source/images/unit15.png": coin,
    "scam-tashkhis-farsi/source/images/unit18.png": phone_alert,
    "scam-tashkhis-farsi/source/images/unit21.png": fake_profile,
}


if __name__ == "__main__":
    only = sys.argv[1:]
    for rel, draw in COVERS.items():
        if only and not any(o in rel for o in only):
            continue
        draw().save(os.path.join(ROOT, rel))
        print("wrote", rel)
