import io
import logging
logger = logging.getLogger("carwings")

from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from tculink.carwings_proto.applications.ap import handle_ap
from tculink.carwings_proto.applications.dj import handle_dj
from tculink.carwings_proto.applications.gls import handle_gls
from tculink.carwings_proto.applications.pi import handle_pi
from tculink.carwings_proto.databuffer import decompress_body, parse_carwings_files
from tculink.carwings_proto.xml import parse_carwings_xml

@csrf_exempt
def carwings_http_gateway(request):
    """Handle Carwings telematics POST request."""
    # Check headers
    if request.method != 'POST' or request.headers.get('Content-Type') != 'application/x-carwings-nz'\
            or ('User-Agent' not in request.headers or 'NISSAN CARWINGS' not in request.headers['User-Agent']):
        return redirect('/')

    # Get compressed body
    compressed_data = request.body
    if not compressed_data:
        return HttpResponse(status=400)

    decompressed_body = decompress_body(compressed_data)
    files = parse_carwings_files(decompressed_body)

    # Parse XML
    if not files[0]['name'].endswith('.xml'):
        logger.warning("No XML file!")
        return HttpResponse(status=400)

    parsed_xml = parse_carwings_xml(files[0]['content'].decode('utf-8'))

    logger.info("XML:")
    logger.info(parsed_xml)

    if "service_info" not in parsed_xml:
        logger.warning("No service info in XML file!")
        return HttpResponse(status=400)


    resp_buffer = bytearray()

    # Authentication
    if parsed_xml["service_info"]["application"]["name"] == "AP":
        ap_resp = handle_ap(parsed_xml, files)
        if ap_resp is not None:
            resp_buffer = ap_resp

    # AutoDJ (information channels)
    if parsed_xml["service_info"]["application"]["name"] == "DJ":
        dj_resp = handle_dj(parsed_xml, files)
        if dj_resp is not None:
            resp_buffer = dj_resp

    # Probe (vehicle data)
    if parsed_xml["service_info"]["application"]["name"] == "PI":
         pi_resp = handle_pi(parsed_xml, files)
         if pi_resp is not None:
             resp_buffer = pi_resp

    # google
    if parsed_xml["service_info"]["application"]["name"] == "GLS":
        gls_resp = handle_gls(parsed_xml, files)
        if gls_resp is not None:
            resp_buffer = gls_resp

    logger.info("Binary response length: %d", len(resp_buffer))

    # Return binary response
    return HttpResponse(io.BytesIO(resp_buffer), content_type="application/x-carwings-nz")