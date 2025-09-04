import logging
import math
import os
from datetime import timedelta, datetime
from io import BytesIO

import geopy.geocoders
import pngquant
import requests
from PIL import Image, ImageFont, ImageDraw, ImageOps
from django.utils import timezone

from tculink.carwings_proto.autodj import NOT_AVAIL_AUTODJ_ITEM
from tculink.carwings_proto.dataobjects import build_autodj_payload
from tculink.carwings_proto.utils import xml_coordinate_to_float

logger = logging.getLogger("carwings_apl")


WEATHER_CODES = {
    0: "clear",
    1: "mainly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "rime",
    51: "light_drizzle",
    53: "moderate_drizzle",
    55: "heavy_drizzle",
    # fr=freezing
    56: "fr_light_drizzle",
    57: "fr_heavy_drizzle",
    61: "slight_rain",
    63: "moderate_rain",
    65: "heavy_rain",
    66: "fr_light",
    67: "fr_heavy",
    71: "slight_snow",
    73: "moderate_snow",
    75: "heavy_snow",
    77: "grain_snow",
    80: "slight_rainshower",
    81: "moderate_rainshower",
    82: "violent_rainshower",
    85: "slight_snowshower",
    86: "heavy_snowshower",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm"
}

WEATHER_NAMES = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "cloudy",
    45: "foggy",
    48: "foggy with rime ice",
    51: "drizzling lightly",
    53: "drizzling moderately",
    55: "heavy drizzling",
    # fr=freezing
    56: "drizzling lightly freezed",
    57: "drizzling moderately freezed",
    61: "raining slightly",
    63: "raining moderately",
    65: "raining heavily",
    66: "freeze raining lightly",
    67: "freeze raining moderately",
    71: "snowing slightly",
    73: "moderate snowing",
    75: "snowing heavily",
    77: "snowing grain",
    80: "slight rain shower",
    81: "moderate rain shower",
    82: "violent rain shower",
    85: "slight snow shower",
    86: "heavy snow shower",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm"
}


def is_daylight(lat, lon):
    try:
        utc_time = timezone.now()
        lat_rad = math.radians(lat)
        day_of_year = utc_time.timetuple().tm_yday
        solar_noon = 12.0 - (lon / 15.0)
        mean_anomaly = math.radians(357.5291 + 0.98560028 * day_of_year)
        ecliptic_long = mean_anomaly + 1.9148 * math.sin(mean_anomaly) + 0.0200 * math.sin(2 * mean_anomaly) + 282.634
        declination = math.asin(math.sin(math.radians(23.44)) * math.sin(math.radians(ecliptic_long)))
        cos_hour_angle = -math.tan(lat_rad) * math.tan(declination)
        if abs(cos_hour_angle) > 1:
            return cos_hour_angle < 0
        hour_angle = math.degrees(math.acos(cos_hour_angle))
        sunrise = solar_noon - (hour_angle / 15.0)
        sunset = solar_noon + (hour_angle / 15.0)+3
        current_hour = utc_time.hour + utc_time.minute / 60.0 + utc_time.second / 3600.0
        return sunrise <= current_hour <= sunset
    except Exception as e:
        print(f"Error calculating sunlight: {e}")
        return False


def get_city(lat, lon):
    geolocator = geopy.geocoders.nominatim.Nominatim(user_agent="OpenCARWINGS", timeout=3)
    try:
        location = geolocator.reverse((lat, lon))
        city = location.raw['address'].get('city', location.raw['address'].get('town', location.raw['address'].get('municipality', location.raw['address'].get('county', "Weather nearby"))))
        suburb = location.raw['address'].get('hamlet',  location.raw['address'].get('suburb', location.raw['address'].get('city_district', None)))
        if suburb is not None and suburb != city:
            return f"{suburb}, {city}"
        return city
    except:
        return "Weather nearby"

def get_weather_data(lat, lon, tz="UTC"):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "hourly": "temperature_2m,precipitation_probability,weathercode,windspeed_10m",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
        "timezone": tz,  # Open-Meteo will return UTC, adjust locally
        "forecast_days": 7
    }
    response = requests.get(url, params=params, headers={"User-Agent": "OpenCARWINGS"})
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to fetch weather data")

def get_weather_forecast(xml_data, returning_xml, channel_id, _):
    response_chdata = NOT_AVAIL_AUTODJ_ITEM
    if (xml_data.get('base_info', None) is not None
            and xml_data['base_info'].get('vehicle', None) is not None
            and xml_data['base_info']['vehicle'].get('coordinates', None) is not None
            and xml_data['base_info']['vehicle']['coordinates'].get('datum', '') == "wgs84"):
        logger.info(xml_data['base_info']['vehicle']['coordinates'])
        try:
            car_coordinate = xml_coordinate_to_float(xml_data['base_info']['vehicle']['coordinates'])
        except Exception as e:
            logger.exception(e)
            car_coordinate = (0.0,0.0)
        city_name = get_city(car_coordinate[0], car_coordinate[1])
        car_timezone = float(xml_data['base_info'].get('navigation_settings', {}).get('time_zone', "+0.00"))
        offset = timedelta(hours=car_timezone)

        # Get current UTC time and adjust to the specified timezone
        utc_now = timezone.now()
        local_time = utc_now + offset
        current_date = local_time.date().isoformat()
        next_date = (local_time.date() + timedelta(days=1)).isoformat()

        data = get_weather_data(car_coordinate[0], car_coordinate[1], tz="auto")

        light_theme = is_daylight(car_coordinate[0], car_coordinate[1])

        periods = {
            'morning': f"{current_date}T06:00",
            'day': f"{current_date}T12:00",
            'evening': f"{current_date}T18:00",
            'night': f"{next_date}T00:00"
        }

        daily_forecast = []
        hourly = data['hourly']
        for period, local_time_str in periods.items():
            # Convert local time to UTC for Open-Meteo data

            # Find the closest matching time in the hourly data
            if local_time_str in hourly['time']:
                idx = hourly['time'].index(local_time_str)
                condition = WEATHER_CODES.get(hourly['weathercode'][idx], "unknown")
                condition_txt = WEATHER_NAMES.get(hourly['weathercode'][idx], "unknown")
                temp = hourly['temperature_2m'][idx]
                rain_chance = hourly['precipitation_probability'][idx]
                wind = hourly['windspeed_10m'][idx]
                if period == 'night' and condition == 'clear':
                    condition = 'clear_moon'
                daily_forecast.append({
                    'period': period,
                    'local_time': local_time_str.split('T')[1],
                    'condition': condition,
                    'condition_txt': condition_txt,
                    'temperature': temp,
                    'rain_chance': rain_chance,
                    'wind_speed': wind
                })

        weekly_forecast = []
        daily = data['daily']
        for i in range(len(daily['time'])):
            date = daily['time'][i]
            condition = WEATHER_CODES.get(daily['weathercode'][i], "unknown")
            condition_txt = WEATHER_NAMES.get(daily['weathercode'][i], "unknown")
            temp_max = daily['temperature_2m_max'][i]
            temp_min = daily['temperature_2m_min'][i]
            rain_chance = daily['precipitation_probability_max'][i]
            wind = daily['windspeed_10m_max'][i]
            weekly_forecast.append({
                'date': date,
                'condition': condition,
                'condition_txt': condition_txt,
                'temp_max': temp_max,
                'temp_min': temp_min,
                'rain_chance': rain_chance,
                'wind_speed': wind
            })

        resources_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images",
            "weather")
        font_file = os.path.join(resources_dir, "Helvetica.ttf")
        header_font = ImageFont.truetype(font_file, 22)
        daily_time_font = ImageFont.truetype(font_file, 15)
        temp_font = ImageFont.truetype(font_file, 28)
        detail_font = ImageFont.truetype(font_file, 18)
        text_color =  (0, 0, 0) if light_theme else (255,255,255)

        # create current day
        daily_image = Image.open(os.path.join(resources_dir, f"weather-{'light' if light_theme else 'dark'}.png"))
        draw = ImageDraw.Draw(daily_image)
        draw.text((8, 5), f"{city_name}",text_color, font=header_font)

        droplet_img = Image.open(os.path.join(resources_dir, "icons", f"droplet.png"))


        for i, daily in enumerate(daily_forecast):
            x_offset = 40 + (i*95)
            daily_item = Image.new("RGBA", (80, 210), (255, 255, 255, 0))
            daily_item_draw = ImageDraw.Draw(daily_item)
            daily_item_draw.text((20, 3), daily['local_time'], text_color, font=daily_time_font)
            icon = Image.open(os.path.join(resources_dir, "icons",  f"{daily['condition']}.png"))
            daily_item.paste(icon, (15, 18), icon)

            # temp
            temp_rounded = int(daily['temperature'])
            temp_color = (11, 114, 212)
            if temp_rounded > 15:
                temp_color = (235, 48, 35)
            daily_item_draw.text((22, 75) , str(temp_rounded), temp_color, font=temp_font)
            if daily['temperature'] <= -0.0:
                daily_item_draw.text((10, 75) , "-", temp_color, font=temp_font)

            daily_item.paste(droplet_img, (8, 115), droplet_img)


            # wind speed
            wind_speed = f"{str(int(daily['wind_speed'])).rjust(4)}\nm / s"
            text_bbox = draw.textbbox((0, 0), wind_speed, font=detail_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (80 - text_width) // 2
            y = (49 - text_height) // 2
            daily_item_draw.text((x, 160+y),wind_speed , text_color, font=detail_font)

            # rain chance
            wind_speed = f"{str(int(daily['rain_chance'])).rjust(3)} %"
            text_bbox = draw.textbbox((0, 0), wind_speed, font=detail_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (80 - text_width) // 2
            y = (49 - text_height) // 2
            daily_item_draw.text((x, 123+y),wind_speed , text_color, font=detail_font)

            daily_item = ImageOps.expand(daily_item,border=1,fill='gray')
            daily_image.paste(daily_item, (x_offset, 43), daily_item)
        daily_image_quant = BytesIO()
        daily_image.save(daily_image_quant, format='PNG')
        daily_image_buffer = pngquant.quant_data(daily_image_quant.getvalue())[1]




        weekly_image = Image.open(os.path.join(resources_dir, f"weather-{'light' if light_theme else 'dark'}.png"))
        draw = ImageDraw.Draw(weekly_image)
        draw.text((8, 5), f"{city_name}",text_color, font=header_font)

        droplet_img = Image.open(os.path.join(resources_dir, "icons", f"droplet.png"))

        temp_font = ImageFont.truetype(font_file, 24)
        detail_font = ImageFont.truetype(font_file, 15)

        for i, weekly in enumerate(weekly_forecast):
            x_offset = 10 + (i*62)
            daily_item = Image.new("RGBA", (58, 210), (255, 255, 255, 0))
            daily_item_draw = ImageDraw.Draw(daily_item)

            day = datetime.fromisoformat(weekly['date']).strftime("%a")
            text_bbox = draw.textbbox((0, 0), day, font=detail_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (58 - text_width) // 2
            y = (15 - text_height) // 2
            daily_item_draw.text((x, y),day , text_color, font=detail_font)

            icon = Image.open(os.path.join(resources_dir, "icons",  f"{weekly['condition']}.png"))
            daily_item.paste(icon, (5, 20), icon)

            # temp
            temp_rounded = int(int(weekly['temp_max']+weekly['temp_min'])/2)
            temp_color = (11, 114, 212)
            if temp_rounded > 15:
                temp_color = (235, 48, 35)
            daily_item_draw.text((14, 75) , str(temp_rounded), temp_color, font=temp_font)
            if weekly['temp_max'] <= -0.0:
                daily_item_draw.text((8, 75) , "-", temp_color, font=temp_font)

            daily_item.paste(droplet_img, (-3, 115), droplet_img)


            # wind speed
            wind_speed = f"{str(int(weekly['wind_speed'])).rjust(4)}\nm / s"
            text_bbox = draw.textbbox((0, 0), wind_speed, font=detail_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (58 - text_width) // 2
            y = (49 - text_height) // 2
            daily_item_draw.text((x, 160+y),wind_speed , text_color, font=detail_font)

            # rain chance
            wind_speed = f"{str(int(weekly['rain_chance'])).rjust(3)} %"
            text_bbox = draw.textbbox((0, 0), wind_speed, font=detail_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (59 - text_width) // 2
            y = (49 - text_height) // 2
            daily_item_draw.text((x, 123+y),wind_speed , text_color, font=detail_font)

            daily_item = ImageOps.expand(daily_item,border=1,fill='gray')
            weekly_image.paste(daily_item, (x_offset, 43), daily_item)
        weekly_image_quant = BytesIO()
        weekly_image.save(weekly_image_quant, format='PNG')
        weekly_image_buffer = pngquant.quant_data(weekly_image_quant.getvalue())[1]

        location_txt = city_name.replace("Weather nearby", "vehicle location")
        daily_text = f"Weather Forecast for today, near {location_txt}.\n"
        if len(daily_forecast) == 0:
            daily_text += "No forecast data available."
        for daily_item in daily_forecast:
            daily_text += f"During the {daily_item['period']}, forecasted to {daily_item['condition_txt']}. With temperature of {daily_item['temperature']} degrees celsius, wind speed of {daily_item['wind_speed']} meters per second and {daily_item['rain_chance']} percent chance of rain. \n"

        weekly_text = f"Weather Forecast for next seven days, near {location_txt}.\n"
        if len(weekly_forecast) == 0:
            weekly_text += "No forecast data available."
        for weekly_item in weekly_forecast:
            weekday = datetime.fromisoformat(weekly_item['date']).strftime("%A")
            weekly_text += f"On {weekday}, forecasted to {weekly_item['condition_txt']}. With highest temperature of {weekly_item['temp_max']} degrees celsius, lowest temperature of {weekly_item['temp_min']} degrees celsius\n"

        response_chdata = [
            {
                'itemId': 1,
                'itemFlag1': 0x00,
                'dynamicDataField1': 'Weather forecast'.encode('utf-8'),
                'dynamicDataField2': f"Weather Forecast for today, {location_txt}.".encode('utf-8'),
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
                "bigDynamicField7": daily_text.encode('utf-8'),
                "bigDynamicField8": daily_text.encode('utf-8'),
                "iconField": 0x310,
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
                "imageDataField": daily_image_buffer,
            },
            {
                'itemId': 2,
                'itemFlag1': 0x00,
                'dynamicDataField1': 'Weather forecast'.encode('utf-8'),
                'dynamicDataField2': f"Weather Forecast for next seven days, {location_txt}.".encode('utf-8'),
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
                "bigDynamicField7": weekly_text.encode('utf-8'),
                "bigDynamicField8": weekly_text.encode('utf-8'),
                "iconField": 0x310,
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
                "imageDataField": weekly_image_buffer,
            }
        ]

    resp_file = build_autodj_payload(
        0,
        channel_id,
        response_chdata,
        {
            "type": 6,
            "data": b'\x01'
        },
        extra_fields={
            'stringField1': 'Weather Forecast'.encode('utf-8'),
            'stringField2': 'Weather Forecast'.encode('utf-8'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )


    return [("WEATHER", resp_file)]







