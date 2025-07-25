import re

import django.conf
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from db.models import Car, COMMAND_TYPES, AlertHistory, EVInfo, LocationInfo, TCUConfiguration, PERIODIC_REFRESH, \
    PERIODIC_REFRESH_ACTIVE, CAR_COLOR
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
        "car_color_choices": CAR_COLOR
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
                        "vin": form.cleaned_data['vin'].strip(),
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