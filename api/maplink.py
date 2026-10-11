import re
from http.cookiejar import CookiePolicy
from urllib.parse import urlparse, parse_qs, unquote

import requests
from django.conf import settings


def parse_google_url(url):
    name_regex = r'(?<=/place/).*?(?=/)'
    data_block = r'(?<=data=).*?(?=\?|\/|$)'
    datablock_search = re.search(data_block, url)
    name_search = re.search(name_regex, url)

    if datablock_search is not None:
        name = None
        address = None
        if name_search is not None:
            name = unquote(name_search[0].replace("+", " "))
            if "," in name:
                name_split = name.split(",")
                address = name
                name = name_split[0]
        datablock = unquote(datablock_search[0])

        parts = [p for p in datablock.split('!') if p]
        if parts:
            root = curr = []
            stack = [root]
            counts = [len(parts)]

            for p in parts:
                kind, value = p[1:2], p[2:]
                counts = [c - 1 for c in counts]

                if kind == 'm':
                    new_arr = []
                    curr.append(new_arr)
                    stack.append(new_arr)
                    curr = new_arr
                    counts.append(int(value) if value.isdigit() else 0)
                else:
                    curr.append({'b': lambda x: x == '1',
                                 'd': float, 'f': float,
                                 'i': int, 'u': int, 'e': int}.get(kind, str)(value))

                while counts and counts[-1] == 0 and len(stack) > 1:
                    stack.pop()
                    counts.pop()
                    curr = stack[-1]

            def flatten(arr):
                return flatten(arr[0]) if isinstance(arr, list) and len(arr) == 1 else \
                    [flatten(x) for x in arr] if isinstance(arr, list) else arr

            parsed_data = flatten(root)

            lat = None
            lon = None

            for item in parsed_data:
                if isinstance(item, str):
                    code_split = item.split(':')
                    if len(code_split) == 2 and code_split[1].startswith('0x') and len(
                            settings.GOOGLE_API_KEY) > 0:
                        cid_info = requests.get(
                            f"https://maps.googleapis.com/maps/api/place/details/json?cid={int(code_split[1], 16)}&key={settings.GOOGLE_API_KEY}")
                        try:
                            json_info = cid_info.json()
                            if "result" in json_info:
                                lat = json_info['result']['geometry']['location']['lat']
                                lon = json_info['result']['geometry']['location']['lng']
                                name = json_info['result']['name']
                                address = json_info['result']['formatted_address']
                                break
                        except Exception as e:
                            continue
                if isinstance(item, list) and len(item) > 2:
                    for block in item:
                        if isinstance(block, list) and len(block) == 2:
                            if (-90 < block[0] < 90) and (-180 < block[1] < 180):
                                lat = block[0]
                                lon = block[1]
                                break
                if isinstance(item, list) and len(item) == 2:
                    if (-90 < item[0] < 90) and (-180 < item[1] < 180):
                        lat = item[0]
                        lon = item[1]
                        break

            if lat is not None and lon is not None:
                return {
                    "lat": lat,
                    "lon": lon,
                    "name": name,
                    "address": address,
                }

    return None


def parse_normal_gmaps_url(url):
    try:
        gmaps_url = urlparse(url)
        gmaps_query = parse_qs(gmaps_url.query)
        if "ftid" in gmaps_query and len(settings.GOOGLE_API_KEY) > 0:
            code_split = gmaps_query['ftid'][0].split(':')
            if len(code_split) == 2 and code_split[1].startswith('0x'):
                cid_info = requests.get(
                    f"https://maps.googleapis.com/maps/api/place/details/json?cid={int(code_split[1], 16)}&key={settings.GOOGLE_API_KEY}")
                try:
                    json_info = cid_info.json()
                    if "result" in json_info:
                        lat = json_info['result']['geometry']['location']['lat']
                        lon = json_info['result']['geometry']['location']['lng']
                        name = json_info['result']['name']
                        address = json_info['result']['formatted_address']
                        return {
                            "lat": lat,
                            "lon": lon,
                            "name": name,
                            "address": address.strip()
                        }
                except Exception as e:
                    ...
        if "q" in gmaps_query:
            s = requests.Session()

            class BlockAll(CookiePolicy):
                return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
                netscape = True
                rfc2965 = hide_cookie2 = False

            s.cookies.set_policy(BlockAll())
            redir_count = 0
            resp = None
            initial_url = url
            while redir_count < 5:
                resp = s.get(initial_url, timeout=3, allow_redirects=False, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'})
                if resp.headers.get('location'):
                    initial_url = resp.headers['location']
                    redir_count += 1
                else:
                    break

            coords_regex = r"-?\d{1,3}\.\d+,-?\d{1,3}\.\d+"
            name_regex = r"(?<=/place/).*?(?=/)"
            place_url_regex = r"(\/maps\/preview\/|\/maps\/)place\/[\w\s%+,]+\/.*?(?=\\\")"

            name = None
            lat = None
            lon = None
            address = None

            place_url = re.search(place_url_regex, resp.text)

            if place_url is not None:
                coords_result = re.search(coords_regex, place_url[0])
                name_results = re.search(name_regex, place_url[0])
                if coords_result is not None:
                    coords_split = coords_result[0].split(",")
                    if len(coords_split) == 2:
                        lat = float(coords_split[0])
                        lon = float(coords_split[1])
                        if not (-90 < lat < 90) or not (-180 < lon < 180):
                            lat = None
                            lon = None
                if name_results is not None:
                    name = unquote(name_results[0].replace("+", " "))
                    name_split = name.split(", ")
                    if len(name_split) > 2:
                        name = name_split[0]
                        address = ",".join(name_split[1:])

                    if lat is not None and lon is not None:
                        return {
                            "lat": lat,
                            "lon": lon,
                            "name": name,
                            "address": address.strip()
                        }

            query_split = unquote(gmaps_query["q"][0].replace("+", " ")).split(",")
            if len(query_split) == 2:
                lat = float(query_split[0])
                lon = float(query_split[1])

                if name is None:
                    name = "Dropped Pin"

                if (-90 < lat < 90) and (-180 < lon < 180):
                    return {
                        'lat': lat,
                        'lon': lon,
                        'name': name,
                        'address': address
                    }
            elif len(query_split) > 2:
                if lat is None or lon is None:
                    return None

                place_name = query_split[0]
                if name is None:
                    name = place_name
                if address is None:
                    address = ",".join(query_split[1:])

                return {
                    "lat": lat,
                    "lon": lon,
                    "name": name,
                    "address": address.strip()
                }


    except Exception as e:
        return None

def parse_map_link(map_url) -> dict|None:
    parsed_map_url = urlparse(map_url)
    map_url_query = parse_qs(parsed_map_url.query)
    location = None

    if "maps.apple" == parsed_map_url.hostname or "maps.apple.com" == parsed_map_url.hostname:
        if parsed_map_url.hostname == "maps.apple":
            resp = requests.get(map_url, allow_redirects=False, timeout=3, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'})
            redir_location = resp.headers.get('Location', '')
            parsed_map_url = urlparse(redir_location)
            map_url_query = parse_qs(parsed_map_url.query)
        if "coordinate" in map_url_query and "name" in map_url_query:
            location = map_url_query['coordinate'][0]
            gps_coords = location.split(",")
            if len(gps_coords) == 2:
                lat = float(gps_coords[0])
                lon = float(gps_coords[1])

                if (-90 < lat < 90) and (-180 < lon < 180):
                    location = {
                        'lat': lat,
                        'lon': lon,
                        'name': map_url_query["name"][0],
                        'address': map_url_query.get('address', [None])[0]
                    }

    if parsed_map_url.hostname.endswith("google.com") and "data=" in parsed_map_url.path:
        location = parse_google_url(map_url)

    if parsed_map_url.hostname.endswith("goo.gl"):
        resp = requests.get(map_url, allow_redirects=False, timeout=3, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'})
        redir_location = resp.headers.get('Location', '')
        parsed_redir_url = urlparse(redir_location)
        if parsed_redir_url.hostname.endswith("google.com") and 'data=' in redir_location:
            location = parse_google_url(redir_location)
        if parsed_redir_url.hostname == "maps.google.com":
            location = parse_normal_gmaps_url(redir_location)

    if parsed_map_url.hostname == "maps.google.com":
        location = parse_normal_gmaps_url(map_url)

    return location
