from api.main import compile_endpoint, CompileRequest


def test():
    text = "Extract product_name."
    req = CompileRequest(text=text, v2=False, diagnostics=True)

    print("Calling compile_endpoint with v2=False...")
    res = compile_endpoint(req)

    print(f"Response Type: {type(res)}")
    print(f"Has 'ir'? {hasattr(res, 'ir')}")
    print(f"Has 'expanded_prompt_v2'? {hasattr(res, 'expanded_prompt_v2')}")

    if res.expanded_prompt_v2:
        print("expanded_prompt_v2 Content Preview:")
        print(res.expanded_prompt_v2[:100])

    if res.heuristic2_version:
        print(f"heuristic2_version: {res.heuristic2_version}")
    else:
        print("heuristic2_version is None")


if __name__ == "__main__":
    test()
