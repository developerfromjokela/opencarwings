import requests
from datetime import datetime, timedelta
from tculink.sms import BaseSMSProvider
from django.utils.translation import gettext_lazy as _


class ProviderMonogoto(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('username', _("Username")),
        ('password', _("Password")),
        ('thing_id', _("Thing ID")),
    ]
    HELP_TEXT = _("Credentials are available in Monogoto dashboard. Thing ID can be found in the URL when viewing your SIM. It has this structure: ThingId_ICCID_9999999999999999999")

    def __init__(self):
        self.token = None
        self.token_expiry = None

    def _get_token(self, username, password):
        """Authenticate and get token if needed"""
        now = datetime.now()
        if self.token and self.token_expiry and now < self.token_expiry:
            return self.token

        auth_url = 'https://console.monogoto.io/Auth'
        auth_data = {
            "UserName": username,
            "Password": password
        }
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(auth_url, json=auth_data, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            # Token lasts 4 hours
            self.token_expiry = now + timedelta(hours=4)
            return self.token
        else:
            raise Exception(f"Authentication failed: {response.status_code} - {response.text}")

    def send(self, message, configuration):
        if "username" not in configuration or "password" not in configuration or "thing_id" not in configuration:
            raise Exception("Configuration is incomplete")

        username = configuration['username']
        password = configuration['password']
        thing_id = configuration['thing_id']

        # Get token
        token = self._get_token(username, password)

        # Send SMS
        sms_url = f'https://console.monogoto.io/thing/{thing_id}/sms'
        sms_data = {
            "Message": message,
            "From": "OpenCarwings Server"
        }
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'User-Agent': 'OpenCarWings/1.0'
        }

        response = requests.post(sms_url, json=sms_data, headers=headers, timeout=10)

        # If token is expired (401), try to refresh it and retry once
        if response.status_code == 401:
            self.token = None  # Force token refresh
            token = self._get_token(username, password)
            headers['Authorization'] = f'Bearer {token}'
            response = requests.post(sms_url, json=sms_data, headers=headers, timeout=10)

        return response.status_code == 200
