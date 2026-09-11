import os
from openai import OpenAI
from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.budget import Budget
from goldenboy.core.priorities import ExecutionUnit

class OpenAIAdapter(ProviderAdapter):
    """
    Adapter for OpenAI models. 
    It estimates budget based on the user's allocated usage limit or rate limits
    by intercepting API response headers (x-ratelimit-remaining-tokens).
    """
    
    def __init__(self, api_key: str = None, safety_margin: float = 3.0):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIAdapter")
            
        self.client = OpenAI(api_key=self.api_key)
        self.safety_margin = safety_margin
        
        # In a real dynamic scenario, this is updated after every API call
        self._current_remaining_tokens = 100000  # Default assumption
        self._total_allowed_tokens = 100000
        
    def _update_limits_from_headers(self, headers):
        """Parse x-ratelimit headers to update budget state."""
        remaining = headers.get("x-ratelimit-remaining-tokens")
        total = headers.get("x-ratelimit-limit-tokens")
        
        if remaining and total:
            self._current_remaining_tokens = float(remaining)
            self._total_allowed_tokens = float(total)

    def get_available_budget(self) -> Budget:
        # Calculate percentage based on tracked tokens
        percentage = (self._current_remaining_tokens / self._total_allowed_tokens) * 100.0 if self._total_allowed_tokens > 0 else 100.0
        
        return Budget(
            remaining_percentage=percentage,
            total_allowed=self._total_allowed_tokens,
            safety_margin=self.safety_margin
        )
        
    def execute_unit(self, unit: ExecutionUnit) -> bool:
        """
        Executes a single unit of work using OpenAI.
        In a real agent framework, this would yield to the agent's actual LLM generation function.
        Here we simulate it for demonstration while showcasing the header interception.
        """
        # Mocking an actual API call to demonstrate header interception
        try:
            response = self.client.chat.completions.with_raw_response.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Execute task: {unit.description}"}],
                max_tokens=10
            )
            # Intercept headers
            self._update_limits_from_headers(response.headers)
            
            return True
        except Exception as e:
            print(f"OpenAI execution failed: {e}")
            return False
