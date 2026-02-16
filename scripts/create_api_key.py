import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from api.auth import SessionLocal, APIKey  # noqa: E402
import uuid  # noqa: E402
import time  # noqa: E402


def create_key(owner: str):
    db = SessionLocal()
    try:
        # Check existing
        existing = db.query(APIKey).filter(APIKey.owner == owner).first()
        if existing:
            print(f"User '{owner}' already has a key: {existing.key}")
            return existing.key

        new_key = "sk-" + uuid.uuid4().hex
        db_obj = APIKey(key=new_key, owner=owner, is_active=True, created_at=time.time())
        db.add(db_obj)
        db.commit()
        print(f"Created new key for '{owner}': {new_key}")
        return new_key
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    owner_name = sys.argv[1] if len(sys.argv) > 1 else "tester"
    create_key(owner_name)
