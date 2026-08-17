# Offline Compiler Heuristics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve offline compiler prompt quality by adding Strict Format Enforcer and Constraint Paradox Resolver heuristics.

**Architecture:** Create two new `BaseHandler` classes in `app/heuristics/handlers` and register them in the main `compile_text` and `compile_text_v2` pipelines in `app/compiler.py`.

**Tech Stack:** Python, Pytest

---

### Task 1: Strict Format Enforcer

**Files:**
- Create: `app/heuristics/handlers/format_enforcer.py`
- Create: `tests/test_format_enforcer.py`

**Step 1: Write the failing test**

```python
# tests/test_format_enforcer.py
from app.heuristics.handlers.format_enforcer import FormatEnforcerHandler
from app.models import IR

def test_format_enforcer_injects_constraint():
    handler = FormatEnforcerHandler()
    ir = IR(text="Extract the emails into a JSON file", language="en")
    result = handler.process(ir)

    assert any("No conversational filler" in c for c in result.constraints)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_format_enforcer.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# app/heuristics/handlers/format_enforcer.py
from app.heuristics.handlers.base import BaseHandler
from app.models import IR

class FormatEnforcerHandler(BaseHandler):
    """Injects strict constraints when data formats are requested."""

    def process(self, ir: IR) -> IR:
        text_lower = ir.text.lower()
        format_keywords = ["json", "csv", "xml", "table", "extract"]

        if any(kw in text_lower for kw in format_keywords):
            if "No conversational filler. Return ONLY the requested format." not in ir.constraints:
                ir.constraints.append("No conversational filler. Return ONLY the requested format.")

        return ir
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_format_enforcer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/heuristics/handlers/format_enforcer.py tests/test_format_enforcer.py
git commit -m "feat: add FormatEnforcerHandler for offline compilation"
```

---

### Task 2: Constraint Paradox Resolver

**Files:**
- Create: `app/heuristics/handlers/paradox_resolver.py`
- Create: `tests/test_paradox_resolver.py`

**Step 1: Write the failing test**

```python
# tests/test_paradox_resolver.py
from app.heuristics.handlers.paradox_resolver import ParadoxResolverHandler
from app.models import IR

def test_paradox_resolver_detects_length_conflict():
    handler = ParadoxResolverHandler()
    ir = IR(text="Make it very short but also explain everything in detail", language="en")
    ir.constraints = ["be brief", "be very detailed"]
    result = handler.process(ir)

    assert any("CONFLICT DETECTED" in c for c in result.constraints)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_paradox_resolver.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# app/heuristics/handlers/paradox_resolver.py
from app.heuristics.handlers.base import BaseHandler
from app.models import IR

class ParadoxResolverHandler(BaseHandler):
    """Detects constraint paradoxes and injects resolution rules."""

    def process(self, ir: IR) -> IR:
        text_lower = ir.text.lower()
        constraints_lower = " ".join(ir.constraints).lower()

        brief_kw = ["short", "brief", "concise"]
        detail_kw = ["detail", "comprehensive", "everything"]

        has_brief = any(k in text_lower or k in constraints_lower for k in brief_kw)
        has_detail = any(k in text_lower or k in constraints_lower for k in detail_kw)

        if has_brief and has_detail:
            resolution = "CONFLICT DETECTED: You have been asked to be both brief and detailed. Prioritize detail but use concise bullet points to remain brief."
            if resolution not in ir.constraints:
                ir.constraints.append(resolution)

        return ir
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_paradox_resolver.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/heuristics/handlers/paradox_resolver.py tests/test_paradox_resolver.py
git commit -m "feat: add ParadoxResolverHandler for offline compilation"
```

---

### Task 3: Integration into Compiler Pipeline

**Files:**
- Modify: `app/compiler.py`

**Step 1: Write the failing test**

```python
# append to tests/test_comprehensive.py or create a new small test inside it
# tests/test_offline_new_heuristics.py
from app.compiler import compile_text

def test_new_heuristics_integration():
    ir = compile_text("Extract a list of items to JSON, make it short but very detailed.")
    constraints_text = " ".join(ir.constraints)

    assert "No conversational filler" in constraints_text
    assert "CONFLICT DETECTED" in constraints_text
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offline_new_heuristics.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Modify `app/compiler.py` to import and register both handlers in `compile_text`.

```python
# Add to imports in app/compiler.py:
from .heuristics.handlers.format_enforcer import FormatEnforcerHandler
from .heuristics.handlers.paradox_resolver import ParadoxResolverHandler

# In compile_text function, add to the pipeline:
    pipeline = [
        # ... existing handlers ...
        FormatEnforcerHandler(),
        ParadoxResolverHandler(),
    ]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offline_new_heuristics.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/compiler.py tests/test_offline_new_heuristics.py
git commit -m "feat: integrate FormatEnforcer and ParadoxResolver into compiler pipeline"
```
