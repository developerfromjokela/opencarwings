def convert_tpms_pressure_kpa(value, int_pressure=False, round_val=True) -> float:
    if value == 0:
        return 0
    psi_val = convert_tpms_pressure(value, int_pressure=int_pressure, round_val=False)
    # to kPa
    kpa_val = psi_val * 6.89476
    if round_val:
        return round(kpa_val, 3)
    return kpa_val

def convert_tpms_pressure_bar(value, int_pressure=False, round_val=True) -> float:
    if value == 0:
        return 0
    psi_val = convert_tpms_pressure(value, int_pressure=int_pressure, round_val=False)
    # to Bar
    bar_val = psi_val / 14.5038
    if round_val:
        return round(bar_val, 3)
    return bar_val

def convert_tpms_pressure(value, int_pressure=False, round_val=True) -> float:
    if value == 0:
        return 0
    if int_pressure:
        return float(int(value))
    if round_val:
        return round(value / 4.0, 3)
    return value / 4.0


def apply_ac_state_timeout(car):
    """Silently assume A/C has turned itself off when the configured timeout has
    elapsed since it was last started AND we have not heard from the car since.

    Runs on-read (lazy). No alerts or notifications are created. This keeps the
    backend state in sync with the car without sending any commands.
    A timeout of 0 means disabled (never assume off).
    Returns True if A/C state was reset to off, False otherwise.
    """
    from datetime import timedelta
    from django.utils import timezone

    minutes = getattr(car, 'ac_assume_off_timeout', 0) or 0
    if minutes <= 0:
        return False

    ev_info = getattr(car, 'ev_info', None)
    if ev_info is None:
        return False

    # A/C is reported off -> clear the start timestamp so it can't trigger later.
    if not ev_info.ac_status:
        if ev_info.ac_last_started is not None:
            ev_info.ac_last_started = None
            ev_info.save(update_fields=['ac_last_started'])
        return False

    if ev_info.ac_last_started is None:
        return False

    # If we have received a status update from the car recently, trust it and
    # do not assume the A/C has turned itself off just because ac_last_started
    # is old. The car may still be reporting "AC on" via periodic updates.
    if ev_info.last_updated is not None:
        if timezone.now() - ev_info.last_updated < timedelta(minutes=minutes):
            return False

    # No recent status update, and A/C has been "on" longer than the timeout.
    if timezone.now() - ev_info.ac_last_started >= timedelta(minutes=minutes):
        ev_info.ac_status = False
        ev_info.ac_last_started = None
        ev_info.save(update_fields=['ac_status', 'ac_last_started'])
        return True
    return False