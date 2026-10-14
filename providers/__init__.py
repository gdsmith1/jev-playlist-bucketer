import importlib

PROVIDER_NAMES = ("musicbrainz", "lastfm", "discogs")


def get_provider(name, **kwargs):
    """Instantiate `providers.<name>.Provider` (imported lazily so a broken or
    stubbed provider only fails when selected)."""
    if name not in PROVIDER_NAMES:
        raise SystemExit(f"unknown source {name!r}; valid sources: {', '.join(PROVIDER_NAMES)}")
    module = importlib.import_module(f"providers.{name}")
    return module.Provider(**kwargs)
