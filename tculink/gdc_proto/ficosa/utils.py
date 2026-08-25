from django.utils.translation import gettext_lazy as _

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
    new_config = CONFIGURATION_MAP.copy()
    for key, val in new_config.items():
        val["label"] = _(val["label"])
        for fkey, fval in val["fields"].items():
            label = fval["label"]
            val["fields"][fkey]["label"] = _(label)
        new_config[key] = val
    return new_config

CONFIGURATION_MAP = {
    "veh_health": {
        "label": _("Vehicle Health Report"),
        "destination": 0x43,
        "service_type": 0x5b,
        "query_support": False,
        "fields": {
            "enabled": {"info_id": 1, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "label": _("Service Enabled")},
            "frequency": {"info_id": 3, "length": 1, "type": ConfigurationFieldType.NUMBER, "max": 30, "min": 2, "label": _("Send frequency (days)")}
        }
    },
    "svc_provision": {
        "label": _("Service Provisioning"),
        "destination": 0xf5,
        "service_type": 0,
        "query_support": False,
        "fields": {
            "ev_batt_chg_stat": {"info_id": 0x42, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("EV Battery Charging Status")},
            "ev_batt_chg_hist": {"info_id": 0x43, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("EV Battery Charging History")},
            "ev_batt_chg_act_rem": {"info_id": 0x44, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("EV Battery Charging Remote Activation")},
            "ev_hmac_rem": {"info_id": 0x46, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("EV Remote HVAC Activation")},
            "ev_plugin_remind": {"info_id": 0x47, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("EV Plug Reminder")},
            "ev_batt_heat": {"info_id": 0x4e, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("EV Battery Heating Notification")},
            "veh_health": {"info_id": 0x5b, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Vehicle Health Report")},
            "burglar_alarm": {"info_id": 0x63, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Burglar Alarm")},
            "remote_door": {"info_id": 0x64, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Door Lock & Unlock")},
            "tow_notif": {"info_id": 0x6d, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Tow Notification")},
            "remote_horn": {"info_id": 0x70, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Horn & Lights")},
            "probe_1": {"info_id": 0x50, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=1))},
            "probe_2": {"info_id": 0x51, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=2))},
            "probe_3": {"info_id": 0x52, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=3))},
            "probe_4": {"info_id": 0x53, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=4))},
            "probe_5": {"info_id": 0x54, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=5))},
            "probe_6": {"info_id": 0x55, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=6))},
            "probe_7": {"info_id": 0x56, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=7))},
            "probe_8": {"info_id": 0x57, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=8))},
            "probe_9": {"info_id": 0x58, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=9))},
            "probe_10": {"info_id": 0x59, "length": 1, "type": ConfigurationFieldType.PROVISIONING, "label": _("Probe Service {num}".format(num=10))},
        }
    },
    "sim1_config": {
        "label": _("SIM Settings 1"),
        "destination": 0xf2,
        "service_type": 0xf2,
        "query_support": False,
        "fields": {
            "f1": {"info_id": 0x00, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": _("SIM Pin Code"), "fill": True},
            "f2": {"info_id": 0x01, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "optional": True,
                   "label": _("SIM Pin Locked"), "fill": True},
            "f3": {"info_id": 0x02, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": "APN", "fill": True},
            "f4": {"info_id": 0x03, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": "APN Username", "fill": True},
            "f5": {"info_id": 0x04, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": "APN Password", "fill": True},
            "f6": {"info_id": 0x05, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": _("SMSC Number 1"), "fill": True},
            "f7": {"info_id": 0x06, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": "DNS1", "fill": True},
            "f8": {"info_id": 0x07, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": "DNS2", "fill": True},
            "f9": {"info_id": 0x08, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                   "label": "MFD/TSP APN", "fill": True},
            "f10": {"info_id": 0x09, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                    "label": "MFD/TSP APN Username", "fill": True},
            "f11": {"info_id": 0x0a, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                    "label": "MFD/TSP APN Password", "fill": True},
            "f12": {"info_id": 0x0b, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                    "label": "MFD/TSP DNS1", "fill": True},
            "f13": {"info_id": 0x0c, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                    "label": "MFD/TSP DNS2", "fill": True},
            "f14": {"info_id": 0x0d, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "optional": True,
                    "label": "SIM Radio Wave Off", "fill": True},
            "f15": {"info_id": 0x0e, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True,
                    "label": _("SMSC Number 2"), "fill": True},
        }
    },
    "sim2_config": {
        "label": _("SIM Settings 2"),
        "destination": 0xf3,
        "service_type": 0xf3,
        "query_support": False,
        "fields": {
            "f1": {"info_id": 0x10, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": _("SIM Pin Code"), "fill": True},
            "f2": {"info_id": 0x11, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "optional": True, "label": _("SIM Pin Locked"), "fill": True},
            "f3": {"info_id": 0x12, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "APN", "fill": True},
            "f4": {"info_id": 0x13, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "APN Username", "fill": True},
            "f5": {"info_id": 0x14, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "APN Password", "fill": True},
            "f6": {"info_id": 0x15, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": _("SMSC Number 1"), "fill": True},
            "f7": {"info_id": 0x16, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "DNS1", "fill": True},
            "f8": {"info_id": 0x17, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "DNS2", "fill": True},
            "f9": {"info_id": 0x18, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "MFD/TSP APN", "fill": True},
            "f10": {"info_id": 0x19, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "MFD/TSP APN Username", "fill": True},
            "f11": {"info_id": 0x1a, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "MFD/TSP APN Password", "fill": True},
            "f12": {"info_id": 0x1b, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "MFD/TSP DNS1", "fill": True},
            "f13": {"info_id": 0x1c, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": "MFD/TSP DNS2", "fill": True},
            "f14": {"info_id": 0x1d, "length": 1, "type": ConfigurationFieldType.BOOLEAN, "optional": True, "label": "SIM Radio Wave Off", "fill": True},
            "f15": {"info_id": 0x1e, "length": 0x20, "type": ConfigurationFieldType.ASCII, "optional": True, "label": _("SMSC Number 2"), "fill": True},
        }
    }
}

def command_to_destination_id(cmd: int) -> int|None:
    """
    Map OpenCARWINGS command ID to FICOSA TCU ACP Destination ID.
    """
    return COMMAND_MAP.get(cmd)