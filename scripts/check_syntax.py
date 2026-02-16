import py_compile

files = [
    r"c:\Users\User\Desktop\myCompiler\api\main.py",
    r"c:\Users\User\Desktop\myCompiler\api\auth.py",
    r"c:\Users\User\Desktop\myCompiler\integrations\mcp-server\server.py",
]

print("Checking syntax...")
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"FAIL: {f}\n{e}")
    except Exception as e:
        print(f"ERROR: {f}\n{e}")
