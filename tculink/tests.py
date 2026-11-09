from django.template.loader import render_to_string
from django.test import TestCase

from tculink.carwings_proto.applications.cp import dedupe_chargers
from tculink.carwings_proto.autodj.opencarwings import create_consumption_slide, create_ecorecord_slide, \
    create_ecoforest_slide, create_info_slide
from tculink.gdc_proto.acp245 import composer
from tculink.gdc_proto.responses import create_charge_status_response, create_charge_request_response, \
    create_ac_setting_response, create_ac_stop_response, create_config_read

from django.utils import timezone, formats


def _ocm_charger(id, lat, lon, title, points=1, date_created="2023-01-01T00:00:00Z", plugs=(2,)):
    return {
        "ID": id,
        "DateCreated": date_created,
        "NumberOfPoints": points,
        "Connections": [{"ConnectionTypeID": p} for p in plugs],
        "AddressInfo": {"Title": title, "Latitude": lat, "Longitude": lon},
    }


class ChargerDedupe(TestCase):

    def test_same_site_collapses_to_one(self):
        # Keldnaholt is in OCM four times
        chargers = [
            _ocm_charger(243577, 64.13835, -21.764618, "Landbúnaðar Háskólinn -Keldnaholti", points=8, date_created="2023-03-07T04:01:00Z"),
            _ocm_charger(238834, 64.13835, -21.764618, "Landbúnaðar Háskólinn -Keldnaholti", points=8, date_created="2023-03-07T01:53:00Z"),
            _ocm_charger(234889, 64.13835, -21.764618, "Landbúnaðar Háskólinn -Keldnaholti", points=8, date_created="2023-02-13T06:01:00Z"),
            _ocm_charger(216375, 64.13835, -21.764618, "Landbúnaðar Háskólinn -Keldnaholti", points=8, date_created="2023-02-09T09:51:00Z"),
        ]

        result = dedupe_chargers(chargers)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ID"], 243577)  # newest DateCreated wins the tie

    def test_distinct_sites_are_kept(self):
        chargers = [
            _ocm_charger(1, 64.1500, -21.9000, "Site A"),
            _ocm_charger(2, 64.1600, -21.8000, "Site B"),
        ]

        self.assertEqual(len(dedupe_chargers(chargers)), 2)

    def test_more_points_wins_over_newer_date(self):
        chargers = [
            _ocm_charger(1, 64.1500, -21.9000, "Site A", points=2, date_created="2024-01-01T00:00:00Z"),
            _ocm_charger(2, 64.1500, -21.9000, "Site A", points=8, date_created="2020-01-01T00:00:00Z"),
        ]

        result = dedupe_chargers(chargers)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ID"], 2)

    def test_different_plugs_are_kept(self):
        chargers = [
            _ocm_charger(1, 64.1500, -21.9000, "Site A", points=4, plugs=(25,)),
            _ocm_charger(2, 64.1500, -21.9000, "Site A", points=1, plugs=(2,)),
        ]

        self.assertEqual(len(dedupe_chargers(chargers)), 2)


class DataPacketParse(TestCase):

    def test_get_responses(self):
        print("Charge status resp true", create_charge_status_response(True).hex(' ').upper())
        print("Charge status resp false", create_charge_status_response(False).hex(' ').upper())
        print("Charge resp true", create_charge_request_response(True).hex(' ').upper())
        print("Charge resp false", create_charge_request_response(False).hex(' ').upper())
        print("AC resp false", create_ac_setting_response(False).hex(' ').upper())
        print("AC resp true", create_ac_setting_response(True).hex(' ').upper())
        print("AC stop false", create_ac_stop_response(False).hex(' ').upper())
        print("AC stop true", create_ac_stop_response(True).hex(' ').upper())
        print("AC stop true", create_ac_stop_response(True).hex(' ').upper())
        print("Read config", create_config_read().hex(' ').upper())

    def test_ficosa(self):
        acp_msg = bytearray()

        acp_msg += composer.VersionFicosa(sw_version=2, hw_1=1, hw_2=0, hw_3=2).encode()
        acp_msg += composer.VehDesc(vin="SHORTVIN", dcm="SHORTDCM").encode()
        acp_msg += b'\xFF'
        acp_msg += b'\xFF'
        acp_msg += composer.Timestamp().encode()

        msg = bytearray()
        msg += composer.AppHeader(app_id=2, mcf=3, length=len(acp_msg), special_flag=1).encode()
        msg += acp_msg

        print(msg.hex())

        assert len(msg) == 0x32


class AutoDJImageGenerationTests(TestCase):

    def test_consumption(self):
        help_txt = "The energy economy trend compared with the average of the last five trips is shown above."
        date_txt = formats.date_format(timezone.now(), format='j b') + "."
        day_txt = formats.date_format(timezone.now(), format='D').upper()
        img_data = create_consumption_slide("Check Energy Economy", "169.5", ["Average", "Good", "Very good"], 5, help_txt, date_txt, day_txt)

        with open("slide_consumption.png", "wb") as f:
            f.write(img_data)

    def test_ecotree(self):
        tstdata = [
            (formats.date_format(timezone.now(), format='j b') + ".", 9999,
              timezone.now()),
            (formats.date_format(timezone.now(), format='j b') + ".", 9999,
              timezone.now()),
            (formats.date_format(timezone.now(), format='j b') + ".", 9999,
              timezone.now())
        ]
        img_data = create_ecorecord_slide(str("Eco Tree Record"), "Total:", 999, "trees", tstdata)

        with open("slide_ecotree.png", "wb") as f:
            f.write(img_data)

    def test_ecoforest(self):
        tree_word = "trees"
        tonnes_words = "tonnes"
        img_data = create_ecoforest_slide("World's Eco Forest", "Total number of Eco Trees:",
                                               f"{round(9999999999999):.0f} {tree_word}",
                                               "CO2 Emission Cuts:",
                                               f"{round(9999999999999):.0f} {tonnes_words}")


        with open("slide_ecoforest.png", "wb") as f:
            f.write(img_data)

    def test_infoslide(self):
        img_data = create_info_slide("Electric Car Column", "Drive Tip")


        with open("slide_info.png", "wb") as f:
            f.write(img_data)

class EmailAlerts(TestCase):

    def test_email_alert_mi(self):
        text_content = render_to_string(
            "emails/vehicle_alert.txt",
            context={
                "alert": "test",
                "vehicle": "nick",
                "range_acon": 50,
                "range_acoff": 55,
                "soc": 55,
                "pluggedin": "yes",
                "athome": "yes",
                "imperial": True
            },
        )

        print(text_content)
        print("KM not in text & mi in text", "km" not in text_content, "mi" in text_content)
        assert "km" not in text_content and "mi" in text_content

    def test_email_alert_km(self):
        text_content = render_to_string(
            "emails/vehicle_alert.txt",
            context={
                "alert": "test",
                "vehicle": "nick",
                "range_acon": 50,
                "range_acoff": 55,
                "soc": 55,
                "pluggedin": "yes",
                "athome": "yes",
                "imperial": False
            },
        )

        print(text_content)
        print("KM in text", "km" in text_content)
        assert "km" in text_content