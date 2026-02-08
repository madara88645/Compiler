import sys
import os

# Add current directory to path so imports work as they do in the app
sys.path.append(os.getcwd())

print("Attempting to import api.main...")
try:
    from api import main

    print(f"SUCCESS: api.main imported successfully: {main}")
except ImportError as e:
    print(f"FAILURE: ImportError: {e}")
    import traceback

    traceback.print_exc()
except Exception as e:
    print(f"FAILURE: Exception: {e}")
    import traceback

    traceback.print_exc()
