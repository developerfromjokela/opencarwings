from django.test import TestCase

from tculink.carwings_proto.autodj.opencarwings import create_consumption_slide, create_ecorecord_slide, \
    create_ecoforest_slide, create_info_slide
from tculink.gdc_proto.responses import create_charge_status_response, create_charge_request_response, \
    create_ac_setting_response, create_ac_stop_response, create_config_read

from django.utils import timezone, formats

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
