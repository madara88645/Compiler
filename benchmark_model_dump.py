import json
import timeit
from app.models_v2 import IRv2

# Create a sample object
ir = IRv2(version="2.0", type="agent", role="You are a helpful assistant.", guidelines=["Be helpful", "Be polite"] * 10)
ir.metadata = {"tool": "test", "tags": ["a", "b", "c"]}

def test_json_dumps_model_dump():
    return json.dumps(ir.model_dump(), indent=2, ensure_ascii=False, sort_keys=True)

def test_orjson_dumps_model_dump():
    import orjson
    return orjson.dumps(ir.model_dump(), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS).decode('utf-8')

print("json.dumps(model_dump()):", timeit.timeit(test_json_dumps_model_dump, number=1000))
print("orjson.dumps(model_dump()):", timeit.timeit(test_orjson_dumps_model_dump, number=1000))
