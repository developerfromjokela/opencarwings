import pytz
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from db.models import User, CAR_COLOR, TCU_TYPE
from tculink.utils.password_hash import password_hash

TIMEZONE_CHOICES = zip(pytz.all_timezones, pytz.all_timezones)

class SettingsForm(forms.Form):
    unit_id = forms.CharField(label="Unit ID", max_length=32, required=True, strip=True, min_length=5)
    tcu_id = forms.CharField(label="TCU ID", max_length=32, required=True, strip=True, min_length=5)
    sim_id = forms.CharField(label="SIM ID", max_length=32, required=True, strip=True, min_length=5)
    color = forms.ChoiceField(label="Car Color", choices=CAR_COLOR)
    max_gids = forms.IntegerField(label="Maximum GIDs value", required=True, min_value=0, max_value=2000)
    periodic_refresh = forms.IntegerField(label="Periodic Refresh", required=True, min_value=0, max_value=2880)
    periodic_refresh_running = forms.IntegerField(label="Periodic Refresh", required=True, min_value=0, max_value=2880)
    nickname = forms.CharField(label=_("Nickname"), max_length=64, required=True, strip=True, min_length=2)
    disable_auth = forms.BooleanField(label=_("Disable TCU authentication"), required=False)
    force_soc_display = forms.BooleanField(label=_("Show calculated battery percentage"), required=False)
    hmac_key = forms.RegexField(label=_("HMAC Key"), max_length=32, required=False, regex=r"^([0-9a-fA-F])+")

class Step0Form(forms.Form):
    tcu_type = forms.ChoiceField(label="TCU Type", choices=TCU_TYPE)
    default_color = forms.ChoiceField(label="Default Color", required=False, choices=CAR_COLOR)

class Step2Form(forms.Form):
    unit_id = forms.CharField(label="Unit ID", max_length=32, required=True, strip=True, min_length=5)
    tcu_id = forms.CharField(label="TCU ID", max_length=32, required=True, strip=True, min_length=5)
    sim_id = forms.CharField(label="SIM ID", max_length=32, required=True, strip=True, min_length=5)
    vin = forms.CharField(label="VIN", max_length=22, required=True, strip=True, min_length=5)

class Step3Form(forms.Form):
    nickname = forms.CharField(label=_("Nickname"), max_length=64, required=True, strip=True, min_length=2)


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput())
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

class ChangeCarwingsPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(), max_length=16)

class ChangeCommandPinForm(forms.Form):
    new_pin = forms.CharField(widget=forms.NumberInput(), max_length=4, min_length=4)
    new_pin_confirm = forms.CharField(widget=forms.NumberInput(), max_length=4, min_length=4)

    def full_clean(self):
        super().full_clean()
        new_pin = self.data.get('new_pin')
        new_pin_confirm = self.data.get('new_pin_confirm')

        if new_pin or new_pin_confirm:
            if new_pin != new_pin_confirm:
                self.add_error('new_pin_confirm',  _('PIN codes do not match.'))

class AccountForm(forms.Form):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(), max_length=254)
    notifications = forms.BooleanField(label=_("Notifications"), widget=forms.CheckboxInput(), required=False)
    units_imperial = forms.BooleanField(label=_("Imperial Units"), widget=forms.CheckboxInput(), required=False)
    timezone = forms.ChoiceField(label=_("Timezone"), choices=TIMEZONE_CHOICES, required=False)

class ProbeConfigForm(forms.Form):
    new_config_id = forms.IntegerField(label="New Config ID", required=False)
    request = forms.CharField(widget=forms.HiddenInput(), required=True)


class SignUpForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(), max_length=254)
    timezone = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = _('Password')
        self.fields['password2'].label = _('Password Confirmation')
        self.fields['tcu_pass_hash'].label = "CARWINGS " + _('Password')

        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None

    def clean_tcu_pass_hash(self):
        return password_hash(self.cleaned_data.get('tcu_pass_hash'))

    def clean_timezone(self):
        tz = self.cleaned_data.get('timezone')
        if tz and tz not in pytz.all_timezones:
            return ''  # ignore invalid/spoofed values instead of erroring out
        return tz

    def save(self, commit=True):
        user = super().save(commit=False)
        tz = self.cleaned_data.get('timezone')
        if tz:
            user.timezone = tz
        if commit:
            user.save()
        return user

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'tcu_pass_hash')
        help_texts = {
            'username': _("Can include only letters, numbers, dashes, dots and underscores"),
            'tcu_pass_hash': _("This password is used for signing in to your account inside the car")
        }