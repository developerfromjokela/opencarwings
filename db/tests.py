from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from db.models import (AlertHistory, Car, CarTransferRequest, EVInfo, LocationInfo, RoutePlan, TCUConfiguration,
                       User)


class CarTransferTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@example.com', 'pw', tcu_pass_hash='x')
        self.buyer = User.objects.create_user('buyer', 'Buyer@Example.com', 'pw', tcu_pass_hash='x')
        self.other = User.objects.create_user('other', 'other@example.com', 'pw', tcu_pass_hash='x')
        self.car = Car.objects.create(
            vin='VIN0001', sms_config={}, owner=self.seller, tcu_configuration=TCUConfiguration.objects.create(),
            location=LocationInfo.objects.create(), ev_info=EVInfo.objects.create(),
        )
        AlertHistory.objects.create(car=self.car, type=1)
        self.car.route_plans.add(RoutePlan.objects.create(
            name='Commute', start_name='a', start_lat=0, start_lon=0, finish_name='b', finish_lat=0, finish_lon=0))
        self.transfer = CarTransferRequest.objects.create(car=self.car, recipient_email='buyer@example.com')
        self.url = self.transfer.get_absolute_url()

    def test_recipient_claims_and_history_is_wiped(self):
        self.assertEqual(self.transfer.previous_owner, self.seller)
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(self.url), 'seller')
        response = self.client.post(self.url)
        self.assertRedirects(response, f'/car/{self.car.vin}/', fetch_redirect_response=False)
        self.car.refresh_from_db()
        self.transfer.refresh_from_db()
        self.assertEqual(self.car.owner, self.buyer)
        self.assertEqual(self.transfer.previous_owner, self.seller)
        self.assertEqual(self.transfer.claimed_by, self.buyer)
        self.assertFalse(AlertHistory.objects.filter(car=self.car).exists())
        self.assertFalse(RoutePlan.objects.exists())
        # Link works only once
        self.assertContains(self.client.get(self.url), 'not found')

    def test_keep_history(self):
        self.transfer.keep_history = True
        self.transfer.save()
        self.client.force_login(self.buyer)
        self.client.post(self.url)
        self.assertTrue(AlertHistory.objects.filter(car=self.car).exists())
        self.assertTrue(self.car.route_plans.exists())

    def test_wrong_account_cannot_claim(self):
        self.client.force_login(self.other)
        self.assertContains(self.client.post(self.url), 'different email address')
        self.car.refresh_from_db()
        self.assertEqual(self.car.owner, self.seller)

    def test_legacy_request_without_email_cannot_be_claimed(self):
        self.transfer.recipient_email = ''
        self.transfer.save()
        self.other.email = ''
        self.other.save()
        self.client.force_login(self.other)
        self.client.post(self.url)
        self.car.refresh_from_db()
        self.assertEqual(self.car.owner, self.seller)

    def test_expired_link(self):
        self.transfer.expiration_time = timezone.now() - timedelta(minutes=1)
        self.transfer.save()
        self.client.force_login(self.buyer)
        self.assertContains(self.client.post(self.url), 'not found')

    def test_default_expiry_is_seven_days(self):
        self.assertAlmostEqual(self.transfer.expiration_time - timezone.now(), timedelta(days=7), delta=timedelta(minutes=1))


class CarTransferAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pw', tcu_pass_hash='x')
        self.car = Car.objects.create(
            vin='VIN0001', sms_config={}, owner=self.admin, tcu_configuration=TCUConfiguration.objects.create(),
            location=LocationInfo.objects.create(), ev_info=EVInfo.objects.create(),
        )
        self.client.force_login(self.admin)
        self.data = {'car': self.car.pk, 'recipient_email': 'buyer@example.com', 'expiration_time_0': '', 'expiration_time_1': ''}

    def test_create_emails_link(self):
        self.client.post('/admin/db/cartransferrequest/add/', self.data)
        transfer = CarTransferRequest.objects.get()
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
        self.assertIn(transfer.get_absolute_url(), mail.outbox[0].body)

    def test_smtp_failure_shows_link(self):
        with mock.patch('db.admin.send_mail', side_effect=ConnectionRefusedError):
            response = self.client.post('/admin/db/cartransferrequest/add/', self.data, follow=True)
        self.assertContains(response, CarTransferRequest.objects.get().get_absolute_url())
