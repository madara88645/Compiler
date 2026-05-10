import time
import json
from pydantic import BaseModel
from typing import List, Dict, Any

class TestModel(BaseModel):
    name: str
    values: List[int]
    meta: Dict[str, Any]

obj = TestModel(name="test", values=[1, 2, 3], meta={"a": 1, "b": "2"})

# json.dumps(model_dump())
start = time.perf_counter()
for _ in range(100000):
    _ = json.dumps(obj.model_dump())
end = time.perf_counter()
print(f"json.dumps(model_dump()): {end - start:.6f}s")

# model_dump_json()
start = time.perf_counter()
for _ in range(100000):
    _ = obj.model_dump_json()
end = time.perf_counter()
print(f"model_dump_json(): {end - start:.6f}s")
