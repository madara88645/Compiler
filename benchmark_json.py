import json
import orjson
import timeit

data = {"passed": True, "reason": "Good job", "score": 0.95}
json_str = json.dumps(data)
orjson_bytes = orjson.dumps(data)

def test_json_loads():
    return json.loads(json_str)

def test_orjson_loads():
    return orjson.loads(json_str.encode("utf-8"))

print("json.loads:", timeit.timeit(test_json_loads, number=100000))
print("orjson.loads:", timeit.timeit(test_orjson_loads, number=100000))
