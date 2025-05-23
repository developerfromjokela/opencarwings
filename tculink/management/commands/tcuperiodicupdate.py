import time
from random import randint
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from db.models import Car, AlertHistory
import datetime

from tculink.sms import send_using_provider


class Command(BaseCommand):
    help = 'Refresh data periodically'

    def handle(self, *args, **options):
        print("Starting data refresh process")
        # Get current time
        now = timezone.now()

        # Find cars that need checking
        timed_out_cars = Car.objects.all()

        for car in timed_out_cars:
            try:
                # Set appropriate threshold based on charging status
                if (car.ev_info.charging or car.ev_info.car_running) and car.periodic_refresh_running != 0:
                    period = now - datetime.timedelta(minutes=car.periodic_refresh_running)
                else:
                    if car.periodic_refresh == 0:
                        continue
                    period = now - datetime.timedelta(minutes=car.periodic_refresh)

                # Skip if there's an ongoing request
                if car.command_requested or car.command_result == -1:
                    print(f"Car {car.vin}: Ongoing request, skipping")
                    continue

                if car.command_result == 2 and car.command_request_time > period:
                    print(f"Car {car.vin}: Last command timed out, wait for period")
                    continue

                # Check if update is actually needed
                if car.last_connection is not None and car.last_connection < period:
                    print(f"Car {car.vin}: Requesting update")
                    try:
                        sms_result = send_using_provider(settings.ACTIVATION_SMS_MESSAGE,
                                                         car.sms_config)
                        if not sms_result:
                            raise Exception("Could not send SMS message")
                    except Exception as e:
                        print(f"Could not send SMS message: {e}")
                        print(e)

                    # Update car status
                    car.command_type = 1
                    car.command_id = randint(10000, 99999)
                    car.command_requested = True
                    car.command_result = -1
                    car.command_request_time = timezone.now()
                    car.save()

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing car VIN: {car.vin}: {str(e)}"
                    )
                )
