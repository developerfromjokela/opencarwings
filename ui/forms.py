from django import forms

class SettingsForm(forms.Form):
    unit_id = forms.CharField(label="Unit ID", max_length=14, required=True, strip=True, min_length=5)
    tcu_id = forms.CharField(label="TCU ID", max_length=14, required=True, strip=True, min_length=5)
    sim_id = forms.CharField(label="SIM ID", max_length=22, required=True, strip=True, min_length=5)

class Step2Form(forms.Form):
    unit_id = forms.CharField(label="Unit ID", max_length=14, required=True, strip=True, min_length=5)
    tcu_id = forms.CharField(label="TCU ID", max_length=14, required=True, strip=True, min_length=5)
    sim_id = forms.CharField(label="SIM ID", max_length=22, required=True, strip=True, min_length=5)
    vin = forms.CharField(label="VIN", max_length=22, required=True, strip=True, min_length=5)

class Step3Form(forms.Form):
    nickname = forms.CharField(label="Nickname", max_length=64, required=True, strip=True, min_length=5)


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput())
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

class ChangeCarwingsPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(), max_length=16)

class AccountForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(), max_length=16)
    notifications = forms.BooleanField(widget=forms.CheckboxInput(), required=False)