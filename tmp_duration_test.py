from app.compiler import compile_text

cases = [
    "yarım saat içinde bana temel sql öğret",
    "half hour tutorial about docker basics",
    "half an hour guide to python lists",
    "1 saatlik makine öğrenmesi özeti",
]
for c in cases:
    ir = compile_text(c)
    print(c, "->", ir.inputs.get("duration"))
