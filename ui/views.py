import re
from random import randint

import django.conf
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from db.models import Car, COMMAND_TYPES, AlertHistory, EVInfo, LocationInfo, TCUConfiguration, PERIODIC_REFRESH, \
    PERIODIC_REFRESH_ACTIVE
from tculink.sms import send_using_provider
from tculink.utils.password_hash import check_password_validity, password_hash
from .forms import Step2Form, Step3Form, SettingsForm, ChangeCarwingsPasswordForm, AccountForm, SignUpForm
from .serializers import CarSerializer, AlertHistorySerializer, CarSerializerList, CommandResponseSerializer, \
    CommandErrorSerializer, StatusSerializer
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


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
    success_url = reverse_lazy('settings')
    template_name = 'ui/change_password.html'


class ResetPasswordView(SuccessMessageMixin, PasswordResetView):
    template_name = 'ui/reset_password.html'
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    success_message = "We've emailed you instructions for setting your password, " \
                      "if an account exists with the email you entered. You should receive them shortly." \
                      " If you don't receive an email, " \
                      "please make sure you've entered the address you registered with, and check your spam folder."
    success_url = reverse_lazy('signin')


def account(request):
    if not request.user.is_authenticated:
        return redirect('login')
    account_form = AccountForm()
    account_form.initial['email'] = request.user.email
    account_form.initial['notifications'] = request.user.email_notifications
    api_key, __ = Token.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            request.user.email = form.cleaned_data['email']
            request.user.email_notifications = form.cleaned_data['notifications']
            request.user.save()
            messages.success(request, _("Account successfully updated!"))
            return redirect('account')
        else:
            messages.error(request, _("Please fill the form correctry and try again."))
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
        return redirect('login')
    if isinstance(request.auth, Token):
        return Response({'status': False, 'cause': 'Cannot reset API token with another API token!'}, status=401)
    api_key, _ = Token.objects.get_or_create(user=request.user)
    api_key.delete()
    return Response({"status": True}, status=status.HTTP_200_OK)

def change_carwings_password(request):
    if not request.user.is_authenticated:
        return redirect('login')
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


def car_detail(request, vin):
    if not request.user.is_authenticated:
        return redirect('login')
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
                    car.iccid = form.cleaned_data['sim_id']
                    car.tcu_model = form.cleaned_data['tcu_id']
                    car.tcu_serial = form.cleaned_data['unit_id']
                    car.nickname = form.cleaned_data['nickname']
                    car.periodic_refresh = form.cleaned_data['periodic_refresh']
                    car.periodic_refresh_running = form.cleaned_data['periodic_refresh_running']
                    print(form.cleaned_data['disable_auth'])
                    car.disable_auth = form.cleaned_data['disable_auth']
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
        "periodic_refresh_running_choices": PERIODIC_REFRESH_ACTIVE
    }
    return render(request, 'ui/car_detail.html', context)


@swagger_auto_schema(
    operation_description="Retrieve car details",
    method='get',
    responses={
        200: CarSerializer(),
        404: 'Not found',
        401: 'Not authorized',
    }
)
@swagger_auto_schema(
    operation_description="Remove a car",
    method='delete',
    responses={
        200: StatusSerializer(),
        404: 'Not found',
        401: 'Not authorized',
    }
)
@api_view(['GET', 'DELETE'])
def car_api(request, vin):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = get_object_or_404(Car, vin=vin, owner=request.user)

    if request.method == 'DELETE':
        car.delete()
        return Response({'status': True}, status=status.HTTP_200_OK)

    serializer = CarSerializer(car)
    return Response(serializer.data)

@swagger_auto_schema(
    operation_description="Retrieve a list of cars",
    method='get',
    responses={
        200: CarSerializerList(many=True),
        401: 'Not authorized',
    }
)
@api_view(['GET'])
def cars_api(request):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = Car.objects.filter(owner=request.user)

    serializer = CarSerializerList(car, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    operation_description="Retrieve a list of alerts for a vehicle",
    method='get',
    responses={
        200: AlertHistorySerializer(many=True),
        401: 'Not authorized',
        404: 'Car not found',
    }
)
@api_view(['GET'])
def alerts_api(request, vin):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = get_object_or_404(Car, vin=vin, owner=request.user)
    alerts = AlertHistory.objects.filter(car=car).order_by('-timestamp')
    serializer = AlertHistorySerializer(alerts, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    operation_description="Send a command to your vehicle",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'command_type': openapi.Schema(type=openapi.TYPE_NUMBER, title="Command type", enum=COMMAND_TYPES),
        },
        required=['vin', 'command_type']
    ),
    method='post',
    responses={
        200: CommandResponseSerializer(),
        401: 'Not authorized',
        404: 'Car not found',
        400: CommandErrorSerializer(),
    }
)
@api_view(['POST'])
def command_api(request, vin):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = get_object_or_404(Car, vin=vin, owner=request.user)
    command_type = request.data.get('command_type')

    try:
        command_type = int(command_type)
        if command_type in dict(COMMAND_TYPES):
            try:
                sms_result = send_using_provider(django.conf.settings.ACTIVATION_SMS_MESSAGE, car.sms_config)
                if not sms_result:
                    raise Exception("Could not send SMS message")
            except Exception as e:
                print(e)
                return Response({'error': _('Failed to send SMS message to TCU. Please try again in a moment.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            car.command_type = command_type
            car.command_id = randint(10000, 99999)
            car.command_requested = True
            car.command_result = -1
            car.command_request_time = timezone.now()
            car.save()
            return Response({
                'message': f"Command '{dict(COMMAND_TYPES)[command_type]}' requested successfully",
                'car': CarSerializer(car).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid command type'}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({'error': 'Command type must be an integer'}, status=status.HTTP_400_BAD_REQUEST)


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
        return redirect('/login')
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
                        "vin": form.cleaned_data['vin'],
                    }
                    return redirect('/setup/step3')
            else:
                messages.error(request, _('Please fill the form correctly'))
    return render(request, 'ui/setup/step2.html', {'steps': SETUP_STEPS, "current_step": request.session['step']['current_step']})

def setup_step3(request):
    if not request.user.is_authenticated:
        return redirect('/login')
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
        return redirect('/login')
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
        return redirect('/login')
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