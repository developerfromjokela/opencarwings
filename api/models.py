import uuid

from django.contrib.auth import get_user_model
from django.db import models


# Model to store token metadata
class TokenMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='token_metadata')
    lang = models.CharField(max_length=10, default='en')
    token = models.CharField(max_length=500, unique=True)  # Store refresh token
    device_type = models.CharField(max_length=100, blank=True)  # e.g., iOS, Android, Web
    device_os = models.CharField(max_length=100, blank=True)  # e.g., iOS 16.2
    app_version = models.CharField(max_length=50, blank=True)  # e.g., 1.0.3
    push_notification_key = models.CharField(max_length=500, blank=True)  # Push notification token
    ip_address = models.GenericIPAddressField(blank=True, null=True)  # Client IP
    user_agent = models.TextField(blank=True)  # Browser or device user agent
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'token_metadata'

    def __str__(self):
        return f"{self.user.username} - {self.device_type} - {self.created_at}"