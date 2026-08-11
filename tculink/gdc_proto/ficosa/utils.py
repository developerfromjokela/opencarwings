
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
    PROVISIONING = 4

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
        "query_support": False,
        "fields": {
            "enabled": {"info_id": 1, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "label": "Service Enabled"},
            "frequency": {"info_id": 3, "length": 1, "type": ConfigurationFieldType.NUMBER, "max": 30, "min": 1, "label": "Send frequency (days)"}
        }
    },
    "svc_provision": {
        "label": "Service Provisioning",
        "destination": 0xf5,
        "service_type": 0,
        "query_support": False,
        "fields": {
            "ev_batt_chg_stat": {"info_id": 0x42, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "EV Battery Charging Status"},
            "ev_batt_chg_hist": {"info_id": 0x43, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "EV Battery Charging History"},
            "ev_batt_chg_act_rem": {"info_id": 0x44, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "EV Battery Charging Remote Activation"},
            "ev_hmac_rem": {"info_id": 0x46, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "EV Remote HVAC Activation"},
            "ev_plugin_remind": {"info_id": 0x47, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "EV Plug Reminder"},
            "ev_batt_heat": {"info_id": 0x4e, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "EV Battery Heating Notification"},
            "veh_health": {"info_id": 0x5b, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Vehicle Health Report"},
            "burglar_alarm": {"info_id": 0x63, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Burglar Alarm"},
            "remote_door": {"info_id": 0x64, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Door Lock & Unlock"},
            "tow_notif": {"info_id": 0x6d, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Tow Notification"},
            "remote_horn": {"info_id": 0x70, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Horn & Lights"},
            "probe_1": {"info_id": 0x50, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 1"},
            "probe_2": {"info_id": 0x51, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 2"},
            "probe_3": {"info_id": 0x52, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 3"},
            "probe_4": {"info_id": 0x53, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 4"},
            "probe_5": {"info_id": 0x54, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 5"},
            "probe_6": {"info_id": 0x55, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 6"},
            "probe_7": {"info_id": 0x56, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 7"},
            "probe_8": {"info_id": 0x57, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 8"},
            "probe_9": {"info_id": 0x58, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 9"},
            "probe_10": {"info_id": 0x59, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": "Probe Service 10"},
        }
    }
}

def command_to_destination_id(cmd: int) -> int|None:
    """
    Map OpenCARWINGS command ID to FICOSA TCU ACP Destination ID.
    """
    return COMMAND_MAP.get(cmd)