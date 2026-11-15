"""No-op stand-in for `setproctitle` (macOS only).

setproctitle only renames processes in `ps`. On recent macOS releases the C extension segfaults in
forked children once Airflow is imported, which kills every scheduler/webserver/task subprocess.
scripts/setup_local.sh installs this shim on macOS; Linux keeps the real package."""
__version__ = "0.0-noop"
_title = ""


def setproctitle(title):
    global _title
    _title = title


def getproctitle():
    return _title


def setthreadtitle(title):
    pass


def getthreadtitle():
    return ""
