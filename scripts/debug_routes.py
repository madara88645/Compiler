from api.main import app

print("Routes:")
for route in app.routes:
    print(f"{route.path} [{route.methods}]")
