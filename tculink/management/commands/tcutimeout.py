# your_app/management/commands/check_command_timeouts.py
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from db.models import Car, AlertHistory
import datetime


class Command(BaseCommand):
    help = 'Checks for command timeouts (5+ minutes) and updates status with alerts'

    def handle(self, *args, **options):

        while True:
            # Get current time
            now = timezone.now()
            # Calculate 5 minutes ago
            timeout_threshold = now - datetime.timedelta(minutes=settings.LEAF_COMMAND_TIMEOUT)

            # Find cars with pending commands older than 5 minutes
            timed_out_cars = Car.objects.filter(
                command_requested=True,
                command_result=-1,  # Waiting status
                command_request_time__lte=timeout_threshold
            )

            timeout_count = 0

            for car in timed_out_cars:
                try:
                    # Update car status
                    car.command_requested = False
                    car.command_result = 2  # Timeout status from COMMAND_RESULTS
                    car.save()

                    # Create timeout alert
                    AlertHistory.objects.create(
                        type=98,  # Command timeout from ALERT_TYPES
                        command_id=car.command_id,
                        car=car,
                        additional_data=f"Command '{car.get_command_type_display()}' timed out after 5 minutes"
                    )

                    timeout_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Processed timeout for car VIN: {car.vin} - Command: {car.get_command_type_display()}"
                        )
                    )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error processing car VIN: {car.vin}: {str(e)}"
                        )
                    )

            if timeout_count == 0:
                self.stdout.write(
                    self.style.WARNING("No command timeouts found")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Processed {timeout_count} command timeouts")
                )

            time.sleep(5)