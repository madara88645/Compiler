import io
import zipfile

from scripts.github_int_failure_fixer import GitHubIntFailureFixer


class FakeResponse:
    def __init__(self, *, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.post_calls = []

    def get(self, url, params=None, timeout=None):
        if url.endswith("/actions/runs"):
            return FakeResponse(payload={"workflow_runs": [{"id": 123, "name": "CI", "html_url": "http://example/run"}]})
        if url.endswith("/actions/runs/123/logs"):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, mode="w") as archive:
                archive.writestr("job.txt", "Error: unable to find package.json")
            return FakeResponse(content=stream.getvalue())
        raise AssertionError(f"unexpected GET url: {url}")

    def post(self, url, timeout=None):
        self.post_calls.append(url)
        return FakeResponse()


def test_analyze_failure_package_json_signature():
    fixer = GitHubIntFailureFixer("o", "r", "token", session=FakeSession())
    cause, recommendation = fixer.analyze_failure("npm ERR! enoent Error: unable to find package.json")
    assert "package.json" in cause
    assert "working-directory" in recommendation


def test_process_failed_runs_dry_run_skips_rerun():
    session = FakeSession()
    fixer = GitHubIntFailureFixer("o", "r", "token", session=session)

    report = fixer.process_failed_runs(auto_rerun=True, dry_run=True)

    assert len(report) == 1
    assert report[0]["rerun_status"] == "skipped"
    assert session.post_calls == []


def test_process_failed_runs_can_trigger_rerun():
    session = FakeSession()
    fixer = GitHubIntFailureFixer("o", "r", "token", session=session)

    report = fixer.process_failed_runs(auto_rerun=True, dry_run=False)

    assert report[0]["rerun_status"] == "triggered"
    assert any(call.endswith("/actions/runs/123/rerun-failed-jobs") for call in session.post_calls)
