#!/usr/bin/env python3
"""Generate a simple .icns for Ghenghis Khan using Pillow + iconutil."""
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def draw_icon(size: int) -> Image.Image:
    # Rounded-rect background with a red-black gradient feel
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = int(size * 0.22)
    # Base
    d.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=(28, 28, 30, 255),
    )
    # Inner accent bar
    bar_h = int(size * 0.14)
    d.rounded_rectangle(
        (0, 0, size - 1, bar_h),
        radius=radius,
        fill=(184, 50, 42, 255),
    )
    # Mask the bottom of the bar so only the top corners are rounded
    d.rectangle((0, bar_h // 2, size - 1, bar_h), fill=(184, 50, 42, 255))

    # Letters "GK" centered
    text = "GK"
    # Try a nice bold font, fall back
    font = None
    for candidate in [
        "/System/Library/Fonts/Supplemental/Futura.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, int(size * 0.42))
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] + int(size * 0.03)
    d.text((tx, ty), text, fill=(242, 242, 247, 255), font=font)

    # Small "PDF" tag lower right
    if size >= 128:
        tag_font = None
        for candidate in ["/System/Library/Fonts/HelveticaNeue.ttc"]:
            if Path(candidate).exists():
                try:
                    tag_font = ImageFont.truetype(candidate, int(size * 0.10))
                    break
                except Exception:
                    pass
        if tag_font:
            tag = "PDF"
            bb = d.textbbox((0, 0), tag, font=tag_font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            pad = int(size * 0.05)
            box_w = tw + pad * 2
            box_h = th + pad
            x0 = size - box_w - int(size * 0.08)
            y0 = size - box_h - int(size * 0.08)
            d.rounded_rectangle(
                (x0, y0, x0 + box_w, y0 + box_h),
                radius=int(size * 0.05),
                fill=(184, 50, 42, 235),
            )
            d.text((x0 + pad - bb[0], y0 + pad // 2 - bb[1]), tag,
                   fill=(255, 255, 255, 255), font=tag_font)

    return img


def main():
    build_dir = Path(__file__).parent
    iconset = build_dir / "AppIcon.iconset"
    iconset.mkdir(exist_ok=True)

    sizes = [
        (16, "16x16"), (32, "16x16@2x"),
        (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"),
        (256, "256x256"), (512, "256x256@2x"),
        (512, "512x512"), (1024, "512x512@2x"),
    ]
    for size, name in sizes:
        img = draw_icon(size)
        img.save(iconset / f"icon_{name}.png")

    icns = build_dir / "AppIcon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
        check=True,
    )
    # Cleanup
    for f in iconset.iterdir():
        f.unlink()
    iconset.rmdir()
    print(f"✓ {icns}")


if __name__ == "__main__":
    main()
