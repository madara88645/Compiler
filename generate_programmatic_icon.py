from PIL import Image, ImageDraw


def create_icon():
    size = 512
    # Background: Deep Purple to Darker Purple Gradient
    img = Image.new("RGB", (size, size), color="#4a148c")
    draw = ImageDraw.Draw(img)

    # Draw simple gradient effect (concentric circles)
    # for i in range(size, 0, -2):
    #     color_val = int(74 - (i / size) * 40)  # #4a148c is approx (74, 20, 140)
    #     draw.ellipse([size/2 - i/2, size/2 - i/2, size/2 + i/2, size/2 + i/2], fill=color)

    # Main Shape: Lightning Bolt (Stylized key/compiler symbol)
    # Coordinates for a simple bolt
    w, h = size, size
    points = [
        (w * 0.55, h * 0.1),  # Top tip
        (w * 0.2, h * 0.6),  # Mid left
        (w * 0.45, h * 0.6),  # Mid inner
        (w * 0.35, h * 0.9),  # Bottom tip
        (w * 0.8, h * 0.4),  # Mid right
        (w * 0.55, h * 0.4),  # Mid inner right
    ]

    # Draw bolt
    draw.polygon(points, fill="#fb8c00")  # Vibrant Orange

    # Save
    img.save("extension/icon.png")
    print("Created programmatic icon: extension/icon.png")


if __name__ == "__main__":
    create_icon()
