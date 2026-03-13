from app.testing.models import TestSuite, TestCase, Assertion
from app.testing.runner import TestRunner, Executor


class SchemaMockExecutor(Executor):
    def execute(self, prompt: str, config: dict) -> str:
        if "invalid" in prompt.lower():
            return '{"name": "Invalid", "price": "not_a_number"}'
        return '{"name": "Valid Name", "price": 10.99}'


def test_runner_schema_validation(tmp_path):
    p_file = tmp_path / "test_prompt.txt"
    p_file.write_text("Test prompt: {{type}}", encoding="utf-8")

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "price": {"type": "number"}},
        "required": ["name", "price"],
    }

    suite = TestSuite(
        name="Schema Suite",
        prompt_file=str(p_file.name),
        test_cases=[
            TestCase(
                id="c1",
                input_variables={"type": "valid"},
                assertions=[Assertion(type="json_schema", value=schema)],
            ),
            TestCase(
                id="c2",
                input_variables={"type": "invalid"},
                assertions=[Assertion(type="json_schema", value=schema)],
            ),
        ],
    )

    runner = TestRunner(executor=SchemaMockExecutor())
    result = runner.run_suite(suite, base_dir=tmp_path)

    assert result.passed == 1
    assert result.failed == 1

    r1 = next(r for r in result.results if r.test_case_id == "c1")
    assert r1.passed

    r2 = next(r for r in result.results if r.test_case_id == "c2")
    assert not r2.passed
    assert "Assertion failed: json_schema" in r2.failures[0]
