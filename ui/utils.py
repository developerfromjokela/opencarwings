def convert_tpms_pressure_kpa(value) -> float:
    if value == 0:
        return 0
    psi_val = value / 4.0
    # to kPa
    return round(psi_val * 6.89476, 3)

def convert_tpms_pressure_bar(value) -> float:
    if value == 0:
        return 0
    psi_val = value / 4.0
    # to Bar
    return round(psi_val / 0.068948, 3)

def convert_tpms_pressure(value) -> float:
    if value == 0:
        return 0
    return round(value / 4.0, 3)