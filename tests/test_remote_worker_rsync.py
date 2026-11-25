from fmd.managers.remote_worker import _only_vanished_sources

# stderr captured from rsync 3.4.1, except the receiver ENOENT line, which follows the
# same mkstemp format with the errno rsync reports when the worker-side folder is gone.

VANISHED = """\
file has vanished: "/tmp/rs/src/f30"
file has vanished: "/tmp/rs/src/f31"
rsync warning: some files vanished before they could be transferred (code 24) at main.c(1356) [sender=3.4.1]
"""

SENDER_MISSING = """\
rsync: [sender] link_stat "/tmp/rs/src/missing" failed: No such file or directory (2)
rsync error: some files/attrs were not transferred (see previous errors) (code 23) at main.c(1356) [sender=3.4.1]
"""

RECEIVER_MISSING = """\
rsync: [receiver] mkstemp "/home/frappe/workspace/release_1/sites/.f1.HmEGf2" failed: No such file or directory (2)
rsync error: some files/attrs were not transferred (see previous errors) (code 23) at main.c(1356) [sender=3.4.1]
"""

# Production, 2026-11-25: root-only config backups on the primary.
UNREADABLE_SOURCE = """\
rsync: [generator] failed to open "/home/frappe/ws/deployment-data/sites/app.godam.io/site_config.json.bak-20261124-1478", continuing: Permission denied (13)
rsync: [generator] failed to set times on "/home/frappe/ws/deployment-data/sites/app.godam.io/site_config.workers.json.bak-20261124-1478": Operation not permitted (1)
rsync: [sender] send_files failed to open "/home/clickhouse/ws/deployment-data/sites/app.godam.io/site_config.json.bak-20261124-1478": Permission denied (13)
rsync error: some files/attrs were not transferred (see previous errors) (code 23) at main.c(1356) [sender=3.2.7]
"""


def test_files_vanishing_mid_copy_do_not_fail_the_sync():
    assert _only_vanished_sources(24, VANISHED)


def test_source_file_missing_at_send_time_does_not_fail_the_sync():
    assert _only_vanished_sources(23, SENDER_MISSING)


def test_missing_file_on_the_worker_side_fails_the_sync():
    assert not _only_vanished_sources(23, RECEIVER_MISSING)


def test_unreadable_source_files_fail_the_sync():
    assert not _only_vanished_sources(23, UNREADABLE_SOURCE)


def test_vanished_and_missing_mixed_with_a_real_error_fails_the_sync():
    assert not _only_vanished_sources(23, SENDER_MISSING + RECEIVER_MISSING)
