import fcntl
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger("cron")

JOBS = ["tcuperiodicupdate", "datasync", "flushexpiredtokens", "flushexpiredtransfers"]


def _run(name):
    try:
        call_command(name)
    except Exception as e:
        logger.exception("cron: %s failed, %s", name, e)
    finally:
        connection.close()


class Command(BaseCommand):
    help = "Single per-minute entry point"
    requires_system_checks = []

    def handle(self, *args, **options):
        lock = open(os.path.join(tempfile.gettempdir(), "cron_tick.lock"), "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stdout.write("previous tick still running, skipping")
            return
        try:
            with ThreadPoolExecutor(max_workers=len(JOBS)) as pool:
                list(pool.map(_run, JOBS))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()