from random import randint
from django.db.models import Q
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from db.models import Car, AlertHistory, CommandTimerSetting
import datetime

from tculink.sms import send_using_provider


class Command(BaseCommand):
    help = 'Refresh data periodically'

    def handle_datarefresh(self):
        # Get current time
        now = timezone.now()

        # Find cars that need checking
        timed_out_cars = Car.objects.exclude(periodic_refresh=0, periodic_refresh_running=0).exclude(
            command_requested=True, command_result=-1)

        cars_count = timed_out_cars.count()

        if cars_count == 0:
            self.stdout.write(
                self.style.WARNING("No pending car refreshes found")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Processing {cars_count} cars")
            )

        for car in timed_out_cars:
            try:
                # Set appropriate threshold based on charging status
                if (car.ev_info.charging or car.ev_info.car_running) and car.periodic_refresh_running != 0:
                    period = now - datetime.timedelta(minutes=car.periodic_refresh_running)
                else:
                    if car.periodic_refresh == 0:
                        continue
                    period = now - datetime.timedelta(minutes=car.periodic_refresh)

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

    def handle_timeouts(self):
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

        cars_count = timed_out_cars.count()

        for car in timed_out_cars:
            try:
                # Update car status
                try:
                    cmd = CommandTimerSetting.objects.get(id=car.command_id)
                    cmd.last_command_execution = timezone.now()
                    cmd.last_command_result = 2
                    if cmd.timer_type == 0:
                        cmd.enabled = False
                    cmd.save()
                except CommandTimerSetting.DoesNotExist:
                    ...
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

        if cars_count == 0:
            self.stdout.write(
                self.style.WARNING("No command timeouts found")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Processed {cars_count} command timeouts")
            )

    def handle_command_timers(self):
        try:
            now = timezone.now().utcnow()
            current_weekday = now.weekday()  # 0=Mon, 6=Sun
            one_minute_later = (now + datetime.timedelta(minutes=1)).time()

            # Weekday mapping to model fields
            weekday_fields = {
                0: 'weekday_mon',
                1: 'weekday_tue',
                2: 'weekday_wed',
                3: 'weekday_thu',
                4: 'weekday_fri',
                5: 'weekday_sat',
                6: 'weekday_sun',
            }

            # Get timers that are scheduled for current weekday or specific date
            timers = CommandTimerSetting.objects.filter(
                Q(**{weekday_fields[current_weekday]: True}) |
                Q(date=now.date())
            ).exclude(
                Q(enabled=False) |
                Q(last_command_execution__date=now.date()) |
                Q(
                    last_command_execution__week_day=current_weekday + 1,
                    last_command_execution__day=now.day,
                    last_command_execution__month=now.month,
                    last_command_execution__year=now.year
                )
            )

            timers_count = timers.count()

            if timers_count == 0:
                self.stdout.write(
                    self.style.WARNING("No pending timers found")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Processing {timers_count} timers")
                )

            for timer in timers:
                if (timer.time.hour == one_minute_later.hour and
                        timer.time.minute == one_minute_later.minute):

                    cars = Car.objects.filter(timer_commands=timer.id)

                    for car in cars:
                        try:
                            print(f"Car {car.vin}: Requesting timer {timer.id}, cmd type: {timer.command_type}")
                            try:
                                sms_result = send_using_provider(settings.ACTIVATION_SMS_MESSAGE,
                                                                 car.sms_config)
                                if not sms_result:
                                    raise Exception("Could not send SMS message")
                            except Exception as e:
                                print(f"Could not send SMS message: {e}")
                                print(e)

                            car.command_type = timer.command_type
                            car.command_id = timer.id
                            car.command_requested = True
                            car.command_result = -1
                            car.command_request_time = timezone.now()
                            car.save()

                            timer.last_command_execution = now
                            timer.last_command_result = -1
                            timer.save()
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                      f"Error processing command for Car: {car}, Timer: {timer.name}: {str(e)}"
                                )
                            )
                            timer.last_command_result = 1
                            timer.save()


        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Error in check_command_timers: {str(e)}"
                )
            )


    def handle(self, *args, **options):
        print("Starting data refresh process")
        self.handle_command_timers()
        self.handle_timeouts()
        self.handle_datarefresh()
