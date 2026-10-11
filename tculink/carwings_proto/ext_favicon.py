"""
External User Favicons
"""
import hashlib
import logging
from typing import TypedDict
from urllib.parse import urlunparse, urlparse, parse_qsl, urlencode, urljoin
from tculink import VERSION
import requests
from django.conf import settings
from django.core.cache import cache
from api.utils import sanitize_external_url

logger = logging.getLogger("carwings_icn")


class UserFavicon(TypedDict):
    valid: bool
    data: bytes|None
    mimetype: str|None

class FaviconFetchError(Exception):
    pass

APPROVED_IMGFORMAT = [
    ("image/png", b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", b"\xff\xd8\xff"),
]

FAVICON_CACHE_TIMEOUT = 3*60*60
if hasattr(settings, 'FAVICON_CACHE_TIMEOUT') and settings.FAVICON_CACHE_TIMEOUT > 0:
    FAVICON_CACHE_TIMEOUT = settings.FAVICON_CACHE_TIMEOUT

def _request_img(url, session=requests.Session()) -> UserFavicon|None:
    # 4 sec least annoying timeout while accounting inet speed, 4*16=64 sec of worst case process time
    response = session.get(url, timeout=4, stream=True)
    if response.status_code == 200 and len(response.content) <= 1800:
        content = response.content
        determined_mime = next((mime for mime, sig in APPROVED_IMGFORMAT if content.startswith(sig)), None)

        if determined_mime is not None:
            return {"valid": True, "data": content, "mimetype": determined_mime}
    return None

def _fetch_favicon(target_url):
  session = requests.Session()
  session.headers.update({"User-Agent": f"OpenCARWINGS/{VERSION}"})

  if hasattr(settings, 'USER_CONTENT_PROXY'):
      session.proxies = settings.USER_CONTENT_PROXY

  base_url = target_url if target_url.endswith("/") else target_url + "/"
  path_url = urljoin(base_url, "favicon.png")

  direct_img = _request_img(path_url, session=session)
  if direct_img:
      return direct_img

  parsed_url = urlparse(target_url)

  query_params = dict(parse_qsl(parsed_url.query))
  query_params["favicon"] = "1"

  new_query = urlencode(query_params)
  query_url = urlunparse((
      parsed_url.scheme,
      parsed_url.netloc,
      parsed_url.path,
      parsed_url.params,
      new_query,
      parsed_url.fragment,
  ))

  direct_img = _request_img(query_url, session=session)
  if direct_img:
      return direct_img

  raise FaviconFetchError

def _build_icon_cache_key(channel_url: str) -> str:
    return "icn_"+hashlib.md5(channel_url.encode()).hexdigest()

def invalidate_icon_cache(channel_url: str) -> bool:
    return cache.delete(_build_icon_cache_key(channel_url))

def get_user_icon(channel_url, skip_cache=False, skip_failed_cache=False) -> UserFavicon:
    cache_key = _build_icon_cache_key(channel_url)
    fail_cache_key = "f"+_build_icon_cache_key(channel_url)
    try:
        if cache.has_key(fail_cache_key) and not skip_failed_cache:
            return {"valid": False, "data": None, "mimetype": None}

        if cache.has_key(cache_key) and not skip_cache:
            cached_img: UserFavicon = cache.get(cache_key)
            return cached_img

        fetched_imgdata = _fetch_favicon(sanitize_external_url(channel_url))
        cache.set(cache_key, fetched_imgdata, timeout=FAVICON_CACHE_TIMEOUT)
        return fetched_imgdata
    except FaviconFetchError:
        logger.debug(f"Fetching favicon for {channel_url} failed!")
        cache.set(fail_cache_key, True, timeout=int(FAVICON_CACHE_TIMEOUT/2))
    except Exception as e:
        logger.exception(e)

    return {"valid": False, "data": None, "mimetype": None}
