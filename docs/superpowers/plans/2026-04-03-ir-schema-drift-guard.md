# IR Schema Drift Guard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Checked-in IR schema files ile backend contract sabitleri arasında kritik enum drift'ini CI'da yakalamak.

**Architecture:** Ortak IR contract sabitlerini tek bir Python modülünde topluyoruz. Testler checked-in JSON schema dosyalarını bu sabitlere karşı doğruluyor, modeller de aynı sabitleri validator içinde kullanıyor.

**Tech Stack:** Python, Pydantic, pytest, jsonschema

---

## Chunk 1: Shared Contract Constants

### Task 1: Add central IR contract constants

**Files:**
- Create: `app/ir_contract.py`
- Modify: `app/models.py`
- Test: `tests/test_schema_validation.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add shared enum constants**
- [ ] **Step 4: Reuse constants in v1 validators**
- [ ] **Step 5: Run tests to verify they pass**

## Chunk 2: Schema Parity Coverage

### Task 2: Cover high-risk checked-in schema enums

**Files:**
- Modify: `tests/test_schema_validation.py`
- Verify: `app/_schemas/ir.schema.json`
- Verify: `app/_schemas/ir_v2.schema.json`

- [ ] **Step 1: Assert shared enums for v1 and v2**
- [ ] **Step 2: Assert v2 policy, intent, step, and priority enums**
- [ ] **Step 3: Run focused schema tests**
- [ ] **Step 4: Run broader regression tests**
