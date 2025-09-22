import re
from http.cookiejar import DefaultCookiePolicy, CookiePolicy
from urllib.parse import urlparse, parse_qs, unquote

import django.conf
import requests
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from db.models import Car, COMMAND_TYPES, AlertHistory, EVInfo, LocationInfo, TCUConfiguration, PERIODIC_REFRESH, \
    PERIODIC_REFRESH_ACTIVE, CAR_COLOR, CRMLatest, CRMLifetime, CRMTripRecord, CRMMonthlyRecord, CRMChargeHistoryRecord, \
    CRMChargeRecord, CRMABSHistoryRecord, CRMExcessiveIdlingRecord, CRMExcessiveAirconRecord, CRMTroubleRecord, \
    CRMMSNRecord, DOTFile
from tculink.utils.password_hash import check_password_validity, password_hash
from .forms import Step2Form, Step3Form, SettingsForm, ChangeCarwingsPasswordForm, AccountForm, SignUpForm
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from django.utils.translation import gettext_lazy as _

from .serializers import MapLinkResolverResponseSerializer, MapLinkResolverInputSerializer

SETUP_STEPS = [
    {"index": 1, "name": _("TCU setup")},
    {"index": 2, "name": _("TCU identifiers")},
    {"index": 3, "name": _("Basic information")},
    {"index": 4, "name": _("SMS configuration")},
    {"index": 5, "name": _("Car added")},
]

def get_class( kls ):
    parts = kls.split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)
    return m

UI_SMS_PROVIDERS = []


for provider_id, provider in django.conf.settings.SMS_PROVIDERS.items():
    provider_class = get_class(provider[1])
    UI_SMS_PROVIDERS.append({
        'id': provider_id,
        'name': provider[0],
        'fields': provider_class.CONFIGURATION_FIELDS,
        'help': provider_class.HELP_TEXT
    })


class ChangePasswordView(PasswordChangeView):
    form_class = PasswordChangeForm
    success_url = '/account'
    template_name = 'ui/change_password.html'


class ResetPasswordView(SuccessMessageMixin, PasswordResetView):
    template_name = 'ui/reset_password.html'
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    success_message = "We've emailed you instructions for setting your password, " \
                      "if an account exists with the email you entered. You should receive them shortly." \
                      " If you don't receive an email, " \
                      "please make sure you've entered the address you registered with, and check your spam folder."
    success_url = '/signin'


def account(request):
    if not request.user.is_authenticated:
        return redirect('signin')
    account_form = AccountForm()
    account_form.initial['email'] = request.user.email
    account_form.initial['notifications'] = request.user.email_notifications
    account_form.initial['units_imperial'] = request.user.units_imperial
    api_key, __ = Token.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            request.user.email = form.cleaned_data['email']
            request.user.email_notifications = form.cleaned_data['notifications']
            request.user.units_imperial = form.cleaned_data['units_imperial']
            request.user.save()
            messages.success(request, _("Account successfully updated!"))
            return redirect('account')
        else:
            messages.error(request, _("Please fill the form correctly and try again."))
    return render(request, 'ui/account.html', {'user': request.user, 'form': account_form, 'api_key': api_key.key})

@swagger_auto_schema(
    operation_description="Reset API-key. ONLY accessible from web portal!",
    method="post",
    responses={
        status.HTTP_200_OK: "Reset successfully!",
    },
)
@api_view(['POST'])
def reset_apikey(request):
    if not request.user.is_authenticated:
        return redirect('signin')
    if isinstance(request.auth, Token):
        return Response({'status': False, 'cause': 'Cannot reset API token with another API token!'}, status=401)
    api_key, _ = Token.objects.get_or_create(user=request.user)
    api_key.delete()
    return Response({"status": True}, status=status.HTTP_200_OK)

@swagger_auto_schema(
    operation_description="Resolve maps link from Google or Apple into location",
    tags=['maplink'],
    request_body=MapLinkResolverInputSerializer(),
    method="post",
    responses={
        status.HTTP_200_OK: MapLinkResolverResponseSerializer(),
    },
)
@api_view(['POST'])
def resolve_maps_link(request):
    if not request.user.is_authenticated and not django.conf.settings.DEBUG:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    url_input = MapLinkResolverInputSerializer(data=request.data)
    if not url_input.is_valid():
        return Response({'status': False, "cause": ",".join(url_input.errors)}, status=status.HTTP_400_BAD_REQUEST)
    location = None

    map_url = url_input.validated_data['url']
    if not map_url.startswith('https://'):
        map_url = 'https://' + map_url

    try:
        parsed_map_url = urlparse(map_url)
        map_url_query = parse_qs(parsed_map_url.query)

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
                        return flatten(arr[0]) if isinstance(arr, list) and len(arr) == 1 and isinstance(arr[0],
                                                                                                         list) else [
                            flatten(x) for x in arr] if isinstance(arr, list) else arr

                    parsed_data = flatten(root)

                    lat = None
                    lon = None

                    for item in parsed_data:
                        if isinstance(item, str):
                            code_split = item.split(':')
                            if len(code_split) == 2 and code_split[1].startswith('0x') and len(django.conf.settings.GOOGLE_API_KEY) > 0:
                                cid_info = requests.get(f"https://maps.googleapis.com/maps/api/place/details/json?cid={int(code_split[1], 16)}&key={django.conf.settings.GOOGLE_API_KEY}")
                                try:
                                    json_info = cid_info.json()
                                    if "result" in json_info:
                                        lat = json_info['result']['geometry']['location']['lat']
                                        lon = json_info['result']['geometry']['location']['lng']
                                        name = json_info['result']['name']
                                        address = json_info['result']['formatted_address']
                                        break
                                except Exception as e:
                                    print(e)
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
                if "ftid" in gmaps_query and len(django.conf.settings.GOOGLE_API_KEY) > 0:
                    code_split = gmaps_query['ftid'][0].split(':')
                    if len(code_split) == 2 and code_split[1].startswith('0x'):
                        cid_info = requests.get(
                            f"https://maps.googleapis.com/maps/api/place/details/json?cid={int(code_split[1], 16)}&key={django.conf.settings.GOOGLE_API_KEY}")
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
                            print(e)
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
                        resp = s.get(initial_url, timeout=3, allow_redirects = False, headers={
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
                print(e)
                return None


        if "maps.apple.com" in parsed_map_url.hostname:
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

        if "google.com" in parsed_map_url.hostname and "data=" in parsed_map_url.path:
            location = parse_google_url(map_url)

        if "goo.gl" in parsed_map_url.hostname:
            resp = requests.get(map_url, allow_redirects=False, timeout=3, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'})
            redir_location = resp.headers.get('Location', '')
            if "google.com" in redir_location and 'data=' in redir_location:
                location = parse_google_url(redir_location)
            if redir_location.startswith("https://maps.google.com"):
                location = parse_normal_gmaps_url(redir_location)

        if parsed_map_url.hostname == "maps.google.com":
            location = parse_normal_gmaps_url(map_url)


    except Exception as e:
        print(e)
        raise e
        location = None


    return Response({'status': True, "location": location}, status=status.HTTP_200_OK)


def change_carwings_password(request):
    if not request.user.is_authenticated:
        return redirect('signin')
    if request.method == 'POST':
        form = ChangeCarwingsPasswordForm(request.POST)
        if form.is_valid():
            result, msg = check_password_validity(form.cleaned_data['new_password'])
            if not result:
                messages.error(request, msg)
            else:
                request.user.tcu_pass_hash = password_hash(form.cleaned_data['new_password'])
                request.user.save()
                messages.success(request, msg)
                return redirect('/account')
    return render(request, 'ui/change_carwings_password.html', {'user': request.user, 'form': ChangeCarwingsPasswordForm()})

def car_list(request):
    if not request.user.is_authenticated:
        return render(request, 'ui/landing.html')
    cars = Car.objects.filter(owner=request.user)
    return render(request, 'ui/car_list.html', {'cars': cars})

def vflash_editor(request):
    return render(request, 'ui/vflash_editor.html')

def car_detail(request, vin):
    if not request.user.is_authenticated:
        return redirect('signin')
    car = get_object_or_404(Car, vin=vin, owner=request.user)
    FILTERED_COMMANDTYPES = COMMAND_TYPES[1:]

    show_settings = False

    if request.method == 'POST':
        show_settings = True
        provider_id = request.POST.get('sms-provider', None)
        sms_provider = next((i for i in UI_SMS_PROVIDERS if i['id'] == provider_id), None)
        if sms_provider is None:
            messages.error(request, 'Please select a provider for SMS.')
        else:
            fields_correct = True
            fields = sms_provider.get('fields', [])
            sms_config = {'provider': provider_id}
            for field in fields:
                field_val = request.POST.get(f"{provider_id}-{field[0]}", "")
                if len(field_val) < 2:
                    fields_correct = False
                    break
                sms_config[field[0]] = field_val.strip()

            if fields_correct:
                car.sms_config = sms_config

                form = SettingsForm(request.POST)
                # check whether it's valid:
                if form.is_valid():
                    car.iccid = re.sub('\D', '', form.cleaned_data['sim_id'])
                    car.tcu_model = re.sub('\D', '', form.cleaned_data['tcu_id'])
                    car.tcu_serial = re.sub('\D', '', form.cleaned_data['unit_id'])
                    car.nickname = form.cleaned_data['nickname']
                    car.color = form.cleaned_data['color']
                    car.periodic_refresh = form.cleaned_data['periodic_refresh']
                    car.periodic_refresh_running = form.cleaned_data['periodic_refresh_running']
                    car.disable_auth = form.cleaned_data['disable_auth']
                    if form.cleaned_data['max_gids'] != car.ev_info.max_gids or form.cleaned_data['force_soc_display'] != car.ev_info.force_soc_display:
                        car.ev_info.max_gids = form.cleaned_data['max_gids']
                        car.ev_info.force_soc_display = form.cleaned_data['force_soc_display']
                        car.ev_info.save()
                    messages.success(request, _('Successfully saved settings.'))
                else:
                    messages.error(request, _('Please fill the form correctly'))

            else:
                messages.error(request, _('Please fill all necessary fields and try again.'))
        car.save()

    if car.last_connection is None:
        messages.info(request, _("Waiting for first connection.."))

    alerts = AlertHistory.objects.filter(car=car).order_by('-timestamp')[:30]
    context = {
        'car': car,
        'alerts': alerts,
        'command_choices': FILTERED_COMMANDTYPES,
        "providers": UI_SMS_PROVIDERS,
        "show_settings": show_settings,
        "periodic_refresh_choices": PERIODIC_REFRESH,
        "periodic_refresh_running_choices": PERIODIC_REFRESH_ACTIVE,
        "car_color_choices": CAR_COLOR,
        'sms_message': django.conf.settings.ACTIVATION_SMS_MESSAGE,
        'imperial': 'true' if request.user.units_imperial else 'false'
    }
    return render(request, 'ui/car_detail.html', context)

# Landing Page View
def index(request):
    return render(request, 'index.html')

# Signup View
def signup(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        if not django.conf.settings.SIGNUP_ENABLED:
            messages.error(request, _("Sign-up is not enabled on this instance"))
            return redirect('signin')
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, _(f'Account created for {username}! Please sign in.'))
            return redirect('signin')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = SignUpForm()
    return render(request, 'ui/signup.html', {'form': form})

# Signin View
def signin(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        username = request.POST.get('username')  # Adjust to 'email' if using email
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('/')  # Replace with your dashboard URL
        else:
            messages.error(request, _('Invalid username or password.'))
    return render(request, 'ui/signin.html')

# Logout View (Optional)
def signout(request):
    logout(request)
    return redirect('/')


# SETUP

def setup_step1(request):
    if not request.user.is_authenticated:
        return redirect('/')
    if 'step' not in request.session:
        request.session['step'] = {"current_step": 1}
    elif request.session['step']['current_step'] != 1:
        return redirect('/setup/step'+str(request.session['step']['current_step']))
    else:
        if request.method == 'POST':
            request.session['step'] = {"current_step": 2}
            return redirect('/setup/step2')
    return render(request, 'ui/setup/step1.html', {'steps': SETUP_STEPS, "current_step": request.session['step']['current_step']})

def setup_step2(request):
    if not request.user.is_authenticated:
        return redirect('/signin')
    if 'step' not in request.session:
        return redirect('/setup/step1')
    elif request.session['step']['current_step'] != 2:
        return redirect('/setup/step'+str(request.session['step']['current_step']))
    else:
        if request.method == 'POST':
            form = Step2Form(request.POST)
            # check whether it's valid:
            if form.is_valid():
                try:
                    cars_with_vin = Car.objects.filter(vin=form.cleaned_data['vin'].strip())
                    car_free = cars_with_vin.count() == 0
                    if not car_free:
                        messages.error(request, _('Car is already added. Please remove and try again.'))
                except Car.DoesNotExist:
                    car_free = True
                if car_free:
                    request.session['step'] = {
                        "current_step": 3,
                        "tcu_id": re.sub('\D', '', form.cleaned_data['tcu_id']),
                        "unit_id": re.sub('\D', '', form.cleaned_data['unit_id']),
                        "sim_id": re.sub('\D', '', form.cleaned_data['sim_id']),
                        "vin": form.cleaned_data['vin'].strip(),
                    }
                    return redirect('/setup/step3')
            else:
                messages.error(request, _('Please fill the form correctly'))
    return render(request, 'ui/setup/step2.html', {'steps': SETUP_STEPS, "current_step": request.session['step']['current_step']})

def setup_step3(request):
    if not request.user.is_authenticated:
        return redirect('/signin')
    if 'step' not in request.session:
        return redirect('/setup/step3')
    elif request.session['step']['current_step'] != 3:
        return redirect('/setup/step'+str(request.session['step']['current_step']))
    else:
        if request.method == 'POST':
            form = Step3Form(request.POST)
            # check whether it's valid:
            if form.is_valid():
                step_info = request.session['step']
                step_info['current_step'] = 4
                step_info['nickname'] = form.cleaned_data['nickname']
                request.session['step'] = step_info
                return redirect('/setup/step4')
            else:
                messages.error(request, _('Please fill the form correctly'))
    return render(request, 'ui/setup/step3.html', {'steps': SETUP_STEPS, "current_step": request.session['step']['current_step']})


def setup_step4(request):
    if not request.user.is_authenticated:
        return redirect('/signin')
    if 'step' not in request.session:
        return redirect('/setup/step1')
    elif request.session['step']['current_step'] != 4:
        return redirect('/setup/step'+str(request.session['step']['current_step']))
    else:
        if request.method == 'POST':
            provider_id = request.POST.get('sms-provider', None)
            sms_provider = next((i for i in UI_SMS_PROVIDERS if i['id'] == provider_id), None)
            if sms_provider is None:
                messages.error(request, _('Please select a provider for SMS.'))
            else:
                step_info = request.session['step']
                fields_correct = True
                fields = sms_provider.get('fields', [])
                sms_config = {'provider': provider_id}
                for field in fields:
                    field_val = request.POST.get(f"{provider_id}-{field[0]}", "")
                    if len(field_val) < 2:
                        fields_correct = False
                        break
                    sms_config[field[0]] = field_val.strip()

                if fields_correct:
                    step_info['current_step'] = 5
                    step_info['sms'] = sms_config
                    request.session['step'] = step_info
                    return redirect('/setup/step5')
                else:
                    messages.error(request, _('Please fill all necessary fields and try again.'))

    return render(request, 'ui/setup/step4.html', {'steps': SETUP_STEPS, 'providers': UI_SMS_PROVIDERS, "current_step": request.session['step']['current_step']})

def setup_step5(request):
    if not request.user.is_authenticated:
        return redirect('/signin')
    if 'step' not in request.session:
        return redirect('/setup/step1')
    elif request.session['step']['current_step'] != 5:
        return redirect('/setup/step'+str(request.session['step']['current_step']))
    else:
        if request.method == 'POST':
            composed_car = request.session['step']
            new_car = Car()
            new_car.vin=composed_car['vin']
            new_car.tcu_serial=composed_car['unit_id']
            new_car.iccid=composed_car['sim_id']
            new_car.tcu_model=composed_car['tcu_id']
            new_car.sms_config=composed_car['sms']
            new_car.nickname=composed_car['nickname']
            ev_info = EVInfo()
            tcu_config = TCUConfiguration()
            location_info = LocationInfo()
            ev_info.save()
            location_info.save()
            tcu_config.save()
            new_car.ev_info = ev_info
            new_car.location = location_info
            new_car.tcu_configuration = tcu_config
            new_car.owner = request.user
            new_car.save()
            del request.session['step']
            return redirect('/')
    return render(request, 'ui/setup/step5.html', {'steps': SETUP_STEPS, "current_step": request.session['step']['current_step']})


## probe data viewer

def probeviewer_home(request, vin):
    if not request.user.is_authenticated:
        return redirect('signin')
    car = get_object_or_404(Car, vin=vin, owner=request.user)

    try:
        latest = CRMLatest.objects.get(car=car)
    except CRMLatest.DoesNotExist:
        latest = None

    try:
        lifetime = CRMLifetime.objects.get(car=car)
    except CRMLifetime.DoesNotExist:
        lifetime = None

    trips = CRMTripRecord.objects.filter(car=car).order_by('-start_ts')
    paginator = Paginator(trips, 25)

    trips_page = request.GET.get("tp", 0)
    trips_paginator = paginator.get_page(trips_page if trips_page != 0 else 1)

    monthly = CRMMonthlyRecord.objects.filter(car=car).order_by('-start')
    paginator2 = Paginator(monthly, 12)

    months_page = request.GET.get("mp", 0)
    months_paginator = paginator2.get_page(months_page if months_page != 0 else 1)

    chargehist = CRMChargeHistoryRecord.objects.filter(car=car).order_by('-start_time')
    paginator3 = Paginator(chargehist, 8)

    chargehist_page = request.GET.get("chp", 0)
    chargehist = paginator3.get_page(chargehist_page if chargehist_page != 0 else 1)

    charge = CRMChargeRecord.objects.filter(car=car).order_by('-start_time')
    paginator4 = Paginator(charge, 8)

    charge_page = request.GET.get("cp", 0)
    charge = paginator4.get_page(charge_page if charge_page != 0 else 1)

    abs = CRMABSHistoryRecord.objects.filter(car=car).order_by('-timestamp')
    paginator5 = Paginator(abs, 8)

    abs_page = request.GET.get("ap", 0)
    abs = paginator5.get_page(abs_page if abs_page != 0 else 1)

    idling = CRMExcessiveIdlingRecord.objects.filter(car=car).order_by('-start')
    paginator6 = Paginator(idling, 30)

    idling_page = request.GET.get("idl", 0)
    idling = paginator6.get_page(idling_page if idling_page != 0 else 1)

    aircon = CRMExcessiveAirconRecord.objects.filter(car=car).order_by('-start')
    paginator7 = Paginator(aircon, 30)

    aircon_page = request.GET.get("aircon", 0)
    aircon = paginator7.get_page(aircon_page if aircon_page != 0 else 1)

    trouble = CRMTroubleRecord.objects.filter(car=car)
    paginator8 = Paginator(trouble, 30)

    trouble_page = request.GET.get("dtc", 0)
    trouble = paginator8.get_page(trouble_page if trouble_page != 0 else 1)

    msn = CRMMSNRecord.objects.filter(car=car).order_by('-timestamp')
    paginator9 = Paginator(msn, 30)

    msn_page = request.GET.get("msn", 0)
    msn = paginator9.get_page(msn_page if msn_page != 0 else 1)
    
    dotfiles = DOTFile.objects.filter(car=car).order_by('-upload_ts')
    paginator10 = Paginator(dotfiles, 30)

    dot_page = request.GET.get("dot", 0)
    dotfiles = paginator10.get_page(dot_page if dot_page != 0 else 1)


    return render(request, 'ui/probeviewer/main.html',
                  {'car': car, 'latest': latest, "lifetime": lifetime, "abs": abs, "dtc": trouble,
                   "msn": msn, "aircon": aircon, "idl": idling, "trips": trips_paginator, "chargehist": chargehist,
                   "charge": charge, "dotfiles": dotfiles, "dtc_act": trouble_page != 0, "msn_act": msn_page != 0, "aircon_act": aircon_page != 0,
                   "idl_act": idling_page != 0, "abs_act": abs_page != 0, "charge_act": charge_page != 0, "chargehist_act": chargehist_page != 0,
                   "months": months_paginator, "trips_act": trips_page != 0, "months_act": (months_page != 0 and trips_page == 0), "dot_act":  dot_page != 0})


def probeviewer_trip(request, vin, trip):
    if not request.user.is_authenticated:
        return redirect('signin')
    car = get_object_or_404(Car, vin=vin, owner=request.user)

    trip = get_object_or_404(CRMTripRecord, car=car, pk=trip)

    return render(request, 'ui/probeviewer/trip.html', {'trip': trip, 'car': car})
