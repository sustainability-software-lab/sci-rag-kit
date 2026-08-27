"""The documented public API surface must keep importing from the top level."""

import sci_rag


def test_version_is_exposed() -> None:
    assert sci_rag.__version__


def test_every_lazy_export_resolves() -> None:
    for name in sci_rag.__all__:
        assert getattr(sci_rag, name) is not None, name


def test_unknown_attribute_raises_attribute_error() -> None:
    import pytest

    with pytest.raises(AttributeError, match="no attribute 'nope'"):
        _ = sci_rag.nope


def test_dir_lists_exports() -> None:
    listing = dir(sci_rag)
    for name in ("Retriever", "AnswerEngine", "RetrievalScope", "create_app"):
        assert name in listing


def test_py_typed_marker_ships() -> None:
    from pathlib import Path

    assert (Path(sci_rag.__file__).parent / "py.typed").exists()
