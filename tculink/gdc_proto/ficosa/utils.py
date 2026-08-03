
COMMAND_MAP = {
    1: 0x28,
    2: 0x2b,
    3: 0x2c,
    4: 0x2c,
    6: 0x3e,
    7: 0x31,
    8: 0x31,
    9: 0x38,
    10: 0x38,
    11: 0x38,
    12: 0x38,
    13: 0x39,
    14: 0x39
}

class ConfigurationFieldType:
    NUMBER = 0
    BOOLEAN = 1
    ASCII = 2
    UNICODE = 3

def get_config_map_translated():
    from django.utils.translation import gettext_lazy
    new_config = CONFIGURATION_MAP.copy()
    for key, val in new_config.items():
        val["label"] = gettext_lazy(val["label"])
        for fkey, fval in val["fields"].items():
            label = fval["label"]
            val["fields"][fkey]["label"] = gettext_lazy(label)
        new_config[key] = val
    return new_config

CONFIGURATION_MAP = {
    "veh_health": {
        "label": "Vehicle Health Report",
        "destination": 0x43,
        "service_type": 0x5b,
        "query_support": True,
        "fields": {
            "enabled": {"info_id": 1, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "label": "Service Enabled"},
            "frequency": {"info_id": 3, "length": 1, "type": ConfigurationFieldType.NUMBER, "max": 30, "min": 1, "label": "Send frequency (days)"}
        }
    }
}

def command_to_destination_id(cmd: int) -> int|None:
    """
    Map OpenCARWINGS command ID to FICOSA TCU ACP Destination ID.
    """
    return COMMAND_MAP.get(cmd)