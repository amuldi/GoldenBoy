import os
from anthropic import Anthropic
from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.budget import Budget
from goldenboy.core.priorities import ExecutionUnit

class AnthropicAdapter(ProviderAdapter):
    """
    Adapter for Anthropic Claude models.
    Parses anthropic-ratelimit-tokens-remaining headers.
    """
    
    def __init__(self, api_key: str = None, safety_margin: float = 3.0):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for AnthropicAdapter")
            
        self.client = Anthropic(api_key=self.api_key)
        self.safety_margin = safety_margin
        
        self._current_remaining_tokens = 100000
        self._total_allowed_tokens = 100000
        
    def _update_limits_from_headers(self, response):
        """Parse anthropic ratelimit headers to update budget state."""
        # Anthropic exposes headers in response.headers
        remaining = response.headers.get("anthropic-ratelimit-tokens-remaining")
        total = response.headers.get("anthropic-ratelimit-tokens-limit")
        
        if remaining and total:
            self._current_remaining_tokens = float(remaining)
            self._total_allowed_tokens = float(total)

    def get_available_budget(self) -> Budget:
        percentage = (self._current_remaining_tokens / self._total_allowed_tokens) * 100.0 if self._total_allowed_tokens > 0 else 100.0
        return Budget(
            remaining_percentage=percentage,
            total_allowed=self._total_allowed_tokens,
            safety_margin=self.safety_margin
        )
        
    def execute_unit(self, unit: ExecutionUnit) -> bool:
        try:
            # Using raw_response to access headers easily
            response = self.client.messages.with_raw_response.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": f"Execute task: {unit.description}"}]
            )
            self._update_limits_from_headers(response)
            return True
        except Exception as e:
            print(f"Anthropic execution failed: {e}")
            return False
