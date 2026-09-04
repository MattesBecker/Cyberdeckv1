import logging
from typing import Iterable, Tuple

from .base import LibraryProvider, LibraryProviderError


logger = logging.getLogger(__name__)


class LibraryProviderRegistry:
    """Resolve configured providers by stable provider key."""

    def __init__(self, providers: Iterable[LibraryProvider]) -> None:
        provider_map = {}
        for provider in providers:
            if not provider.key or not provider.title:
                raise LibraryProviderError(
                    "Library providers require a key and title."
                )
            if provider.key in provider_map:
                raise LibraryProviderError(
                    "Duplicate library provider: {0}".format(provider.key)
                )
            provider_map[provider.key] = provider
        self._providers = provider_map

    def list_providers(self) -> Tuple[LibraryProvider, ...]:
        return tuple(self._providers.values())

    def get(self, provider_key: str) -> LibraryProvider:
        try:
            return self._providers[provider_key]
        except KeyError as exc:
            raise LibraryProviderError(
                "Unknown library provider: {0}".format(provider_key)
            ) from exc

    def close(self) -> None:
        """Close all providers without preventing the remaining cleanup."""
        for provider in self._providers.values():
            try:
                provider.close()
            except Exception as exc:
                logger.warning(
                    "Could not close library provider %s: %s",
                    provider.key,
                    exc,
                )
