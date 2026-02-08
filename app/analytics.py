from typing import Any, Dict


class AnalyticsManager:
    def __init__(self):
        pass


def create_record_from_ir(ir: Any, *args, **kwargs) -> Dict[str, Any]:
    """Stub for create_record_from_ir."""
    # Return a dummy dict to prevent crashes in UI
    return {
        "id": getattr(ir, "id", "unknown"),
        "timestamp": "2024-01-01T00:00:00",
        "prompt": str(ir),
        "metrics": {},
    }
