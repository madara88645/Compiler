"""
Cost Estimator for Optimization Runs.
Predicts token usage and cost based on configuration and initial prompt.
"""

from __future__ import annotations
from typing import Dict, Any, Union
import math
from .models import OptimizationConfig

# Pricing per 1M tokens (USD)
# Source: OpenAI Pricing (Approximate as of late 2024/2025)
MODEL_PRICING = {
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Fallback/Default
    "default": {"input": 5.00, "output": 15.00},
}


def estimate_run_cost(
    config: OptimizationConfig, initial_prompt: str
) -> Dict[str, Union[float, str]]:
    """
    Estimate the cost of a full optimization run.

    Args:
        config: The optimization configuration.
        initial_prompt: The starting prompt text.

    Returns:
        Dict containing 'min_cost', 'max_cost', and a formatted 'message'.
    """
    model_name = config.model.lower()
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["default"])

    # 1. Volume Estimation
    generations = config.max_generations
    candidates_per_gen = config.candidates_per_generation

    # Total number of mutation output generations
    # Gen 0 is baseline (0 mutations).
    # Gen 1 to Gen N: Each produces `candidates_per_gen` candidates.
    total_mutations = generations * candidates_per_gen

    # Adversarial runs (if enabled)
    # logic: if adversarial_every > 0, we run it every N gens.
    # Each run generates ~3 adversarial cases (using LLM).
    adversarial_calls = 0
    if config.adversarial_every > 0:
        # Runs at Gen 1, Gen 2... if gen % every == 0
        adversarial_runs = generations // config.adversarial_every
        adversarial_calls = adversarial_runs  # 1 call generates list of cases

    total_llm_calls = total_mutations + adversarial_calls

    # 2. Token Estimation
    # Rough generic estimator: 1 token ~= 4 chars
    # This is conservative for code/technical text but decent for English.
    prompt_len = len(initial_prompt)
    prompt_tokens = math.ceil(prompt_len / 4)

    # Input Tokens per Mutation Call:
    # - System Prompt (~500 tokens for strategies like CoT/Persona)
    # - User Prompt Wrapper (~50 tokens)
    # - The Candidate Text (prompt_tokens)
    # - Failures/Feedback (variable, let's estimate 200 tokens buffer for context)
    avg_input_tokens = 500 + 50 + prompt_tokens + 200

    # Output Tokens per Mutation Call:
    # - JSON Structure (~50 tokens)
    # - The New Prompt (prompt_tokens * 1.2 for variation expansion)
    avg_output_tokens = 50 + math.ceil(prompt_tokens * 1.2)

    # Adversarial Input/Output (usually generates short cases)
    # Input: System (~300) + Prompt (prompt_tokens)
    # Output: JSON cases (~300 tokens)
    adv_input_tokens = 300 + prompt_tokens
    adv_output_tokens = 300

    # 3. Total Token Calculation
    total_input_tokens = (total_mutations * avg_input_tokens) + (
        adversarial_calls * adv_input_tokens
    )
    total_output_tokens = (total_mutations * avg_output_tokens) + (
        adversarial_calls * adv_output_tokens
    )

    # 4. Overheads & Buffer
    # Add 20% buffer for retries, extra feedback context, or token counting errors
    buffer_multiplier = 1.20

    final_input_tokens = total_input_tokens * buffer_multiplier
    final_output_tokens = total_output_tokens * buffer_multiplier

    # 5. Cost Calculation
    cost_input = (final_input_tokens / 1_000_000) * pricing["input"]
    cost_output = (final_output_tokens / 1_000_000) * pricing["output"]

    estimated_cost = cost_input + cost_output

    # Range estimates (tight range since logic is deterministic, but content varies)
    # We'll provide a range based on variability in output length (e.g. +/- 10%)
    min_cost = estimated_cost * 0.90
    max_cost = estimated_cost * 1.10

    # Formatting
    msg = (
        f"Estimated Cost: ${min_cost:.4f} - ${max_cost:.4f} "
        f"({config.model}, {total_llm_calls} calls, ~{int(final_input_tokens + final_output_tokens)} tokens)"
    )

    return {
        "min_cost": round(min_cost, 4),
        "max_cost": round(max_cost, 4),
        "message": msg,
        "details": {
            "total_calls": total_llm_calls,
            "estimated_input_tokens": int(final_input_tokens),
            "estimated_output_tokens": int(final_output_tokens),
        },
    }
