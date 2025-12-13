import datetime
import io
import logging
import math
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl
from django.core.cache import cache

import requests
from PIL import Image
from django.conf import settings
from django.utils.http import urlencode
from unidecode import unidecode

from tculink.carwings_proto.databuffer import construct_carwings_filepacket, compress_carwings
from tculink.carwings_proto.xml import carwings_create_xmlfile_content

logger = logging.getLogger("carwings_apl")

def haversine_distance(lat1, lon1, lat2, lon2):
    earth_radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c

def nominatim_radius_search(lat, lon, radius_km, query, limit=60):
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

    south = lat - delta_lat
    north = lat + delta_lat
    west = lon - delta_lon
    east = lon + delta_lon

    params = {
        'q': query,
        'format': 'json',
        'limit': limit,
        'viewbox': f"{west},{south},{east},{north}",
        'bounded': 1,
        'addressdetails': 1,
        'extratags': 1
    }

    response = requests.get("https://nominatim.openstreetmap.org/search", params=params)
    if response.status_code == 200:
        results = response.json()
        filtered = []
        for place in results:
            place_lat = float(place['lat'])
            place_lon = float(place['lon'])
            distance = haversine_distance(lat, lon, place_lat, place_lon)/1000
            filtered.append({
                'id': f"N,{place['place_id']}",
                'name': place.get('display_name', ''),
                'address': place.get('address', ''),
                'city': '',
                'region': '',
                'country': '',
                'country_code': '',
                'phone': place.get('extratags', {}).get('phone', ''),
                'rating': 0,
                'lat': place_lat,
                'lon': place_lon,
                'distance_km': round(distance, 1)
            })
        return filtered
    else:
        logger.error("Error: %d", response.status_code)
        return []

def nominatim_place_info(place_id):
    params = {
        'place_id': str(place_id),
        'format': 'json'
    }

    response = requests.get("https://nominatim.openstreetmap.org/details", params=params)
    if response.status_code == 200:
        place_info = response.json()
        address = ""
        if "street" in place_info['addresstags']:
            address += place_info['addresstags']['street']+" "
            if 'housenumber' in place_info['addresstags']:
                address += place_info['addresstags']['housenumber']+", "
        if "postcode" in place_info['addresstags']:
            address += place_info['addresstags']['postcode']+" "
        if "city" in place_info['addresstags']:
            address += place_info['addresstags']['city']
        return {
            'name': place_info.get('localname'),
            'address': address,
            'phone': place_info.get('extratags', {}).get('phone', ''),
            'website': place_info.get('website', ''),
            'photo': {'url': '', 'width': 0, 'height': 0},
            'rating': 0.0,
            'reviews': []
        }
    else:
        logger.error("Error: %d", response.status_code)
        return None

def google_radius_search(lat, lon, radius_km, query, pagetoken=None):
    params = {
        'query': query,
        'location': f"{lat},{lon}",
        'radius': radius_km*1000,
        'key': settings.GOOGLE_API_KEY,
    }
    if pagetoken is not None:
        params['pagetoken'] = pagetoken

    response = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json', params=params)
    if response.status_code == 200:
        results = response.json()
        logger.info(results)
        reformatted = []
        next_pagetoken = results.get('next_page_token', None)
        for place in results.get('results', []):
            place_lat = float(place['geometry']['location']['lat'])
            place_lon = float(place['geometry']['location']['lng'])
            distance = haversine_distance(lat, lon, place_lat, place_lon)
            logger.info("Distance: %f", distance)
            reformatted.append({
                'id': f'G,{place.get("place_id", 0)}',
                'name': place.get('name', ''),
                'address': place.get('formatted_address', ''),
                'city': '',
                'region': '',
                'country': '',
                'country_code': '',
                'phone': place.get('international_phone_number', ''),
                'rating': place.get('rating', 0.0),
                'lat': place_lat,
                'lon': place_lon,
                'distance_km': round(distance, 1)
            })
        return reformatted, next_pagetoken
    else:
        logger.error("Error: %d", response.status_code)
        return [], None

def google_place_info(place_id):
    params = {
        'place_id': str(place_id),
        'fields': 'name,formatted_address,international_phone_number,website,photo,rating,reviews',
        'key': settings.GOOGLE_API_KEY,
    }

    response = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params=params)
    if response.status_code == 200:
        place_info = response.json().get('result', {})
        photo_url = ""
        photo_size = (0,0)
        if len(place_info.get('photos', [])) > 0:
            ref_id = place_info['photos'][0].get('photo_reference')
            photo_url = "https://maps.googleapis.com/maps/api/place/photo?"+urlencode({'photo_reference': ref_id})
            photo_size = (place_info['photos'][0].get('width', 0),place_info['photos'][0].get('height', 0))

        reviews = []
        for review in place_info.get('reviews', [])[:10]:
            reviews.append({
                'rating': review.get('rating', 0.0),
                'author': review.get('author_name', ''),
                'date': datetime.date.fromtimestamp(review.get('time', 0)),
                'title': '',
                'body': review.get('text', '')
            })
        return {
            'name': place_info.get('name'),
            'address': place_info.get('formatted_address', ''),
            'phone': place_info.get('international_phone_number', ''),
            'website': place_info.get('website', ''),
            'photo': {'url': photo_url, 'width': photo_size[0], 'height': photo_size[1]},
            'rating': place_info.get('rating', 0),
            'reviews': reviews
        }
    else:
        logger.error("Error: %d", response.status_code)
        return None

def handle_gls(xml_data, files):
    if 'send_data' in xml_data['service_info']['application']:
        if len(xml_data['service_info']['application']['send_data']) == 0:
            return None
        send_data = xml_data['service_info']['application']['send_data'][0]
        id_type = send_data['id_type']
        id_value = send_data['id']
        file_content = bytearray()
        if id_type == "file":
            logger.info("Retrieving file %s", id_value)
            file_content = next((x for x in files if x['name'] == id_value), None)
            if file_content is None:
                logger.warning("File not found, %s", id_value)
                return None
            logger.debug("File content, %s", file_content['content'].hex())
            file_content = file_content['content']

        req_id = int.from_bytes(file_content[4:6], byteorder="big")
        logger.debug(req_id)

        if req_id != 0x301:
            logger.error("Invalid request id, %d", req_id)
            return None

        query_len = int.from_bytes(file_content[6:8], byteorder="big")
        query_str = file_content[8:8+query_len].decode('utf-8').rstrip('\x00')
        logger.info("GLS Query: %s", query_str)

        parsed_query = dict(parse_qsl(query_str))
        logger.debug("Parsed query: %s", parsed_query)

        if "type" not in parsed_query:
            logger.error("query type missing!")
            return None

        resp_file = bytes.fromhex('00 00 00 00 00 00 00 00 00 03 01'.replace(' ', ''))

        if parsed_query["type"] == "GLS1":
            logger.info("Sending List, Q: %s, NEAR: %s, RADIUS: %s, STARTPOS: %s", parsed_query["q"], parsed_query["near"], parsed_query["radius"], parsed_query["start"])

            resp_file += b'\x02'

            near_latlon = [float(x) for x in parsed_query["near"].split(",")]
            radius = int(parsed_query["radius"])+10
            startpos = int(parsed_query["start"])
            if len(settings.GOOGLE_API_KEY) == 0:
                results = nominatim_radius_search(near_latlon[0], near_latlon[1], radius, parsed_query["q"])[startpos:startpos+20]
                legal_notice = "OpenStreetMaps and contributors"
                total_items = len(results)
            else:
                legal_notice = "Google Maps"
                page_token = None
                if startpos != 0 and startpos <= 40:
                    scroll_pages = int(round(startpos/20, 0))
                    curr_page = 0
                    while curr_page < scroll_pages-1:
                        curr_page += 1
                        _, pagetoken = google_radius_search(near_latlon[0], near_latlon[1], radius, parsed_query["q"], page_token)
                        if pagetoken is not None:
                            page_token = pagetoken


                results, new_token = google_radius_search(near_latlon[0], near_latlon[1], radius, parsed_query["q"], page_token)
                logger.info("NEXT PAGE TOKEN: curr:%s, next:%s", page_token, new_token)
                total_items = len(results)
                if new_token is not None:
                    if startpos == 0:
                        total_items = total_items+20
                    else:
                        total_items = startpos+20

            poi_response_root = ET.Element("Local")
            ET.SubElement(poi_response_root, "LegalNotice", ).text = legal_notice
            results_root = ET.SubElement(poi_response_root, "Results", {"estresults": str(total_items), "start": str(startpos), "end": str(startpos+total_items)})
            listings = ET.SubElement(results_root, "Listings")
            for item in results:
                listing = ET.SubElement(listings, "Listing")
                ET.SubElement(listing, "Location", {"long": str(item['lon']), "lat": str(item['lat'])})
                ET.SubElement(listing, "Name").text = item['name']
                if item.get('country_code', ''):
                    ET.SubElement(listing, "CountryCode").text = item['country_code']
                elif item.get('country', ''):
                    ET.SubElement(listing, "Country").text = item['country']
                ET.SubElement(listing, "Addr").text = item['address']
                if item.get('city', ''):
                    ET.SubElement(listing, "City").text = item['city']
                if item.get('region', ''):
                    ET.SubElement(listing, "Region").text = item['region']
                if item.get('phone', ''):
                    ET.SubElement(listing, "Phone").text = item['phone']
                ET.SubElement(listing, "Reviews", {"starRating": str(item.get('rating', 0.0))})
                ET.SubElement(listing, "LatLng").text = str(item['id'])

                # distance is localized in by navigation, set as KM
                distance = ET.SubElement(listing, "Distance")
                ET.SubElement(distance, "DisplayValue").text = str(item['distance_km'])
                logger.info("DIST DISPLAYVALUE: %s", str(item['distance_km']))
                ET.SubElement(distance, "Units").text = "km"

            poi_xml_file = carwings_create_xmlfile_content(poi_response_root).encode('utf-8')
            resp_file += len(poi_xml_file).to_bytes(4, byteorder='big')
            resp_file += poi_xml_file
        elif parsed_query["type"] == "GLS2":
            logger.info("Sending info, point: %s", parsed_query["latlng"])

            resp_file += b'\x02'

            poi_id = parsed_query["latlng"]
            if poi_id.startswith('N,'):
                poi_id = poi_id[2:]
                logger.info("Nominatim Poi: %s", poi_id)
                place_info = nominatim_place_info(poi_id)
            elif poi_id.startswith('G,'):
                poi_id = poi_id[2:]
                logger.info("Google Poi: %s", poi_id)
                place_info = google_place_info(poi_id)
            else:
                logger.error("Invalid POI ID identifier!")
                return None
            logger.info(place_info)
            poi_response_root = ET.Element("Local")
            results_root = ET.SubElement(poi_response_root, "Results")
            listings = ET.SubElement(results_root, "Listings")
            if place_info is not None:
                listing = ET.SubElement(listings, "Listing")
                ET.SubElement(listing, "Name").text = place_info['name']
                if place_info.get('phone', ''):
                    ET.SubElement(listing, "Phone").text = place_info['phone']
                ET.SubElement(listing, "Addr").text = place_info['address']
                if place_info.get('website', ''):
                    homepage = ET.SubElement(listing, "Homepage")
                    ET.SubElement(homepage, "T").text = place_info.get('website', '')[:258]
                    ET.SubElement(homepage, "U").text = place_info.get('website', '')

                if place_info.get('photo', {}):
                    photo = place_info['photo']
                    logger.info("Photo: %s", photo)
                    if photo.get('width', 0) > 0 and photo.get('height', 0) > 0:
                        xml_photo = ET.SubElement(listing, "Images")
                        xml_thumb = ET.SubElement(xml_photo, "IMAGE_THUMB")
                        photo_uuid = uuid.uuid4().__str__()
                        cache.set(f"GLSPIC_{photo_uuid}", photo["url"], 60*2)
                        ET.SubElement(xml_thumb, "U").text = f"cache://{photo_uuid}"
                        ET.SubElement(xml_thumb, "IMAGE_HEIGHT").text = str(photo['height'])
                        ET.SubElement(xml_thumb, "IMAGE_WIDTH").text = str(photo['width'])

                reviews = ET.SubElement(listing, "Reviews", {'starRating': str(place_info.get('rating', 0.0)), 'start': "1", 'end': str(len(place_info.get('reviews', [])))})
                for review in place_info.get('reviews', [])[:10]:
                    xml_review = ET.SubElement(reviews, "Review")
                    ET.SubElement(xml_review, "Rating", {'starRating': str(review.get('rating', 0.0))})
                    ET.SubElement(xml_review, "Author").text = str(review.get('author', ''))
                    ET.SubElement(xml_review, "Date", {'iso8601': review.get('date', datetime.date.today()).isoformat()})
                    ET.SubElement(xml_review, "T").text = unidecode(review.get('title', ''))
                    ET.SubElement(xml_review, "S").text = unidecode(review.get('body', ''))


            poi_xml_file = carwings_create_xmlfile_content(poi_response_root).encode('utf-8')
            logger.info(poi_xml_file.decode('utf-8'))
            resp_file += len(poi_xml_file).to_bytes(4, byteorder='big')
            resp_file += poi_xml_file
        elif parsed_query["type"] == "GLS3":
            logger.info("Sending jpeg image, url: %s, width: %s, height: %s", parsed_query["url"], parsed_query["width"], parsed_query["height"])
            resp_file += b'\x02'

            url = parsed_query["url"]
            width = parsed_query["width"]
            height = parsed_query["height"]

            # retrieve photo from cache
            if url.startswith("cache://"):
                photo_uuid = url.replace("cache://", "")[:38]
                url = cache.get(f"GLSPIC_{photo_uuid}")
                cache.delete(f"GLSPIC_{photo_uuid}")

            if url.startswith('https://maps.googleapis.com/maps/api/place/photo?'):
                url = url + "&maxwidth=" + str(width) + "&maxheight=" + str(height)+"&key="+settings.GOOGLE_API_KEY
                jpeg_data = requests.get(url).content
            else:
                temp_jpeg_data = requests.get(url).content
                img = Image.open(io.BytesIO(temp_jpeg_data))
                img.thumbnail((int(width), int(height)), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                img.save(output, format='JPEG')
                jpeg_data = output.getvalue()

            resp_file += len(jpeg_data).to_bytes(4, byteorder='big')
            resp_file += jpeg_data
        elif parsed_query["type"] == "GLS4":
            logger.info("Received clickinfo, url: %s", parsed_query["url"])
            resp_file += b'\x01'
        else:
            logger.error("Invalid request type: %s", parsed_query["type"])
            return None

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})



        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "GLS"})
        ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "GLSRESP.001"})


        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)
        files.append(("response.xml", xml_str.encode("utf-8"),))
        files.append(("GLSRESP.001", resp_file,))

        return compress_carwings(construct_carwings_filepacket(files))


    return None