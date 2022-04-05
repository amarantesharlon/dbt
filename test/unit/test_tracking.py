import dbt.tracking
import datetime
import shutil
import tempfile
import unittest

_INITIALIZE_FROM_FLAGS_TEST_CASES = [
    (True, True, True),
    (True, False, True),
    (False, True, False),
    (False, False, True),
]


class TestTracking(unittest.TestCase):
    def setUp(self):
        dbt.tracking.active_user = None
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        dbt.tracking.active_user = None
        shutil.rmtree(self.tempdir)

    def test_tracking_initial(self):
        assert dbt.tracking.active_user is None
        dbt.tracking.initialize_tracking(self.tempdir)
        assert isinstance(dbt.tracking.active_user, dbt.tracking.User)

        invocation_id = dbt.tracking.active_user.invocation_id
        run_started_at = dbt.tracking.active_user.run_started_at

        assert dbt.tracking.active_user.do_not_track is False
        assert isinstance(dbt.tracking.active_user.id, str)
        assert isinstance(invocation_id, str)
        assert isinstance(run_started_at, datetime.datetime)

        dbt.tracking.disable_tracking()
        assert isinstance(dbt.tracking.active_user, dbt.tracking.User)

        assert dbt.tracking.active_user.do_not_track is True
        assert dbt.tracking.active_user.id is None
        assert dbt.tracking.active_user.invocation_id == invocation_id
        assert dbt.tracking.active_user.run_started_at == run_started_at

        # this should generate a whole new user object -> new run_started_at
        dbt.tracking.do_not_track()
        assert isinstance(dbt.tracking.active_user, dbt.tracking.User)

        assert dbt.tracking.active_user.do_not_track is True
        assert dbt.tracking.active_user.id is None
        assert isinstance(dbt.tracking.active_user.invocation_id, str)
        assert isinstance(dbt.tracking.active_user.run_started_at, datetime.datetime)
        # invocation_id no longer only linked to active_user so it doesn't change
        assert dbt.tracking.active_user.invocation_id == invocation_id
        # if you use `!=`, you might hit a race condition (especially on windows)
        assert dbt.tracking.active_user.run_started_at is not run_started_at

    def test_tracking_never_ok(self):
        assert dbt.tracking.active_user is None

        # this should generate a whole new user object -> new invocation_id/run_started_at
        dbt.tracking.do_not_track()
        assert isinstance(dbt.tracking.active_user, dbt.tracking.User)

        assert dbt.tracking.active_user.do_not_track is True
        assert dbt.tracking.active_user.id is None
        assert isinstance(dbt.tracking.active_user.invocation_id, str)
        assert isinstance(dbt.tracking.active_user.run_started_at, datetime.datetime)

    def test_disable_never_enabled(self):
        assert dbt.tracking.active_user is None

        # this should generate a whole new user object -> new invocation_id/run_started_at
        dbt.tracking.disable_tracking()
        assert isinstance(dbt.tracking.active_user, dbt.tracking.User)

        assert dbt.tracking.active_user.do_not_track is True
        assert dbt.tracking.active_user.id is None
        assert isinstance(dbt.tracking.active_user.invocation_id, str)
        assert isinstance(dbt.tracking.active_user.run_started_at, datetime.datetime)

    def test_initialize_from_flags(self):
        for (
            do_not_track,
            send_aonymous_usage_stats,
            expected,
        ) in _INITIALIZE_FROM_FLAGS_TEST_CASES:
            with self.subTest(
                do_not_track=do_not_track,
                send_aonymous_usage_stats=send_aonymous_usage_stats,
                expected=expected,
            ):
                dbt.tracking.flags.DO_NOT_TRACK = do_not_track
                dbt.tracking.flags.SEND_ANONYMOUS_USAGE_STATS = (
                    send_aonymous_usage_stats
                )

                dbt.tracking.initialize_from_flags()

                assert dbt.tracking.active_user.do_not_track == expected
