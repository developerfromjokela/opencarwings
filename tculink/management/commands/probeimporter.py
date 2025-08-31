import pprint

from django.core.management.base import BaseCommand

from db.models import Car
from tculink.carwings_proto.probe_crm import parse_crmfile, update_crm_to_db
from tculink.carwings_proto.utils import calculate_prb_data_checksum


class Command(BaseCommand):
    help = 'Import probe data from logfile'

    def add_arguments(self, parser):
        parser.add_argument('navi_id', type=str)
        parser.add_argument("files", nargs="+", type=str)

    def handle(self, *args, **options):
        navi_id = options['navi_id']
        for filename in options["files"]:
            print("File: ",filename)
            with open(filename, "rb") as f:
                file_content = f.read()
                data_length = int.from_bytes([file_content[3], file_content[4], file_content[5]], byteorder="big") - 8
                xor_key = file_content[6]
                file_number = int.from_bytes([file_content[7], file_content[8]], byteorder="big")
                coordinate_system = file_content[9]
                checksum_byte = file_content[-1]

                print("Probe file metadata:")
                print("  DataLength: %d", data_length)
                print("  FileNumber: %d", file_number)
                print("  XORKey: %s", hex(xor_key))
                print("  Checksum: %s", hex(checksum_byte))
                print("  CoordinateSystem: %s", hex(coordinate_system))

                # skip header added for logging
                file_content = file_content[10:len(file_content)-1]
                probedata = file_content[38:]
                if probedata[0] == 0xE1:
                    print("Detected probe CRM data")
                    crm_info = parse_crmfile(file_content)
                    print("Info:")
                    pprint.pprint(crm_info)
                    print("Adding to car records")
                    car = Car.objects.get(tcu_serial=navi_id)
                    update_crm_to_db(car, crm_info)
                    print("Added!")
                elif probedata[0] == 0x05:
                    print("Detected probe DOT data, skipping for now!")