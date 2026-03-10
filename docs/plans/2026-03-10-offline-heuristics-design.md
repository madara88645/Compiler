# Offline Compiler Heuristics Design

## Overview
This document outlines two new heuristics to improve the prompt quality and token efficiency of the offline compiler engine.

## 1. Strict Format Enforcer (`FormatEnforcerHandler`)
**Goal:** Prevent LLMs from wrapping structured data in conversational filler or markdown code blocks when strict data is requested.
**Trigger:** Analyzes the prompt for data extraction intent (e.g., "extract", "CSV", "JSON", "table", "schema").
**Action:** Injects explicit negative constraints into the IR, such as "No conversational filler. Return ONLY the requested format."

## 2. Constraint Paradox Resolver (`ParadoxResolverHandler`)
**Goal:** Detect conflicting instructions from the user that confuse the LLM and cause poor performance.
**Trigger:** Scans parsed constraints and the raw prompt for antonym pairs (e.g., "be brief" vs "explain in detail", "simple language" vs "technical deep dive").
**Action:** Injects a meta-constraint that resolves the conflict, e.g., "CONFLICT DETECTED: You have been asked to both be brief and detailed. Prioritize detail but use concise bullet points to remain brief."
