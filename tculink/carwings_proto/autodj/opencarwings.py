import os
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
import pngquant
from PIL import Image, ImageFont, ImageDraw
from django.utils import timezone, formats
from django.contrib.humanize.templatetags.humanize import ordinal
from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy

from db.models import CRMTripRecord
from tculink.carwings_proto.dataobjects import build_autodj_payload
from tculink.carwings_proto.utils import get_word_of_month_i18n

RELEASE_NOTES = "What's new in OpenCARWINGS?\n1. Route Planner\n2.Multiple Send To Car Locations\n3. Data Channels\n4. Energy Information"

RELEASE_NOTES_SPK = ("What's new in Open CAR WINGS? September release.\nNumber one. Route Planner. With new support of Route Planner, you can"
                     " plan your navigation routes in advance via your computer or mobile phone. It supports up to "
                     "5 waypoints and it is possible to send 5 routes to the car."
                     "\nNumber two. Multiple Send To Car Locations. Previously familar Google Send To Car function"
                     " supports sending up to six destinations, instead of previously supporting only one."
                     "\n3. Data Channels. Data channels are fully functional as of now and support for custom channels are coming soon."
                     "\n4. Energy Information. With the introduction of vehicle data, it is now possible to view your monthly trips, average consumption and more."
                     " Individual trips are transmitted to the Open Car Wings server with detailed information. In addition to this, data channels about E V information are now available.")

NOT_SIGNEDIN_NOTE = ("To make use of more functions of Open Car Wings, please sign in with your User I D and Car Wings "
                     "password inside your car.\n\nGo to Car Wings menu, Settings, Security Settings, to input and send "
                     "your credentials. Unlock even more useful functions and make your life easier with Open Car Wings.")

def get_infochannel(xml_data, returning_xml, channel_id, car):
    resources_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images")
    with open(os.path.join(resources_dir, "releasenotes.jpg"), "rb") as f:
        releasenotes_img = f.read()
    response_chdata = [
        {
            'itemId': 1,
            'itemFlag1': 0x00,
            'dynamicDataField1': 'What\'s new?'.encode('utf-8'),
            'dynamicDataField2': f"What\'s new?".encode('utf-8'),
            'dynamicDataField3': b'',
            "DMSLocation": b'\xFF' * 10,
            'flag2': 0,
            'flag3': 0,
            'dynamicField4': b'',
            # phone num field
            'dynamicField5': b'',
            'dynamicField6': b'',
            'unnamed_data': bytearray(),
            # text shown on bottom
            "bigDynamicField7": RELEASE_NOTES.encode('utf-8'),
            "bigDynamicField8": RELEASE_NOTES_SPK.encode('utf-8'),
            "iconField": 0x400,
            # annoucnement sound, 1=yes,0=no
            "longField2": 1,
            "flag4": 1,
            "unknownLongId4": 0x0000,
            # feature flag? 0xa0 = dial, 0x0F = Img
            "flag5": 0x9F,
            "flag6": 0xBB,
            # image button title
            "12byteField1": b'\x00' * 12,
            # image name2
            "12byteField2": b'\x00' * 12,
            "mapPointFlag": b'\x20',
            # save flag
            "flag8": 0x80,
            "imageDataField": releasenotes_img,
        }
    ]

    if car is None:
        with open(os.path.join(resources_dir, "releasenotes.jpg"), "rb") as f:
            tips_img = f.read()
        response_chdata.append(
            {
                'itemId': 2,
                'itemFlag1': 0x00,
                'dynamicDataField1': 'Tips & Tricks'.encode('utf-8'),
                'dynamicDataField2': "Tips & Tricks".encode('utf-8'),
                'dynamicDataField3': b'',
                "DMSLocation": b'\xFF' * 10,
                'flag2': 0,
                'flag3': 0,
                'dynamicField4': b'',
                # phone num field
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                # text shown on bottom
                "bigDynamicField7": NOT_SIGNEDIN_NOTE.encode('utf-8'),
                "bigDynamicField8": NOT_SIGNEDIN_NOTE.encode('utf-8'),
                "iconField": 0x400,
                # annoucnement sound, 1=yes,0=no
                "longField2": 1,
                "flag4": 1,
                "unknownLongId4": 0x0000,
                # feature flag? 0xa0 = dial, 0x0F = Img
                "flag5": 0x9F,
                "flag6": 0xBB,
                # image button title
                "12byteField1": b'\x00' * 12,
                # image name2
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x20',
                # save flag
                "flag8": 0x80,
                "imageDataField": tips_img,
            }
        )

    resp_file = build_autodj_payload(
        0,
        channel_id,
        response_chdata,
        {
            "type": 6,
            "data": b'\x01'
        },
        extra_fields={
            'stringField1': 'Info from OpenCARWINGS'.encode('utf-8'),
            'stringField2': 'Info from OpenCARWINGS'.encode('utf-8'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )

    ET.SubElement(returning_xml, "send_data", {"id_type": "file", "id": "INFOCHAN.001"})

    return [("INFOCHAN.001", resp_file)]

BUBBLE_TXT_COLOR = (222, 247, 148)


def wrap_text(text, width, font):
    text_lines = []
    text_line = []
    text = text.replace('\n', ' [br] ')
    words = text.split()

    for word in words:
        if word == '[br]':
            text_lines.append(' '.join(text_line))
            text_line = []
            continue
        text_line.append(word)
        w = font.getlength(' '.join(text_line))
        if w > width:
            text_line.pop()
            text_lines.append(' '.join(text_line))
            text_line = [word]

    if len(text_line) > 0:
        text_lines.append(' '.join(text_line))

    return text_lines

def create_consumption_slide(title, consumption, bar_labels, bars=0, helptext="", date="", day="", unit="3"):
    resources_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images")
    font_file = os.path.join(resources_dir, "zeroemission.ttf")

    header_font = ImageFont.truetype(font_file, 29)

    day_font = ImageFont.truetype(font_file, 18)

    date_font = ImageFont.truetype(font_file, 28)

    bar_font = ImageFont.truetype(font_file, 18)

    info_font = ImageFont.truetype(font_file, 13)

    main_frame = Image.open(os.path.join(resources_dir, f"zeroemission_2_{unit}.png"))
    mainframe_draw = ImageDraw.Draw(main_frame)
    # 57,87: dat
    # 330, 118: unit
    space_spacing = -4
    letter_spacing = -0.7
    x, y = 60, 23

    text = title

    end_x = 60
    font_size_correct = False
    title_stroke_width = 0.4

    while not font_size_correct:
        for char in text:
            char_width = mainframe_draw.textlength(char, font=header_font)
            if char == " ":
                end_x += char_width + space_spacing
            else:
                end_x += char_width + letter_spacing

        if end_x > 360:
            end_x = 60
            header_font = ImageFont.truetype(font_file, header_font.size - 1)
            title_stroke_width -= 0.005
        else:
            font_size_correct = True

    for char in text:
        mainframe_draw.text((x, y), char, fill=(181, 239, 255), stroke_width=title_stroke_width, font=header_font,
                            anchor="lm")
        char_width = mainframe_draw.textlength(char, font=header_font)
        if char == " ":
            x += char_width + space_spacing
        else:
            x += char_width + letter_spacing

    mainframe_draw.text((89, 98), date, fill=BUBBLE_TXT_COLOR, stroke_width=0.35, font=date_font, anchor="mm")
    mainframe_draw.text((90, 126), day, fill=BUBBLE_TXT_COLOR, stroke_width=0.30, font=day_font, anchor="mm")

    mainframe_draw.text((33, 213), bar_labels[0], fill="white", stroke_width=0.3, font=bar_font)
    mainframe_draw.text((225, 222), bar_labels[2], fill="white", stroke_width=0.3, font=bar_font, anchor="mm")
    txt = bar_labels[2][::-1]
    x, y = 422, 222
    space_width = 4
    o_width = 3.5
    normal_width = 3
    for i, char in enumerate(txt):
        mainframe_draw.text((x, y), char, fill="white", stroke_width=0.3, font=bar_font, anchor="rm")
        char_width = mainframe_draw.textlength(char, font=header_font)
        if char == " ":
            x -= char_width - space_width
        elif char == "o" or (i + 1 < len(txt) and txt[i + 1] == "o") or i == 1:
            x -= char_width - o_width
        else:
            x -= char_width - normal_width

    cons_fullnum = consumption

    cons_first = cons_fullnum.split(".")[0].rjust("3")
    for idx, i in enumerate(cons_first):
        pos = -85 + (42 * idx)
        print(i)
        if i != " ":
            segment = Image.open(os.path.join(resources_dir, f"seg{i}.png"))
            main_frame.paste(segment, (pos, 0), segment)

    if len(cons_fullnum.split(".")) > 1:
        cons_first = cons_fullnum.split(".")[1][0]
        segment = Image.open(os.path.join(resources_dir, f"seg{cons_first}.png"))
    else:
        segment = Image.open(os.path.join(resources_dir, f"seg0.png"))
    main_frame.paste(segment, (55, 0), segment)

    wrappedtxt = wrap_text(helptext, 390, info_font)
    mainframe_draw.text((32, 235), "\n".join(wrappedtxt), fill=(255, 189, 49), stroke_width=0.0, font=info_font)

    if bars > 0:
        bars_img = Image.open(os.path.join(resources_dir, f"bar{bars}.png"))
        main_frame.paste(bars_img, (0, 0), bars_img)

    indicator = Image.open(os.path.join(resources_dir, f"pin1.png"))
    base_ind_pos = -195
    if bars > 0:
        base_ind_pos += 35
        base_ind_pos += (bars - 1) * 79
    main_frame.paste(indicator, (base_ind_pos, 0), indicator)
    frame_data = BytesIO()
    main_frame.save(frame_data, format="PNG")
    return pngquant.quant_data(frame_data.getvalue())[1]

def create_info_slide(title, info_title):
    resources_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images")
    font_file = os.path.join(resources_dir, "zeroemission.ttf")

    header_font = ImageFont.truetype(font_file, 29)

    info_font = ImageFont.truetype(font_file, 26)

    main_frame = Image.open(os.path.join(resources_dir, f"zeroemission_0.png"))
    header_info = Image.open(os.path.join(resources_dir, "header_info.png"))
    body_info = Image.open(os.path.join(resources_dir, "body_info.png"))
    main_frame.paste(header_info, (0, 0), header_info)
    main_frame.paste(body_info, (0, 0), body_info)
    mainframe_draw = ImageDraw.Draw(main_frame)
    # 57,87: dat
    # 330, 118: unit
    space_spacing = -4
    letter_spacing = -0.7
    x, y = 60, 23

    end_x = 60
    font_size_correct = False
    title_stroke_width = 0.3

    while not font_size_correct:
        for char in title:
            char_width = mainframe_draw.textlength(char, font=header_font)
            if char == " ":
                end_x += char_width + space_spacing
            else:
                end_x += char_width + letter_spacing

        if end_x > 360:
            print(header_font.size)
            end_x = 60
            header_font = ImageFont.truetype(font_file, header_font.size - 1)
            title_stroke_width -= 0.005
        else:
            font_size_correct = True

    for char in title:
        mainframe_draw.text((x, y), char, fill=(181, 239, 255), stroke_width=title_stroke_width, font=header_font,
                            anchor="lm")
        char_width = mainframe_draw.textlength(char, font=header_font)
        if char == " ":
            x += char_width + space_spacing
        else:
            x += char_width + letter_spacing

    # 145 146
    y = 145
    infotxt = wrap_text(info_title, 152, info_font)
    for txt in infotxt:
        mainframe_draw.text((72, y + 2), txt, fill="black", stroke_width=0.4, font=info_font, anchor="lm")
        mainframe_draw.text((70, y), txt, fill="white", stroke_width=0.4, font=info_font, anchor="lm")
        y += 25

    frame_data = BytesIO()
    main_frame_jpg = main_frame.convert("RGB")
    main_frame_jpg.save(frame_data, 'JPEG', optimize=True, quality=80,compress_level=9)
    return frame_data.getvalue()

def get_ordinal_suffix(day):
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix

def get_random_drive_tip():
    tips = [
        _("Use remote climate control or the timer so that the cabin will be at a comfortable temperature before starting.  This allows the car to save energy whilst being driven."),
        _("Keep your car in the garage during winter times to keep the battery pack warm.  This will increase your range a bit, especially in colder climates."),
        _('Use <phoneme alphabet="x-SVOX-sampa_en-GB" ph="\'i:-k@@U">eco</phoneme> mode or B-mode when possible to increase your regenerative energy.'),
        _('Check your tire pressure at least once a month to ensure they are at optimal level.  Low tire pressure decreases rolling effect of the car and more energy is used on propulsion.'),
        _("Plan your routes to include charging stations, especially on longer trips, to avoid range anxiety and ensure smooth travel."),
        _("Avoid rapid acceleration and maintain a steady speed to maximize battery efficiency, as aggressive driving can significantly reduce your range."),
        _("Use the Nissan Leaf’s navigation system to find the most energy-efficient routes, which can help conserve battery power on unfamiliar roads."),
        _("In colder times, try to use more of seat heating and steering wheel heating while keeping your air conditioning on lower settings. Auxiliary heating elements consume less than car's air conditioning system."),
        _("Park in shaded areas during hot weather to keep the battery cool, as extreme heat can reduce battery efficiency and longevity."),
        _("Try to charge the battery up to 80 percent for daily usage. Charging to full, every day, is not recommended for battery longevity."),
        _("With Open Car Wings, you can review your driving efficiency of each trip, online. With the data, it is easier to determine which areas of driving needs to be improved to achieve supreme energy efficiency. ")
    ]
    return random.choice(tips)

def get_energy_information_channel(xml_data, returning_xml, channel_id, car):
    response_chdata = []

    last_trips = CRMTripRecord.objects.filter(car=car).order_by("-start_ts")[:5]

    car_timezone = float(xml_data['base_info'].get('navigation_settings', {}).get('time_zone', "+0.00"))
    car_tzinfo = timezone.get_fixed_timezone(car_timezone)
    time_car_now = datetime.now(tz=car_tzinfo)

    spent_energy = 0
    driven_km = 0
    consumptions = []
    for trip in last_trips:
        consume_wh = (trip.motor_consumption+trip.aircon_consumption+trip.auxiliary_consumption)/10.0
        regen_wh = trip.regen/100.0
        spent_energy += (consume_wh-regen_wh)
        driven_km += trip.distance
        if (consume_wh-regen_wh) != 0 and trip.distance != 0:
            consumptions.append((consume_wh-regen_wh)/trip.distance)

    wh_per_km = -1
    if driven_km > 0 and spent_energy > 0:
        wh_per_km = (spent_energy/driven_km)


    cons_formatted_str = "{:.1f}".format(wh_per_km)
    status_labels = [_("Average"), _("Good"), _("Very good")]
    slide_title = _("Check Energy Economy")

    day = time_car_now.day
    month = formats.date_format(time_car_now, format='%B')
    day_word = get_word_of_month_i18n(day)
    help_text = _("The energy economy trend compared with the average of the last five trips is shown above.")

    date_txt = formats.date_format(time_car_now, format='%d %b')+"."
    day_txt = formats.date_format(time_car_now, format='%a').upper()

    display_txt = _("Trend of Energy Economy\n")
    display_txt += f"{ordinal(day)} / {month}:"

    if wh_per_km != -1:
        # status
        """
        10 -> 5 (very good)
        12 -> 4 (good)
        13.8 -> 3 bar (good)
        16 -> 3 bar (good)
        20 ->  2 (average)
        28 -> 1 (average)
        """
        economy_status = _("Good")
        bars = 0
        if wh_per_km < 110:
            economy_status = _("Very good")
            bars = 5
        elif wh_per_km < 140:
            bars = 4
        elif wh_per_km < 180:
            bars = 3
        elif wh_per_km < 280:
            bars = 2
            economy_status = _("Average")
        elif wh_per_km < 360:
            bars = 1
            economy_status = _("Bad")


        display_txt += "{:.1f} Wh/km".format(wh_per_km)
        display_txt += "\n\nLast 5 days:\n"
        display_txt += _("[Average]\n")
        display_txt += "{:.1f} Wh/km\n".format(wh_per_km)
        display_txt += _("[Best]\n")
        display_txt += "{:.1f} Wh/km\n".format(min(consumptions))
        display_txt += _("[Worst]\n")
        display_txt += "{:.1f} Wh/km\n".format(max(consumptions))

        read_txt = format_lazy(_("\nAs of the {day_word} of {month}, your energy economy was {cons_formatted_str} watt hours per kilometer.\n"
                    "Based on the last 5 trips, Your energy economy is {economy_status}. "), day_word=day_word, month=month,
                               cons_formatted_str=cons_formatted_str, economy_status=economy_status)
    else:
        cons_formatted_str = "0.0"
        bars = 0
        display_txt += _("There is no trip records available yet. Try checking in again after your next trip.")
        read_txt = format_lazy(
            _("\nAs of the {day_word} of {month}, your energy economy cannot be calculated yet, because of missing trip"
              " information. Try checking in to this channel again after your next trip. "), day_word=day_word, month=month)


    consumption_slide_img = create_consumption_slide(slide_title, cons_formatted_str, status_labels, bars, help_text, date_txt, day_txt)

    response_chdata.append({
            'itemId': 1,
            'itemFlag1': 0x00,
            'dynamicDataField1': slide_title.encode('utf-8'),
            'dynamicDataField2': slide_title.encode('utf-8'),
            'dynamicDataField3': b'',
            "DMSLocation": b'\xFF' * 10,
            'flag2': 0,
            'flag3': 0,
            'dynamicField4': b'',
            # phone num field
            'dynamicField5': b'',
            'dynamicField6': b'',
            'unnamed_data': bytearray(),
            # text shown on bottom
            "bigDynamicField7": display_txt.encode('utf-8'),
            "bigDynamicField8": read_txt.encode('utf-8'),
            "iconField": 0x400,
            # annoucnement sound, 1=yes,0=no
            "longField2": 1,
            "flag4": 1,
            "unknownLongId4": 0x0000,
            # feature flag? 0xa0 = dial, 0x0F = Img
            "flag5": 0x9F,
            "flag6": 0xBB,
            # image button title
            "12byteField1": b'\x00' * 12,
            # image name2
            "12byteField2": b'\x00' * 12,
            "mapPointFlag": b'\x20',
            # save flag
            "flag8": 0x80,
            "imageDataField": consumption_slide_img,
        })

    tip_title = _("Electric Car Column")
    tip_slide_img = create_info_slide(tip_title, _("Drive Tip"))

    tip_txt = get_random_drive_tip()

    tip_onscreen = _("Drive Tip")+": "+tip_txt

    response_chdata.append(
        {
            'itemId': 2,
            'itemFlag1': 0x00,
            'dynamicDataField1': tip_title.encode('utf-8'),
            'dynamicDataField2': tip_title.encode('utf-8'),
            'dynamicDataField3': b'',
            "DMSLocation": b'\xFF' * 10,
            'flag2': 0,
            'flag3': 0,
            'dynamicField4': b'',
            # phone num field
            'dynamicField5': b'',
            'dynamicField6': b'',
            'unnamed_data': bytearray(),
            # text shown on bottom
            "bigDynamicField7": tip_onscreen.encode('utf-8'),
            "bigDynamicField8": tip_txt.encode('utf-8'),
            "iconField": 0x400,
            # annoucnement sound, 1=yes,0=no
            "longField2": 1,
            "flag4": 1,
            "unknownLongId4": 0x0000,
            # feature flag? 0xa0 = dial, 0x0F = Img
            "flag5": 0x9F,
            "flag6": 0xBB,
            # image button title
            "12byteField1": b'\x00' * 12,
            # image name2
            "12byteField2": b'\x00' * 12,
            "mapPointFlag": b'\x20',
            # save flag
            "flag8": 0x80,
            "imageDataField": tip_slide_img,
        }
    )


    resp_file = build_autodj_payload(
        0,
        channel_id,
        response_chdata,
        {
            "type": 6,
            "data": b'\x01'
        },
        extra_fields={
            'stringField1': _('Energy Information').encode('utf-8'),
            'stringField2': _('Energy Information').encode('utf-8'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )

    ET.SubElement(returning_xml, "send_data", {"id_type": "file", "id": "ENERGY.001"})

    return [("ENERGY.001", resp_file)]






