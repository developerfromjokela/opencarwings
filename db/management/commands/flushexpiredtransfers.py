from django.core.management.base import BaseCommand
from django.utils import timezone

from db.models import CarTransferRequest


class Command(BaseCommand):
    help = "Delete expired car transfer requests."

    def handle(self, *args, **options):
        CarTransferRequest.objects.filter(expiration_time__lte=timezone.now()).delete()
