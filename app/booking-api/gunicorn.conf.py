"""Gunicorn settings that expose Prometheus metrics for every worker.

Why this file exists: this service runs several gunicorn workers. Each worker
is its own process, so a normal in-process counter would show only the worker
that happened to answer the scrape, and the numbers would jump around. Here
every worker writes its counters to small files in PROMETHEUS_MULTIPROC_DIR
and the master process adds them up, so one scrape shows the whole pod.

The metrics are served on their own port (METRICS_PORT, default 9102), never
on the application port. The gateway does not route to it, so it is not
reachable from the internet. Only a NetworkPolicy allow in the cluster lets
Prometheus reach it. The worker count is NOT changed by this file.
"""
import os

# Must be set before prometheus_client is imported anywhere (master or worker).
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus-multiproc")

from prometheus_client import CollectorRegistry, multiprocess, start_http_server  # noqa: E402

_DIR = os.environ["PROMETHEUS_MULTIPROC_DIR"]
_PORT = int(os.environ.get("METRICS_PORT", "9102"))


def on_starting(server):
    # Start from an empty directory so counters of an earlier run are not mixed in.
    os.makedirs(_DIR, exist_ok=True)
    for name in os.listdir(_DIR):
        if name.endswith(".db"):
            os.remove(os.path.join(_DIR, name))


def when_ready(server):
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    start_http_server(_PORT, registry=registry)


def child_exit(server, worker):
    # A worker that exited stops reporting live gauges; its counters stay.
    multiprocess.mark_process_dead(worker.pid)
