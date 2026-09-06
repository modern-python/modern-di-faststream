import types

import modern_di_faststream


def test_public_surface_is_exactly_the_four_documented_names() -> None:
    """INVARIANT: the package exports exactly the four names ``README.md`` documents as its API.

    Broken by promoting a helper to a public name, in ``__all__`` or as an unprefixed binding
    in ``__init__`` -- the latter is public whether or not it was meant to be. The middleware
    factory, the middleware, and the ``Dependency`` seam are deliberately private: every name
    added here is one a major release has to keep working, and an adapter whose surface grows
    stops being reviewable against FastStream's own API. The surface is the only place that
    cost is visible before it is paid.
    """
    public = sorted(
        name
        for name, value in vars(modern_di_faststream).items()
        if not name.startswith("_") and not isinstance(value, types.ModuleType)
    )

    assert public == ["FromDI", "faststream_message_provider", "fetch_di_container", "setup_di"]
    assert modern_di_faststream.__all__ == public
