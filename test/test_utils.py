"""Tests for Spinal Tap utility functions."""

from spinal_tap import app
from spinal_tap.callbacks import validate_file_access
from spinal_tap.utils import (
    canonicalize_data_path,
    classify_source,
    clear_data_caches,
    get_data_cache_info,
    get_data_path_candidates,
    get_file_signature,
    get_reader_products,
    initialize_reader,
    load_data,
    resolve_data_path,
    resolve_reader_keys,
    resolve_source_path,
)


def test_get_reader_products_uses_writer_configuration():
    """Capability discovery should avoid loading an event when metadata exists."""

    class Reader:
        cfg = {"io": {"writer": {"keys": ["truth_particles", "points"]}}}

    assert get_reader_products(Reader()) == {"truth_particles", "points"}


def test_canonicalize_data_path():
    """S3DF paths should canonicalize to their container equivalents."""
    assert canonicalize_data_path("/data/2x2/file.h5") == "/data/2x2/file.h5"
    assert (
        canonicalize_data_path("/sdf/data/neutrino/2x2/file.h5") == "/data/2x2/file.h5"
    )
    assert canonicalize_data_path("/sdf/data/other/file.h5") == (
        "/sdf/data/other/file.h5"
    )
    assert canonicalize_data_path("https://example.org/file.h5") == (
        "https://example.org/file.h5"
    )
    assert canonicalize_data_path("/sdf/data/neutrino") == "/data"


def test_get_data_path_candidates():
    """Both aliases should be considered with the user path first."""
    assert get_data_path_candidates(" /data/2x2/*.h5 ") == [
        "/data/2x2/*.h5",
        "/sdf/data/neutrino/2x2/*.h5",
    ]
    assert get_data_path_candidates("/sdf/data/neutrino/2x2/*.h5") == [
        "/sdf/data/neutrino/2x2/*.h5",
        "/data/2x2/*.h5",
    ]
    assert get_data_path_candidates("relative/*.h5") == ["relative/*.h5"]
    assert get_data_path_candidates("/data") == ["/data", "/sdf/data/neutrino"]
    assert get_data_path_candidates("/sdf/data/neutrino") == [
        "/sdf/data/neutrino",
        "/data",
    ]


def test_resolve_data_path_uses_alias(monkeypatch):
    """Resolution should fall back through either alias direction."""
    matches = {"/data/2x2/file.h5": ["/data/2x2/file.h5"]}
    monkeypatch.setattr("spinal_tap.utils.glob.glob", matches.get)

    assert resolve_data_path("/sdf/data/neutrino/2x2/file.h5") == "/data/2x2/file.h5"

    matches.clear()
    matches["/sdf/data/neutrino/2x2/file.h5"] = ["/sdf/data/neutrino/2x2/file.h5"]
    assert resolve_data_path("/data/2x2/file.h5") == "/sdf/data/neutrino/2x2/file.h5"


def test_resolve_data_path_prefers_user_path(monkeypatch):
    """Resolution should preserve the supplied form when both forms exist."""
    monkeypatch.setattr("spinal_tap.utils.glob.glob", lambda path: [path])

    path = "/sdf/data/neutrino/2x2/file.h5"
    assert resolve_data_path(path) == path


def test_resolve_data_path_preserves_missing_expression(monkeypatch):
    """Missing sources should retain the user's preferred spelling."""
    monkeypatch.setattr("spinal_tap.utils.glob.glob", lambda path: [])
    assert resolve_data_path("/data/missing.h5") == "/data/missing.h5"


def test_validate_file_access_accepts_both_aliases(monkeypatch):
    """Authorization should grant the same access through either alias."""
    monkeypatch.setattr(app, "REQUIRE_AUTH", True)
    monkeypatch.setattr(app, "SHARED_FOLDERS", [])
    monkeypatch.setattr(app, "EXPERIMENT_PATHS", {"dune": ["/data/2x2"]})
    monkeypatch.setattr(app, "get_experiment", lambda: "dune")

    assert validate_file_access("/data/2x2/file.h5") == (True, None)
    assert validate_file_access("/sdf/data/neutrino/2x2/file.h5") == (True, None)
    assert validate_file_access("/sdf/data/neutrino/icarus/file.h5")[0] is False


def test_initialize_reader_cache_invalidates_on_file_change(monkeypatch, tmp_path):
    """Unchanged files should reuse readers and changed files should not."""
    path = tmp_path / "events.h5"
    path.write_bytes(b"first")
    calls = []

    def make_reader(*args, **kwargs):
        reader = object()
        calls.append((args, kwargs, reader))
        return reader

    clear_data_caches()
    monkeypatch.setattr("spinal_tap.utils.HDF5Reader", make_reader)
    first = initialize_reader(str(path))
    second = initialize_reader(str(path))
    assert first is second
    assert len(calls) == 1

    path.write_bytes(b"second version")
    third = initialize_reader(str(path))
    assert third is not first
    assert len(calls) == 2
    clear_data_caches()


def test_load_data_cache_reuses_built_event(monkeypatch):
    """Repeated presentation updates should reuse one built event."""

    class Reader:
        cfg = {"geo": {"detector": "2x2"}}

        def __init__(self):
            self.calls = 0

        def get(self, entry):
            self.calls += 1
            return {"index": entry}

    class Builder:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, data):
            data["built"] = True

    reader = Reader()
    clear_data_caches()
    monkeypatch.setattr("spinal_tap.utils.BuildManager", Builder)
    first = load_data(reader, 3, "both", "particles")
    second = load_data(reader, 3, "both", "particles")

    assert first is second
    assert first[0] == {"index": 3, "built": True}
    assert reader.calls == 1
    clear_data_caches()


def test_load_data_returns_run_metadata(monkeypatch):
    """Uncached event loading should expose geometry and run information."""

    class Reader:
        cfg = {"geo": {"detector": "2x2"}}

        def get(self, entry):
            run_info = type("RunInfo", (), {"run": 1, "subrun": 2, "event": 3})()
            return {"run_info": run_info}

    calls = []

    class Builder:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def __call__(self, data):
            data["built"] = True

    clear_data_caches()
    monkeypatch.setattr("spinal_tap.utils.BuildManager", Builder)
    data, geo, run, subrun, event = load_data(Reader(), 0, "truth", "interactions")
    assert data["built"] is True
    assert geo == {"detector": "2x2"}
    assert (run, subrun, event) == (1, 2, 3)
    assert calls == [((False, True, True), {"mode": "truth"})]
    assert get_data_cache_info()["events"].currsize == 1
    clear_data_caches()


def test_resolve_url_and_reader_source_kinds(monkeypatch, tmp_path):
    """URLs, JSON views, globs and missing paths should dispatch correctly."""
    monkeypatch.setattr(
        "spinal_tap.cache.cache_manager.fetch_url", lambda url: "/tmp/download.h5"
    )
    assert resolve_source_path(" https://example.org/a.h5 ") == "/tmp/download.h5"

    view = tmp_path / "view.any"
    view.write_text('{"version": 1}')
    try:
        resolve_reader_keys(str(view))
    except ValueError as error:
        assert "not an HDF5" in str(error)
    else:
        raise AssertionError("JSON view accepted as reader input")

    missing = str(tmp_path / "missing.h5")
    assert classify_source(missing) == ("hdf5", missing)
    glob_path = str(tmp_path / "*.h5")
    assert classify_source(glob_path) == ("hdf5", glob_path)

    local = tmp_path / "local.h5"
    local.write_bytes(b"x")
    manifest = tmp_path / "mixed.list"
    manifest.write_text(f"{local}\nhttps://example.org/remote.h5\n")
    monkeypatch.setattr(
        "spinal_tap.utils.resolve_source_path",
        lambda source: "/tmp/remote.h5" if source.startswith("http") else source,
    )
    keys, _ = resolve_reader_keys(str(manifest))
    assert keys == (str(local), "/tmp/remote.h5")


def test_reader_products_fall_back_to_hdf5_metadata(monkeypatch, tmp_path):
    """Legacy reader products should be intersected across local input files."""
    import h5py

    first = tmp_path / "first.h5"
    second = tmp_path / "second.h5"
    for path, extra in ((first, "reco_particles"), (second, "truth_particles")):
        with h5py.File(path, "w") as output:
            output.create_group("events")
            output.create_group("points")
            output.create_group(extra)

    class Reader:
        cfg = None
        file_paths = [str(first), str(second)]

        @staticmethod
        def is_remote_path(path):
            return False

    assert get_reader_products(Reader()) == {"points"}

    Reader.file_paths = ["remote://file"]
    Reader.is_remote_path = staticmethod(lambda path: True)
    products = get_reader_products(Reader())
    assert {"reco_particles", "truth_particles", "flashes", "crthits"}.issubset(
        products
    )

    Reader.file_paths = [str(tmp_path / "missing.h5")]
    Reader.is_remote_path = staticmethod(lambda path: False)
    products = get_reader_products(Reader())
    assert "reco_interactions" in products


def test_get_file_signature(tmp_path):
    """File signatures should include every sorted glob match."""
    first = tmp_path / "a.h5"
    second = tmp_path / "b.h5"
    first.write_bytes(b"a")
    second.write_bytes(b"bb")

    signature = get_file_signature(str(tmp_path / "*.h5"))
    assert [record[0] for record in signature] == [str(first), str(second)]
    assert [record[1] for record in signature] == [1, 2]


def test_content_detected_manifest_supports_arbitrary_extension(tmp_path):
    """Manifest dispatch should depend on content rather than a .txt suffix."""
    first = tmp_path / "a.h5"
    second = tmp_path / "b.h5"
    first.write_bytes(b"a")
    second.write_bytes(b"bb")
    manifest = tmp_path / "events.list"
    manifest.write_text("# inputs\na.h5\n\nb.h5\n")

    kind, resolved = classify_source(str(manifest))
    keys, signature = resolve_reader_keys(str(manifest))

    assert kind == "manifest"
    assert resolved == str(manifest)
    assert keys == (str(first), str(second))
    assert [record[0] for record in signature] == [
        str(manifest),
        str(first),
        str(second),
    ]


def test_content_detection_does_not_assume_txt_is_a_manifest(tmp_path):
    """An HDF5 source should stay HDF5 even when its suffix says text."""
    import h5py

    source = tmp_path / "misleading.txt"
    with h5py.File(source, "w") as output:
        output.create_dataset("events", data=[0])

    kind, resolved = classify_source(str(source))

    assert kind == "hdf5"
    assert resolved == str(source)
    keys, signature = resolve_reader_keys(str(source))
    assert keys == (str(source),)
    assert signature[0][0] == str(source)
