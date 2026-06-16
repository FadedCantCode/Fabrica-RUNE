"""
base.py — Common interface every backend adapter must implement.

A backend's only job is: given a system instruction and a user message,
return the model's text response. The runtime is responsible for everything
about *what* gets asked at each genome step; backends just answer prompts.
"""
from abc import ABC, abstractmethod


class Backend(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.5) -> str:
        """Send one turn to the model and return its text response."""
        raise NotImplementedError
