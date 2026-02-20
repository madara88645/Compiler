from PIL import Image
import os

ICON_PATH = "extension/icon.png"
SIZES = [16, 48, 128]


def generate_icons():
    if not os.path.exists(ICON_PATH):
        print(f"Error: {ICON_PATH} not found.")
        return

    img = Image.open(ICON_PATH)

    for size in SIZES:
        new_img = img.resize((size, size), Image.Resampling.LANCZOS)
        output_path = f"extension/icon{size}.png"
        new_img.save(output_path)
        print(f"Generated: {output_path}")


if __name__ == "__main__":
    generate_icons()
