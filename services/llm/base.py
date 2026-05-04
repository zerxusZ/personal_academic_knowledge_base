from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    async def chat(self, system: str, user: str) -> str: ...

    @abstractmethod
    def available(self) -> bool: ...
