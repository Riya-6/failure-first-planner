"""
Token usage and cost tracker for the Failure-First Planner.
Tracks cumulative spend across all API calls in a session.

Pricing (gpt-4o):
    Input:  $2.50 / 1M tokens
    Output: $10.00 / 1M tokens
"""

INPUT_COST_PER_TOKEN = 2.5 / 1_000_000
OUTPUT_COST_PER_TOKEN = 10.0 / 1_000_000


class CostTracker:
    """Accumulate token counts and compute USD cost estimates."""

    def __init__(self) -> None:
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self._calls: int = 0

    def add(self, usage) -> None:
        """Add token usage from an OpenAI API response's usage object."""
        self.input_tokens += getattr(usage, "prompt_tokens", 0)
        self.output_tokens += getattr(usage, "completion_tokens", 0)
        self._calls += 1

    @property
    def total_usd(self) -> float:
        return (
            self.input_tokens * INPUT_COST_PER_TOKEN
            + self.output_tokens * OUTPUT_COST_PER_TOKEN
        )

    def report(self) -> str:
        return (
            f"API calls: {self._calls} | "
            f"Tokens: {self.input_tokens:,} in / {self.output_tokens:,} out | "
            f"Estimated cost: ${self.total_usd:.4f}"
        )

    def __repr__(self) -> str:
        return f"CostTracker({self.report()})"
