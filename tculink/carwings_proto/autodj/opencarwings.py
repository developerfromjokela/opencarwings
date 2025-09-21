import calendar
import logging
import os
import random
from datetime import datetime
from io import BytesIO
logger = logging.getLogger("carwings_apj")

import pngquant
from PIL import Image, ImageFont, ImageDraw
from django.contrib.humanize.templatetags.humanize import ordinal
from django.db.models.aggregates import Sum
from django.utils import timezone, formats
from django.utils.text import format_lazy
from django.utils.translation import gettext as _

from db.models import CRMTripRecord
from tculink.carwings_proto.dataobjects import build_autodj_payload
from tculink.carwings_proto.utils import get_word_of_month_i18n, encode_utf8

RELEASE_NOTES = "What's new in OpenCARWINGS?\n1. Charging Stations\n"

RELEASE_NOTES_SPK = ("What's new in Open CAR WINGS? Last updated 17th of September.\nNumber one. Charging Stations.\n"
                     "You are now able to search for new charging stations in your area and do automatic updates on startup.\n"
                     "Charging Stations are loaded from Open Charge Map service. In upcoming releases, in addition to Charging Station Updates, "
                     "you will also be able to see charging station availability in the area.\n")

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
            'dynamicDataField1': encode_utf8('What\'s new?'),
            'dynamicDataField2': encode_utf8('What\'s new?'),
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
            "bigDynamicField7": encode_utf8(RELEASE_NOTES),
            "bigDynamicField8": encode_utf8(RELEASE_NOTES_SPK),
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
                'dynamicDataField1': encode_utf8('Tips & Tricks'),
                'dynamicDataField2': encode_utf8("Tips & Tricks"),
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
                "bigDynamicField7": encode_utf8(NOT_SIGNEDIN_NOTE),
                "bigDynamicField8": encode_utf8(NOT_SIGNEDIN_NOTE),
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
            'stringField1': _('Info from OpenCARWINGS'),
            'stringField2': _('Info from OpenCARWINGS'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )


    return [("INFOCHAN", resp_file)]

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

    mainframe_draw.text((33, 213), str(bar_labels[0]), fill="white", stroke_width=0.3, font=bar_font)
    mainframe_draw.text((225, 222), str(bar_labels[1]), fill="white", stroke_width=0.3, font=bar_font, anchor="mm")
    mainframe_draw.text((422, 222), str(bar_labels[2]), fill="white", stroke_width=0.3, font=bar_font, anchor="rm")
    #txt = str(bar_labels[2])[::-1]
    #x, y =
    #space_width = 4
    #o_width = 3.5
    #normal_width = 3
    #for i, char in enumerate(txt):
    #    mainframe_draw.text((x, y), char, fill="white", stroke_width=0.3, font=bar_font, anchor="rm")
    #    char_width = mainframe_draw.textlength(char, font=header_font)
    #    if char == " ":
    #        x -= char_width - space_width
    #    elif char == "o" or (i + 1 < len(txt) and txt[i + 1] == "o") or i == 1:
    #        x -= char_width - o_width
    #    else:
    #        x -= char_width - normal_width

    cons_fullnum = str(consumption)

    cons_first = cons_fullnum.split(".")[0].rjust(3)
    for idx, i in enumerate(cons_first):
        pos = -85 + (42 * idx)
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

def create_ecorecord_slide(title, total, total_count, trees, records):
    resources_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images")
    font_file = os.path.join(resources_dir, "zeroemission.ttf")

    header_font = ImageFont.truetype(font_file, 28)

    total_info = ImageFont.truetype(font_file, 17)
    total_data_info = ImageFont.truetype(font_file, 17)

    date_label = ImageFont.truetype(font_file, 21.5)
    trees_label = ImageFont.truetype(font_file, 19)

    bignum = ImageFont.truetype(font_file, 35)

    main_frame = Image.open(os.path.join(resources_dir, f"zeroemission_w.png"))
    forest = Image.open(os.path.join(resources_dir, f"forest.png"))
    table = Image.open(os.path.join(resources_dir, f"ecodata.png"))
    main_frame.paste(forest, (0, 0), forest)
    main_frame.paste(table, (0, 0), table)
    mainframe_draw = ImageDraw.Draw(main_frame)
    # 57,87: dat
    # 330, 118: unit
    space_spacing = -2
    letter_spacing = -0.5
    x, y = 16, 23

    end_x = 16
    font_size_correct = False
    title_stroke_width = 0.25

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
        mainframe_draw.text((x, y), char, fill="white", stroke_width=title_stroke_width + 2, font=header_font,
                            anchor="lm")
        mainframe_draw.text((x, y), char, fill=(41, 140, 123), stroke_width=title_stroke_width, font=header_font,
                            anchor="lm")
        char_width = mainframe_draw.textlength(char, font=header_font)
        if char == " ":
            x += char_width + space_spacing
        else:
            x += char_width + letter_spacing

    # 23,76: total
    # 23,175: total res

    mainframe_draw.text((22, 76), str(total), fill=(251, 186, 49), anchor="lm", stroke_width=0.3, font=total_info)

    mainframe_draw.text((175, 76), f"{total_count:.1f}", fill="white", anchor="rm", stroke_width=0.3, font=total_data_info)

    for i, row in enumerate(records):
        y_offset = (i * 54)
        txt_color_date = (255, 255, 255) if i != 0 else (231, 255, 156)
        txt_color_data = (140, 231, 255) if i != 0 else (231, 255, 156)
        mainframe_draw.text((23, 131 + y_offset), str(row[0]), fill=txt_color_date, anchor="lb", stroke_width=0.25,
                            font=date_label)
        mainframe_draw.text((172, 131 + y_offset), f"{row[1]:.1f}", fill=txt_color_data, anchor="rb", stroke_width=0.35,
                            font=bignum)
        mainframe_draw.text((176, 131 + y_offset), str(trees), fill=txt_color_data, anchor="lb", stroke_width=0.15,
                            font=trees_label)

        halftrees = row[1] % 1
        fulltrees = int(row[1] - halftrees)
        print(halftrees, fulltrees)
        tree_x = 0
        for i in range(fulltrees):
            tree = Image.open(os.path.join(resources_dir, f"t5.png")).resize((30, 42))
            main_frame.paste(tree, (234 + (36 * tree_x), 89 + y_offset), tree)
            tree_x += 1

        if halftrees > 0:
            print(round(halftrees * 5))
            tree = Image.open(os.path.join(resources_dir, f"t{int(round(halftrees * 5))}.png")).resize((30, 42))
            main_frame.paste(tree, (234 + (36 * tree_x), 89 + y_offset), tree)

    frame_data = BytesIO()
    main_frame.save(frame_data, format="PNG")
    return pngquant.quant_data(frame_data.getvalue())[1]

def create_ecoforest_slide(title, total_title, total_value, emission_title, emission_value):
    resources_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images")
    font_file = os.path.join(resources_dir, "zeroemission.ttf")

    header_font = ImageFont.truetype(font_file, 28)

    total_info = ImageFont.truetype(font_file, 16)
    total_data_info = ImageFont.truetype(font_file, 19)

    main_frame = Image.open(os.path.join(resources_dir, f"zeroemission_w.png"))
    forest = Image.open(os.path.join(resources_dir, f"forest.png"))
    main_frame.paste(forest, (0, 0), forest)

    globe = Image.open(os.path.join(resources_dir, f"globe.png"))
    maptree = Image.open(os.path.join(resources_dir, f"maptree.png"))
    main_frame.paste(globe, (0, 0), globe)
    main_frame.paste(maptree, (0, 0), maptree)

    mainframe_draw = ImageDraw.Draw(main_frame)
    # 57,87: dat
    # 330, 118: unit
    space_spacing = -2
    letter_spacing = -0.5
    x, y = 16, 23

    end_x = 16
    font_size_correct = False
    title_stroke_width = 0.25

    while not font_size_correct:
        for char in title:
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

    for char in title:
        mainframe_draw.text((x, y), char, fill="white", stroke_width=title_stroke_width + 2, font=header_font,
                            anchor="lm")
        mainframe_draw.text((x, y), char, fill=(41, 140, 123), stroke_width=title_stroke_width, font=header_font,
                            anchor="lm")
        char_width = mainframe_draw.textlength(char, font=header_font)
        if char == " ":
            x += char_width + space_spacing
        else:
            x += char_width + letter_spacing

    mainframe_draw.text((62, 235), str(total_title), fill=(8, 33, 76), anchor="lm", stroke_width=3,
                        font=total_info)
    mainframe_draw.text((62, 235), str(total_title), fill=(251, 186, 49), anchor="lm", stroke_width=0.3,
                        font=total_info)

    mainframe_draw.text((62, 255), str(emission_title), fill=(8, 33, 76), anchor="lm", stroke_width=3, font=total_info)
    mainframe_draw.text((62, 255), str(emission_title), fill=(251, 186, 49), anchor="lm", stroke_width=0.3,
                        font=total_info)

    mainframe_draw.text((440, 234), total_value, fill="white", anchor="rm", stroke_width=0.3,
                        font=total_data_info)
    mainframe_draw.text((440, 254), emission_value, fill="white", anchor="rm", stroke_width=0.3,
                        font=total_data_info)

    frame_data = BytesIO()
    main_frame_jpg = main_frame.convert("RGB")
    main_frame_jpg.save(frame_data, 'JPEG', optimize=True, quality=70,compress_level=9)
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
        energy = trip.wh_energy_start-trip.wh_energy_end
        if energy != 0 and trip.distance >= 1:
            spent_energy += energy
            driven_km += trip.distance
            consumptions.append(energy/trip.distance)

    wh_per_km = -1
    if driven_km > 0 and spent_energy > 0:
        wh_per_km = (spent_energy/driven_km)


    cons_formatted_str = "{:.1f}".format(wh_per_km)
    status_labels = [_("Average"), _("Good"), _("Very good")]
    slide_title = _("Check Energy Economy")

    day = time_car_now.day
    month = formats.date_format(time_car_now, format='F')
    day_word = get_word_of_month_i18n(day)
    help_text = _("The energy economy trend compared with the average of the last five trips is shown above.")

    date_txt = formats.date_format(time_car_now, format='j b')+"."
    day_txt = formats.date_format(time_car_now, format='D').upper()

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
        else:
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
            'dynamicDataField1': encode_utf8(slide_title),
            'dynamicDataField2': encode_utf8(slide_title),
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
            "bigDynamicField7": encode_utf8(display_txt),
            "bigDynamicField8": encode_utf8(read_txt),
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
            'dynamicDataField1': encode_utf8(tip_title),
            'dynamicDataField2': encode_utf8(tip_title),
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
            "bigDynamicField7": encode_utf8(tip_onscreen),
            "bigDynamicField8": encode_utf8(tip_txt),
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
            'stringField1': _('Energy Information'),
            'stringField2': _('Energy Information'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )


    return [("ENERGY", resp_file)]



def get_eco_tree_channel(xml_data, returning_xml, channel_id, car):
    response_chdata = []

    current_month = timezone.now().month
    current_year = timezone.now().year
    month_trips = CRMTripRecord.objects.filter(start_ts__month=current_month, start_ts__year=current_year, car=car).order_by("-start_ts")

    car_timezone = float(xml_data['base_info'].get('navigation_settings', {}).get('time_zone', "+0.00"))
    car_tzinfo = timezone.get_fixed_timezone(car_timezone)
    time_car_now = datetime.now(tz=car_tzinfo)

    trees = 0
    tree_records = {}

    start_d = time_car_now.day-3
    if time_car_now.day < 3:
        start_d = time_car_now.day

    max_days_cal = calendar.monthrange(time_car_now.year, time_car_now.month)[1]
    if start_d+3 > max_days_cal:
        start_d -= (start_d-calendar.monthrange(time_car_now.year, time_car_now.month)[1])



    for trip in month_trips:
        trip_trees = trip.eco_tree_count/5
        trees += trip_trees
        if trip.start_ts.day < time_car_now.day+1:
            day_idx = trip.start_ts.day
            if day_idx in tree_records:
                temp_itm = list(tree_records[day_idx])
                temp_itm[1] = temp_itm[1]+trip_trees
                tree_records[day_idx] = tuple(temp_itm)
            else:
                tree_records[day_idx] = (formats.date_format(trip.start_ts, format='j b')+".", trip_trees, trip.start_ts)

    logger.info(tree_records)
    slide_title = _("Eco Tree Record")

    if len(tree_records.keys()) < 3:
        for d in range(4):
            day_num = start_d+d
            if day_num not in tree_records:
                record_ts = time_car_now.date().replace(day=day_num)
                tree_records[d] = (formats.date_format(record_ts, format='j b')+".", 0.0, record_ts)


    display_txt = _("Your Eco Tree Record \n\n")

    record_keys = list(sorted(tree_records.keys()))
    record_keys.reverse()
    tree_records = [tree_records[key] for key in record_keys][:3]
    for tree_record in tree_records:
        tree_word = _("tree")
        if tree_record[1] > 1 or tree_record[1] == 0:
            tree_word = _("trees")
        month = formats.date_format(tree_record[2], format='F')
        display_txt += f"{ordinal(tree_record[2].day)} / {month}:\n{tree_record[1]:.1f} {tree_word}\n\n"

    tree_word = _("tree")
    if trees > 1 or trees == 0:
        tree_word = _("trees")
    display_txt += format_lazy(_("Sum total: {trees} {tree_word}"), trees=f"{trees:.1f}", tree_word=tree_word)

    first_record = tree_records[0]
    month = formats.date_format(first_record[2], format='F')
    day_word = get_word_of_month_i18n(first_record[2].day)
    read_txt = format_lazy(
        _('On the {day_word} of {month}, you saved {trees} <phoneme alphabet="x-SVOX-sampa_en-GB" ph="\'i:-k@@U">eco</phoneme>trees.")'),
        trees=f"{first_record[1]:.1f}",
        day_word=day_word,
        month=month,
    )

    eco_record_slide_img = create_ecorecord_slide(str(slide_title), _("Total:"), trees, _("trees"), tree_records[:3])

    response_chdata.append({
            'itemId': 1,
            'itemFlag1': 0x00,
            'dynamicDataField1': encode_utf8(slide_title),
            'dynamicDataField2': encode_utf8(slide_title),
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
            "bigDynamicField7": encode_utf8(display_txt),
            "bigDynamicField8": encode_utf8(read_txt),
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
            "imageDataField": eco_record_slide_img,
        })

    forest_title = _("World's Eco Forest")

    total_trees = CRMTripRecord.objects.aggregate(trees=Sum('eco_tree_count'))['trees']/5
    total_tonnes = round(total_trees*0.00412)
    tree_word = _("trees")
    tonnes_words = _("tonnes")
    ecoforest_slide = create_ecoforest_slide(forest_title, _("Total number of Eco Trees:"),
                                           f"{round(total_trees):.0f} {tree_word}",
                                           _("CO2 Emission Cuts:"),
                                           f"{round(total_tonnes):.0f} {tonnes_words}")


    day = time_car_now.day
    month = formats.date_format(time_car_now, format='F')
    tip_onscreen = f"{forest_title}\n\n"

    tip_onscreen += format_lazy(_("Total number of Eco Trees by {day} / {month}:"), month=month, day=ordinal(day))+"\n"
    tip_onscreen += f"{round(total_trees):.0f} {tree_word}\n\n"
    tip_onscreen += format_lazy(_("CO2 emissions reduced by {day} / {month}:"), month=month, day=ordinal(day))+"\n"
    tip_onscreen += f"{round(total_tonnes):.0f} {tonnes_words}\n\n"

    tip_onscreen += format_lazy(_("(This calculation is based on an assumption that the CO2 emitted by petrol-driven cars of equivalent class can be reduced by driving electric cars)"))
    month = formats.date_format(time_car_now, format='F')
    day_word = get_word_of_month_i18n(time_car_now.day)

    tip_txt = format_lazy(
        _('By the {day_word} of {month}, electric cars with Open Car Wings world wide saved a total of {trees} <phoneme alphabet="x-SVOX-sampa_en-GB" ph="\'i:-k@@U">eco</phoneme>trees. And {tonnes} tonnes of carbon dioxide has been reduced.'),
        month=month,
        day_word=day_word,
        trees=f"{round(total_trees):.0f}",
        tonnes=f"{round(total_tonnes):.0f}"
    )

    response_chdata.append(
        {
            'itemId': 2,
            'itemFlag1': 0x00,
            'dynamicDataField1': encode_utf8(forest_title),
            'dynamicDataField2': encode_utf8(forest_title),
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
            "bigDynamicField7": encode_utf8(tip_onscreen),
            "bigDynamicField8": encode_utf8(tip_txt),
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
            "imageDataField": ecoforest_slide,
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
            'stringField1': _('ECO Tree'),
            'stringField2': _('ECO Tree'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )


    return [("ECOTREE", resp_file)]


