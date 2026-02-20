import os
import zipfile
import json

EXTENSION_DIR = "extension"
OUTPUT_DIR = "dist"


def get_version():
    with open(os.path.join(EXTENSION_DIR, "manifest.json"), "r") as f:
        data = json.load(f)
    return data.get("version", "0.0.0")


def package():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    version = get_version()
    filename = f"my-compiler-extension-v{version}.zip"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(EXTENSION_DIR):
            for file in files:
                # Calculate path relative to extension dir so it zips cleanly at root
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, EXTENSION_DIR)
                zipf.write(abs_path, rel_path)
                print(f"Adding: {rel_path}")

    print(f"\n✅ Packaged successfully: {filepath}")


if __name__ == "__main__":
    package()
