from abc import ABC, abstractmethod
from goldenboy.core.budget import Budget
from goldenboy.core.priorities import ExecutionUnit

class ProviderAdapter(ABC):
    """Abstract base class for all agent provider adapters."""
    
    @abstractmethod
    def get_available_budget(self) -> Budget:
        """Fetch and normalize the current available usage/budget."""
        pass
        
    @abstractmethod
    def execute_unit(self, unit: ExecutionUnit) -> bool:
        """
        Execute a single unit of work.
        Returns True if successful, False otherwise.
        """
        pass
