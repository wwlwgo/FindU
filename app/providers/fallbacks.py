from app.providers.base import ProviderResult, ProviderUnavailable, SpeechProvider


class UnconfiguredSpeechProvider(SpeechProvider):
    def transcribe(self, audio: bytes, content_type: str) -> ProviderResult:
        raise ProviderUnavailable("Speech provider is not configured")


def transcribe_or_raise(audio: bytes, content_type: str) -> ProviderResult:
    # Audio is intentionally accepted only in memory; callers must not persist it.
    return UnconfiguredSpeechProvider().transcribe(audio, content_type)
