from dbt.adapters.factory import adapter_management
from dbt.cli.flags import Flags
from dbt.config.runtime import load_project, load_profile
from dbt.events.functions import setup_event_logger
from dbt.exceptions import DbtProjectError
from dbt.profiler import profiler
from dbt.tracking import initialize_from_flags, track_run
from click import Context


def preflight(func):
    def wrapper(*args, **kwargs):
        ctx = args[0]
        assert isinstance(ctx, Context)
        ctx.obj = ctx.obj or {}

        # Flags
        flags = Flags(ctx)
        ctx.obj["flags"] = flags

        # Tracking
        initialize_from_flags(flags.ANONYMOUS_USAGE_STATS, flags.PROFILES_DIR)
        ctx.with_resource(track_run(run_command=flags.WHICH))

        # Logging
        # N.B. Legacy logger is not supported
        setup_event_logger(
            flags.LOG_PATH,
            flags.LOG_FORMAT,
            flags.USE_COLORS,
            flags.DEBUG,
        )

        # Profiling
        if flags.RECORD_TIMING_INFO:
            ctx.with_resource(profiler(enable=True, outfile=flags.RECORD_TIMING_INFO))

        # Adapter management
        ctx.with_resource(adapter_management())

        return func(*args, **kwargs)

    return wrapper


def profile(func):
    def wrapper(*args, **kwargs):
        ctx = args[0]
        assert isinstance(ctx, Context)

        if ctx.obj.get("profile") is None:
            flags = ctx.obj["flags"]
            # TODO: Generalize safe access to flags.THREADS:
            # https://github.com/dbt-labs/dbt-core/issues/6259
            threads = getattr(flags, "THREADS", None)
            profile = load_profile(
                flags.PROJECT_DIR, flags.VARS, flags.PROFILE, flags.TARGET, threads
            )
            ctx.obj["profile"] = profile

        return func(*args, **kwargs)

    return wrapper


def project(func):
    def wrapper(*args, **kwargs):
        ctx = args[0]
        assert isinstance(ctx, Context)

        if ctx.obj.get("project") is None:
            # TODO: Decouple target from profile, and remove the need for profile here:
            # https://github.com/dbt-labs/dbt-core/issues/6257
            if not ctx.obj.get("profile"):
                raise DbtProjectError("profile required for project")

            flags = ctx.obj["flags"]
            project = load_project(
                flags.PROJECT_DIR, flags.VERSION_CHECK, ctx.obj["profile"], flags.VARS
            )
            ctx.obj["project"] = project

        return func(*args, **kwargs)

    return wrapper
