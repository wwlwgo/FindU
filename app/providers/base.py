from dataclasses import dataclass


class ProviderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    text: str
    provider: str


class SpeechProvider:
    def transcribe(self, audio: bytes, content_type: str) -> ProviderResult:
        raise NotImplementedError


class LlmProvider:
    def complete(self, prompt: str) -> ProviderResult:
        raise NotImplementedError
