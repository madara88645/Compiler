import time
from unittest.mock import MagicMock
from app.ui.live import LiveModeManager
from app.llm_engine.schemas import WorkerResponse
from app.models_v2 import IRv2


class MockRoot:
    def __init__(self):
        self.called_after = []

    def after(self, delay, callback):
        self.called_after.append((delay, callback))
        # Execute immediately to simulate callback execution on main thread
        callback()


def test_live_mode_manager_init():
    root = MockRoot()
    on_result = MagicMock()
    on_start = MagicMock()
    on_error = MagicMock()

    manager = LiveModeManager(root, on_result, on_start, on_error)
    assert manager.root == root
    assert manager.on_result == on_result
    assert manager.on_start == on_start
    assert manager.on_error == on_error
    assert manager.compiler is None
    assert manager.enabled is False


def test_live_mode_manager_set_compiler():
    manager = LiveModeManager(MockRoot(), MagicMock(), MagicMock(), MagicMock())
    compiler = MagicMock()
    manager.set_compiler(compiler)
    assert manager.compiler == compiler


def test_live_mode_manager_schedule_disabled():
    on_error = MagicMock()
    manager = LiveModeManager(MockRoot(), MagicMock(), MagicMock(), on_error)
    manager.enabled = False

    manager.schedule("test prompt")
    assert not on_error.called
    assert manager._timer is None


def test_live_mode_manager_schedule_no_compiler():
    on_error = MagicMock()
    manager = LiveModeManager(MockRoot(), MagicMock(), MagicMock(), on_error)
    manager.enabled = True

    manager.schedule("test prompt")
    on_error.assert_called_once_with("HybridCompiler not initialized. Check API Key.")


def test_live_mode_manager_schedule_duplicate_text():
    compiler = MagicMock()
    manager = LiveModeManager(MockRoot(), MagicMock(), MagicMock(), MagicMock())
    manager.set_compiler(compiler)
    manager.enabled = True
    manager._last_text = "test prompt"

    manager.schedule("test prompt")
    assert manager._timer is None


def test_live_mode_manager_schedule_and_debounce():
    compiler = MagicMock()
    manager = LiveModeManager(MockRoot(), MagicMock(), MagicMock(), MagicMock())
    manager.set_compiler(compiler)
    manager.enabled = True

    # Schedule first text
    manager.schedule("test 1", delay_ms=10)
    timer1 = manager._timer
    assert timer1 is not None
    assert timer1.is_alive()

    # Schedule second text immediately to cancel first timer (debounce)
    manager.schedule("test 2", delay_ms=10)
    timer2 = manager._timer
    assert timer2 is not None
    assert timer2 is not timer1

    # Wait for timer to fire
    time.sleep(0.05)
    assert not timer2.is_alive()


def test_live_mode_manager_worker_success():
    root = MockRoot()
    on_result = MagicMock()
    on_start = MagicMock()
    on_error = MagicMock()
    compiler = MagicMock()

    dummy_response = WorkerResponse(ir=IRv2(), optimized_content="compiled prompt")
    compiler.compile.return_value = dummy_response

    manager = LiveModeManager(root, on_result, on_start, on_error)
    manager.set_compiler(compiler)

    manager._worker("test prompt")

    on_start.assert_called_once()
    compiler.compile.assert_called_once_with("test prompt")
    on_result.assert_called_once_with(dummy_response)
    assert not on_error.called


def test_live_mode_manager_worker_compiler_error():
    root = MockRoot()
    on_result = MagicMock()
    on_start = MagicMock()
    on_error = MagicMock()
    compiler = MagicMock()

    compiler.compile.side_effect = ValueError("Compilation failed")

    manager = LiveModeManager(root, on_result, on_start, on_error)
    manager.set_compiler(compiler)

    manager._worker("test prompt")

    on_start.assert_called_once()
    on_error.assert_called_once_with("An internal error occurred.")
    assert not on_result.called


def test_live_mode_manager_worker_stale_request():
    root = MockRoot()
    on_result = MagicMock()
    on_start = MagicMock()
    on_error = MagicMock()
    compiler = MagicMock()

    dummy_response = WorkerResponse(ir=IRv2(), optimized_content="compiled prompt")
    compiler.compile.return_value = dummy_response

    manager = LiveModeManager(root, on_result, on_start, on_error)
    manager.set_compiler(compiler)

    # Intercept compile call and increment request ID to simulate a newer request coming in
    def compile_side_effect(text):
        manager._latest_request_id += 1
        return dummy_response

    compiler.compile.side_effect = compile_side_effect

    manager._worker("test prompt")

    # Result should be ignored because it is stale
    assert not on_result.called
    assert not on_error.called


def test_live_mode_manager_worker_stale_request_on_error():
    root = MockRoot()
    on_result = MagicMock()
    on_start = MagicMock()
    on_error = MagicMock()
    compiler = MagicMock()

    compiler.compile.side_effect = ValueError("Failed")

    manager = LiveModeManager(root, on_result, on_start, on_error)
    manager.set_compiler(compiler)

    # Intercept compiler call, simulate newer request, and raise error
    def compile_side_effect(text):
        manager._latest_request_id += 1
        raise ValueError("Failed")

    compiler.compile.side_effect = compile_side_effect

    manager._worker("test prompt")

    # Error should be ignored because it is stale
    assert not on_error.called


def test_live_mode_manager_worker_no_compiler_error():
    root = MockRoot()
    on_result = MagicMock()
    on_start = MagicMock()
    on_error = MagicMock()

    manager = LiveModeManager(root, on_result, on_start, on_error)
    # Don't set compiler
    manager._worker("test prompt")

    on_start.assert_called_once()
    on_error.assert_called_once_with("An internal error occurred.")
    assert not on_result.called
