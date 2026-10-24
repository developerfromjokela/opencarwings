from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone


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

def order_ts_future_last(qs, field):
    """
    Custom ordering, which moves dates in the future to lower priority
    """
    now = timezone.now()
    return qs.annotate(
        _is_future=Case(
            When(**{f"{field}__gt": now}, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('_is_future', f'-{field}')