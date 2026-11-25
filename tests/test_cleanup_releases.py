from types import SimpleNamespace

from fmd.services.cleanup import CleanupService


def _cleanup(tmp_path, release_names, current, retain_limit):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in release_names:
        (workspace / name).mkdir()
    bench = workspace / "frappe-bench"
    bench.symlink_to(current)

    config = SimpleNamespace(release=SimpleNamespace(releases_retain_limit=retain_limit))
    printer = SimpleNamespace(print=lambda *a, **k: None)
    CleanupService(None, None, config, printer).cleanup_releases(tmp_path, bench)
    return sorted(d.name for d in workspace.iterdir() if d.name.startswith("release_"))


def test_keeps_newest_releases_across_days(tmp_path):
    # Production layout on 2026-11-25: older releases deployed later in the day
    # must not outrank the previous live release.
    remaining = _cleanup(
        tmp_path,
        [
            "release_20261014_161655",
            "release_20261021_172435",
            "release_20261120_124352",
            "release_20261125_060158",
        ],
        current="release_20261125_060158",
        retain_limit=2,
    )

    assert remaining == [
        "release_20261021_172435",
        "release_20261120_124352",
        "release_20261125_060158",
    ]
