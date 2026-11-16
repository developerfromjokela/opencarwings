import logging
from datetime import timedelta

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from tculink.coordinators import convert_abrp_for_coordinator
from db.models import Car

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync data to 3rd party services'

    def handle_abrp_upload(self):
        update_delta = timezone.now() - timedelta(minutes=2) # upload results that fresh
        cars = Car.objects.filter(abrp_token__isnull=False, ev_info__last_updated__gte=update_delta)
        if cars.count() == 0:
            print("No cars need updating")
            return
        bulk_data = []
        for car in cars:
            convert_abrp = convert_abrp_for_coordinator(car.tcu_type)
            if convert_abrp is not None:
                converted_abrp = convert_abrp(car)
                converted_abrp["utc"] = int(car.last_connection.strftime('%s'))
                converted_abrp["lat"] = float(car.location.lat)
                converted_abrp["lon"] = float(car.location.lon)
                bulk_data.append({
                    "token": car.abrp_token,
                    "tlm_list": [converted_abrp]
                })
            else:
                print("tcu type not supported!")

        abrp_resp = requests.post(
            'https://api.iternio.com/1/tlm/bulk',
            # APIKEY allowed by iternio staff to be hard-coded
            headers={"Authorization": "APIKEY 32b2162f-9599-4647-8139-66e9f9528370", "Content-Type": "application/json"},
            json={"data": bulk_data})
        print("ABRP", abrp_resp.request.body, abrp_resp.status_code, abrp_resp.text)
        if abrp_resp.status_code != 200:
            print("ABRP Error", abrp_resp.text)

    def handle(self, *args, **options):
        print("Starting data sync process")
        self.handle_abrp_upload()
