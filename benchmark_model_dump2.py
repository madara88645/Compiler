import json
import timeit
from app.models_v2 import PromptIR

# Create a sample object
ir = PromptIR()
ir.system_prompt = "You are a helpful assistant." * 100
ir.tools = [{"name": "test_tool", "description": "test"}] * 10

def test_json_dumps_model_dump():
    return json.dumps(ir.model_dump(), indent=2, ensure_ascii=False, sort_keys=True)

def test_model_dump_json():
    # Unfortunately model_dump_json doesn't support sorting keys natively to match json.dumps format,
    # but we can check if it's faster.
    # However, for unified diff, sort_keys=True is important.
    return ir.model_dump_json(indent=2)

def test_orjson_dumps_model_dump():
    import orjson
    return orjson.dumps(ir.model_dump(), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS).decode('utf-8')

print("json.dumps(model_dump()):", timeit.timeit(test_json_dumps_model_dump, number=1000))
print("model_dump_json():", timeit.timeit(test_model_dump_json, number=1000))
print("orjson.dumps(model_dump()):", timeit.timeit(test_orjson_dumps_model_dump, number=1000))
