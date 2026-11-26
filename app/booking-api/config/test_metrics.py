"""Proves the metrics setup with a real multi-worker gunicorn, not a mock.

Starts the service exactly as the entrypoint does (gunicorn.conf.py, 2 workers),
sends a known number of requests, then checks that the separate metrics port
reports ALL of them (the workers' counters are added together) and that the
metrics are not reachable on the normal application port.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from django.test import SimpleTestCase

BASE = Path(__file__).resolve().parent.parent
PROBE_PATH = '__PROBE__'
REQUESTS = 40


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class MultiWorkerMetricsTest(SimpleTestCase):
    def test_two_workers_report_one_consistent_total(self):
        try:
            import gunicorn  # noqa: F401
        except ImportError:
            self.skipTest('gunicorn is not installed')
        from prometheus_client.parser import text_string_to_metric_families

        app_port, metrics_port = _free_port(), _free_port()
        tmp = tempfile.mkdtemp()
        env = dict(os.environ, DB_ENGINE='sqlite', DB_PATH=os.path.join(tmp, 'db.sqlite3'),
                   WEB_DB_PATH=os.path.join(tmp, 'web.sqlite3'), SECRET_KEY='metrics-test',
                   ALLOWED_HOSTS='127.0.0.1,localhost', METRICS_PORT=str(metrics_port),
                   PROMETHEUS_MULTIPROC_DIR=os.path.join(tmp, 'prom'))
        proc = subprocess.Popen(
            [sys.executable, '-m', 'gunicorn', '-c', 'gunicorn.conf.py', 'config.wsgi:application',
             '--bind', f'127.0.0.1:{app_port}', '--workers', '2'],
            cwd=BASE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 30
            while True:
                try:
                    _get(f'http://127.0.0.1:{metrics_port}/metrics')
                    _get(f'http://127.0.0.1:{app_port}/{PROBE_PATH}')
                    break
                except (urllib.error.URLError, ConnectionError, OSError):
                    if time.time() > deadline:
                        self.fail('gunicorn did not start')
                    time.sleep(0.3)
            for _ in range(REQUESTS):
                _get(f'http://127.0.0.1:{app_port}/{PROBE_PATH}')
            status, body = _get(f'http://127.0.0.1:{metrics_port}/metrics')
            self.assertEqual(status, 200)
            total = 0.0
            for family in text_string_to_metric_families(body):
                if family.name == 'django_http_responses_total_by_status':
                    total = sum(s.value for s in family.samples if s.name.endswith('_total'))
            # +1 for the readiness probe request above; every worker is included.
            self.assertEqual(total, REQUESTS + 1)
            # Metrics must not be served on the application port.
            self.assertEqual(_get(f'http://127.0.0.1:{app_port}/metrics')[0], 404)
            # Nothing in the exposed metrics carries request paths or personal data.
            self.assertNotIn(PROBE_PATH, body)
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
            shutil.rmtree(tmp, ignore_errors=True)
