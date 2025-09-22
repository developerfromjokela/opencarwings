import datetime
import logging
from django.utils import timezone

logger = logging.getLogger("probe")


prb_dotfiletypes = {
   # 1: ("Car Unit ID", 0),
    2: ("Probe soft version", 1),
    3: ("Configuration version", 2),
    4: ("Map version", 32),
    5: ("GPS time", 6),
    6: ("GPS Position", 9),
    7: ("GPS Direction", 3),
    8: ("GPS Speed", 3),
    9: ("GPS Height", 3),
    10: ("Deadreckoning pos", 8),
    11: ("Deadreckoning dir", 2),
    12: ("Navi position", 8),
    13: ("Navi direction", 2),
    14: ("Navi speed", 2),
    15: ("Navi odometer", 4),
    16: ("Navi Brrake", 1),
    17: ("Navi reverse", 1),
    18: ("Map matching road", 1),
    37: ("GPS Time [Relative]", 1),
    38: ("GPS Position [Relative]", 9),
    42: ("Deadreckoning position [Relative]", 8),
    44: ("Navi position [Relative]", 4),
    250: ("Timezone", 1),
    64: ("VCan speed", 3),
    65: ("VCan winker", 2)
}

road_types = {
    0: "highway",
    1: "urban highway",
    2: "general-road",
    3: "toll-road",
    4: "other"
}

def apply_date_patch(date):
    # apply patch for gps rollover, add 1024 weeks
    rollover_timedelta = datetime.timedelta(days=1024*7)
    if date.year < timezone.now().year-5:
        return date + rollover_timedelta
    return date

def parse_dotfile(dotfile_data):
    pos = 0
    files = []
    blocks = []
    gps_time_aquired = False
    struct = {}
    while pos < len(dotfile_data):
        item_type = dotfile_data[pos]
        if item_type in prb_dotfiletypes:
            if gps_time_aquired and item_type == 2:
                files.append(blocks)
                blocks = []
            if (not gps_time_aquired and item_type == 5) or (gps_time_aquired and item_type == 0x25):
                if len(struct.keys()) > 0:
                    blocks.append(struct)
                    struct = {}
            prb_type = prb_dotfiletypes[item_type]
            pos += 1
            logger.debug("TYPE: %d/%s, %s", item_type, hex(item_type), str(prb_type[0]))
            logger.debug("DATALEN: %d", prb_type[1])
            data = dotfile_data[pos:pos + prb_type[1]]
            logger.debug("DATA: %s", data.hex())
            pos += prb_type[1]
            if item_type in [0xf, 0xe, 0xb, 0xd, 0x7, 0x8]:
                struct[prb_type[0]] = int.from_bytes(data, byteorder="big") / 10
            elif item_type in [0x9, 0x25]:
                struct[prb_type[0]] = int.from_bytes(data, byteorder="big")
            elif item_type == 0x40:
                struct[prb_type[0]] = int.from_bytes(data, byteorder="big") / 100
            elif item_type == 0x5:
                struct[prb_type[0] + "_raw"] = "%02d.%02d.%02d %02d:%02d:%02d" % (data[0], data[1], data[2], data[3], data[4],
                                                                                data[5])
                struct[prb_type[0]] = apply_date_patch(datetime.datetime(2000 + data[0], data[1], data[2], data[3], data[4], data[5]))
            elif item_type == 16 or item_type == 17:
                struct[prb_type[0]] = True if int.from_bytes(data, byteorder="big") == 0x31 else False
            elif item_type == 18:
                road_type = data[0] & 3
                road_collection_status = ((data[0] >> 2) & 1)
                struct["road_collected"] = road_collection_status == 1
                if road_collection_status == 1:
                    struct["road_type"] = road_types[road_type]
                else:
                    struct["road_type"] = road_types[4]
            elif item_type == 4:
                struct[prb_type[0]] = data.decode("ascii").rstrip('\x00')
            else:
                struct[prb_type[0]] = "0x"+data.hex()
            logger.debug("-------------------")
            if item_type == 0x05:
                gps_time_aquired = True
        else:
            raise Exception("UNKNOWN DOT TYPE: ", item_type, "HEX", hex(item_type), "pos:", pos)

    if len(struct.keys()) > 0:
        blocks.append(struct)

    return blocks