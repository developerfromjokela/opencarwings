import os
import ipaddress
import socket
from urllib.parse import urlparse, urlunparse
from drf_yasg.generators import OpenAPISchemaGenerator


class SchemaGenerator(OpenAPISchemaGenerator):
  def get_schema(self, request=None, public=False):
    schema = super(SchemaGenerator, self).get_schema(request, public)
    schema.basePath = os.path.join(schema.basePath, 'api/')
    return schema

class OTPNotEnabledError(Exception):
  pass

def sanitize_external_url(user_input: str) -> str:
  try:
    parsed = urlparse(user_input)
  except Exception as e:
    raise ValueError("Malformed URL") from e

  if parsed.scheme not in ('http', 'https'):
    raise ValueError("Unsupported scheme, only http or https are allowed")

  hostname = parsed.hostname
  if not hostname:
    raise ValueError("URL is missing a hostname")

  try:
    addr_info = socket.getaddrinfo(hostname, None)
    for family, _, _, _, sockaddr in addr_info:
      ip_str = sockaddr[0]
      ip_obj = ipaddress.ip_address(ip_str)
      if not ip_obj.is_global:
        raise ValueError("Invalid resolved IP")
  except socket.gaierror:
    raise ValueError("Failed to resolve the hostname")

  return urlunparse((
    parsed.scheme,
    parsed.netloc,
    parsed.path,
    parsed.params,
    parsed.query,
    parsed.fragment
  ))