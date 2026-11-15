"""macOS only (installed into the venv by scripts/setup_local.sh).

Python defaults to the 'spawn' start method on macOS, but Airflow 2.10's LocalExecutor workers can only be
forked (AttributeError: 'QueuedLocalWorker' object has no attribute 'wrapper'). Airflow's own
`core.mp_start_method` option does not reach the LocalExecutor, so the global default is set here
whenever scripts/airflow_env.sh has exported AIRFLOW__CORE__MP_START_METHOD."""
import os

_method = os.environ.get("AIRFLOW__CORE__MP_START_METHOD")
if _method:
    import multiprocessing

    try:
        multiprocessing.set_start_method(_method, force=True)
    except (RuntimeError, ValueError):
        pass
