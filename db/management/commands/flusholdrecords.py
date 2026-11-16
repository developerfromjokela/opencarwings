import fcntl
import logging
import os
import tempfile
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

logger = logging.getLogger(__name__)

from db.models import *

class Command(BaseCommand):
    help = "Delete historical data after a certain time"

    def get_purge_querysets(self, now, days):
        normal_factor = now - timedelta(days=days)
        higher_factor = now - timedelta(days=int(days*2))
        important_factor = now - timedelta(days=int(days*3))
        return [
            ("CRMExcessiveAirconRecord", CRMExcessiveAirconRecord.objects.filter(start__lt=normal_factor)),
            ("CRMExcessiveIdlingRecord", CRMExcessiveIdlingRecord.objects.filter(start__lt=normal_factor)),
            ("CRMABSHistoryRecord", CRMABSHistoryRecord.objects.filter(timestamp__lt=normal_factor)),
            ("CRMTroubleRecord", CRMTroubleRecord.objects.filter(created_at__lt=normal_factor)),
            ("CRMDistanceRecord", CRMDistanceRecord.objects.filter(timestamp__lt=important_factor)),
            ("CRMMSNRecord", CRMMSNRecord.objects.filter(timestamp__lt=normal_factor)),
            ("CRMChargeRecord", CRMChargeRecord.objects.filter(start_time__lt=higher_factor)),
            ("CRMChargeHistoryRecord", CRMChargeHistoryRecord.objects.filter(start_time__lt=important_factor)),
            ("CRMTripRecord", CRMTripRecord.objects.filter(start_ts__lt=important_factor)),
            ("DOTFile", DOTFile.objects.filter(upload_ts__lt=higher_factor)),
        ]

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, help="Retention period in days")
        parser.add_argument("--batch-size", type=int, help="deletion batch size")
        parser.add_argument("--sleep", type=float, help="seconds to sleep between batches")
        parser.add_argument(
            "--max-runtime", type=int,
            help="stop after this many seconds (remaining rows are purged next run)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Only report how many rows would be deleted.",
        )

    def handle(self, *args, **options):
        days = options["days"] or getattr(settings, "PURGE_PERIOD_DAYS", None)
        if days is None:
            self.stdout.write("Purge disabled, use --days to override settings.py")
            return
        batch_size = options["batch_size"] or getattr(settings, "PURGE_BATCH_SIZE", 5000)
        sleep_s = (
            options["sleep"] if options["sleep"] is not None
            else getattr(settings, "PURGE_SLEEP_SECONDS", 0.2)
        )
        max_runtime = options["max_runtime"] or getattr(settings, "PURGE_MAX_RUNTIME_SECONDS", 60*30)
        dry_run = options["dry_run"]

        if days <= 0 or batch_size <= 0:
            raise CommandError("--days and --batch-size must be positive.")

        lock_file = open(os.path.join(tempfile.gettempdir(), "purge_historical_data.lock"), "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stdout.write("purge lockfile is present, another process still running?")
            return

        try:
            deadline = time.monotonic() + max_runtime if max_runtime else None
            self.stdout.write(f"Purging data older than ({days} days){' [DRY RUN]' if dry_run else ''}")

            targets = self.get_purge_querysets(timezone.now(), days)
            if not targets:
                raise CommandError("No purge querysets defined in get_purge_querysets().")

            failures = []
            total = 0
            for label, qs in targets:
                try:
                    total += self._purge_queryset(
                        label, qs, batch_size, sleep_s, deadline, dry_run
                    )
                except Exception:
                    logger.exception("Purge failed for %s", label)
                    failures.append(label)

                if deadline and time.monotonic() >= deadline:
                    self.stdout.write("Max runtime reached; stopping. Will continue next run.")
                    break

            verb = "Would delete" if dry_run else "Deleted"
            self.stdout.write(self.style.SUCCESS(f"{verb} {total} rows in total."))

            if failures:
                raise CommandError(f"Purge failed for: {', '.join(failures)}")
        except Exception as e:
            logger.exception("Purge failed")
            logger.exception(e)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

    def _purge_queryset(self, label, qs, batch_size, sleep_s, deadline, dry_run):
        model = qs.model

        if dry_run:
            count = qs.count()
            self.stdout.write(f"  {label}: {count} rows would be deleted")
            return count

        deleted_total = 0
        while True:
            if deadline and time.monotonic() >= deadline:
                break

            close_old_connections()

            pks = list(qs.order_by("pk").values_list("pk", flat=True)[:batch_size])
            if not pks:
                break

            count, _ = model._default_manager.filter(pk__in=pks).delete()
            deleted_total += count
            logger.info("%s: deleted %s (running total %s)", label, count, deleted_total)

            if len(pks) < batch_size:
                break
            if sleep_s:
                time.sleep(sleep_s)

        self.stdout.write(f"  {label}: deleted {deleted_total} rows")
        return deleted_total