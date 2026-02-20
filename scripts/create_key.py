import uuid
from api.auth import SessionLocal, APIKey, engine, Base


def create_key(owner: str):
    db = SessionLocal()
    new_key = "sk_" + str(uuid.uuid4()).replace("-", "")
    key_record = APIKey(key=new_key, owner=owner)
    db.add(key_record)
    db.commit()
    print(f"Created API Key for {owner}: {new_key}")
    db.close()


if __name__ == "__main__":
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    create_key("test_user")
