from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from db.models import User
from tculink.utils.password_hash import password_hash


class SettingsForm(forms.Form):
    unit_id = forms.CharField(label="Unit ID", max_length=14, required=True, strip=True, min_length=5)
    tcu_id = forms.CharField(label="TCU ID", max_length=14, required=True, strip=True, min_length=5)
    sim_id = forms.CharField(label="SIM ID", max_length=22, required=True, strip=True, min_length=5)
    nickname = forms.CharField(label=_("Nickname"), max_length=64, required=True, strip=True, min_length=2)

class Step2Form(forms.Form):
    unit_id = forms.CharField(label="Unit ID", max_length=14, required=True, strip=True, min_length=5)
    tcu_id = forms.CharField(label="TCU ID", max_length=14, required=True, strip=True, min_length=5)
    sim_id = forms.CharField(label="SIM ID", max_length=22, required=True, strip=True, min_length=5)
    vin = forms.CharField(label="VIN", max_length=22, required=True, strip=True, min_length=5)

class Step3Form(forms.Form):
    nickname = forms.CharField(label=_("Nickname"), max_length=64, required=True, strip=True, min_length=5)


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput())
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

class ChangeCarwingsPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(), max_length=16)

class AccountForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(), max_length=254)
    notifications = forms.BooleanField(widget=forms.CheckboxInput(), required=False)

class SignUpForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(), max_length=254)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = _('Password')
        self.fields['password2'].label = _('Password Confirmation')
        self.fields['tcu_pass_hash'].label = _('TCU Password')

        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None

    def clean_tcu_pass_hash(self):
        return password_hash(self.cleaned_data.get('tcu_pass_hash'))

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'tcu_pass_hash')
        help_texts = {
            'username': "Can include only letters, numbers, dashes, dots and underscores",
            'tcu_pass_hash': "This password is used for signing in to your account inside the car"
        }