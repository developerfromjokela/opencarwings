from random import randint
from django.db.models import Q
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from db.models import Car, AlertHistory, CommandTimerSetting
import datetime
import logging

from tculink.coordinators.stub import send_command_using_provider

logger = logging.getLogger(__name__)

# Hardcoded A/C timeout assumptions (minutes) per review feedback.
# Only relevant for ficosa2016 TCU; continental is skipped altogether.
# Values are intentionally set slightly above the car's own auto-off threshold
# (15 min unplugged / 45 min plugged) to avoid assuming AC is off right before
# the car would have turned it off itself.
AC_ASSUME_OFF_TIMEOUT_UNPLUGGED = 16   # 15 min + threshold when unplugged
AC_ASSUME_OFF_TIMEOUT_PLUGGED = 46     # 45 min + threshold while plugged


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

                if car.command_result == 2 and car.command_request_time is not None and car.command_request_time > period:
                    print("Skip car, last execution timed out.")
                    continue

                # Check if update is actually needed
                if car.last_connection is not None and car.last_connection < period:
                    print(f"Car {car.vin}: Requesting update")
                    try:
                        car = send_command_using_provider(1, None, car)
                    except Exception as e:
                        print(f"Could not send SMS message: {e}")
                        print(e)

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
        # Add 3 minutes of response wait time
        resp_timeout_threshold = now - datetime.timedelta(minutes=settings.LEAF_COMMAND_TIMEOUT+3)

        # Find cars with pending commands older than 5 minutes
        timed_out_cars = Car.objects.filter(
            command_requested=True,
            command_result=-1,  # Waiting status
            command_request_time__lte=timeout_threshold
        )

        # Find cars who wait for response
        failed_resp_cars = Car.objects.filter(
            command_result=3,  # Await response status
            command_request_time__lte=resp_timeout_threshold
        )

        all_failed_cars = timed_out_cars.union(failed_resp_cars)

        cars_count = all_failed_cars.count()

        for car in all_failed_cars:
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
                car.save(update_fields=["command_requested", "command_result"])

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
                                car = send_command_using_provider(timer.command_type, {"timer": timer.id}, car)
                            except Exception as e:
                                print(f"Could not send SMS message: {e}")
                                print(e)

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


    def handle_ac_timeout_assumption(self):
        """Assume A/C has turned itself off after a hardcoded timeout of silence.

        Only relevant for ficosa2016 TCU; continental is skipped altogether.

        When the timeout fires, A/C is assumed off (ac_status=False,
        ac_last_started=None) and a refresh command (type 1) is attempted via
        SMS to retrieve the latest state from the car, if the SMS provider
        supports sending from backend.
        """
        now = timezone.now()

        # Only ficosa2016 TCU is relevant for this logic.
        cars = Car.objects.filter(tcu_type='ficosa2016')

        cars_count = cars.count()
        if cars_count == 0:
            self.stdout.write(
                self.style.NOTICE("No ficosa2016 cars found for AC timeout check")
            )
            return

        self.stdout.write(
            self.style.NOTICE(f"Checking AC timeout assumption for {cars_count} ficosa2016 cars")
        )

        for car in cars:
            try:
                ev_info = car.ev_info

                # A/C is already off:€” nothing to assume.
                if not ev_info.ac_status:
                    continue

                # No start timestamp recorded:€” cannot determine age.
                if ev_info.ac_last_started is None:
                    continue

                # Determine timeout based on charging plug state.
                if ev_info.plugged_in:
                    timeout_minutes = AC_ASSUME_OFF_TIMEOUT_PLUGGED
                else:
                    timeout_minutes = AC_ASSUME_OFF_TIMEOUT_UNPLUGGED

                timeout_delta = datetime.timedelta(minutes=timeout_minutes)
                age = now - ev_info.ac_last_started

                if age < timeout_delta:
                    # Still within the timeout window: trust the car.
                    continue

                # Timeout exceeded: assume A/C has turned itself off.
                self.stdout.write(
                    self.style.NOTICE(
                        f"Car {car.vin}: A/C on for {age}, assuming off "
                        f"(timeout {timeout_minutes} min, plugged_in={ev_info.plugged_in})"
                    )
                )

                ev_info.ac_status = False
                ev_info.ac_last_started = None
                ev_info.save(update_fields=['ac_status', 'ac_last_started'])

                # Attempt a refresh command via SMS to retrieve latest state.
                try:
                    car = send_command_using_provider(1, None, car)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Car {car.vin}: Refresh command (type 1) sent via SMS"
                        )
                    )
                except Exception as e:
                    # SMS provider may not support sending from backend.€”
                    # That's acceptable, A/C state is already corrected in DB.
                    logger.warning(
                        f"Car {car.vin}: Could not send refresh SMS: {e}"
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"Car {car.vin}: Refresh SMS failed: {e}"
                        )
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing AC timeout for car {car.vin}: {str(e)}"
                    )
                )

    def handle(self, *args, **options):
        print("Starting data refresh process")
        self.handle_timeouts()
        self.handle_command_timers()
        self.handle_datarefresh()
        self.handle_ac_timeout_assumption()
