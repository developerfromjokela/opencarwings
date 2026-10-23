from datetime import timedelta
from unittest import mock
from urllib.parse import urljoin

import pyotp
from django.conf import settings
from django.core import mail
from django.core.management import call_command
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
        self.assertEqual(self.car.owner, self.buyer)
        self.assertFalse(CarTransferRequest.objects.exists())
        self.assertFalse(AlertHistory.objects.filter(car=self.car).exists())
        self.assertFalse(RoutePlan.objects.exists())
        # Link works only once
        self.assertContains(self.client.get(self.url), 'not found')

    def test_claim_message_mentions_signin_for_continental(self):
        self.client.force_login(self.buyer)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'sign in on its navigation unit')

    def test_claim_message_skips_signin_for_newer_tcu(self):
        self.car.tcu_type = 'ficosa2016'
        self.car.save()
        self.client.force_login(self.buyer)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'You now own')
        self.assertNotContains(response, 'sign in on its navigation unit')

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

    def test_expired_link(self):
        self.transfer.expiration_time = timezone.now() - timedelta(minutes=1)
        self.transfer.save()
        self.client.force_login(self.buyer)
        self.assertContains(self.client.post(self.url), 'not found')

    def test_default_expiry_is_seven_days(self):
        self.assertAlmostEqual(self.transfer.expiration_time - timezone.now(), timedelta(days=7), delta=timedelta(minutes=1))

    def test_send_link_builds_url_from_site_url_setting(self):
        link, sent = self.transfer.send_link()
        self.assertTrue(sent)
        self.assertEqual(link, urljoin(settings.SITE_URL, self.transfer.get_absolute_url()))
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])


class CarTransferSignalTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@example.com', 'pw', tcu_pass_hash='x')
        self.car = Car.objects.create(
            vin='VIN0001', sms_config={}, owner=self.seller, tcu_configuration=TCUConfiguration.objects.create(),
            location=LocationInfo.objects.create(), ev_info=EVInfo.objects.create(),
        )

    def test_creating_a_transfer_emails_the_link_on_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            transfer = CarTransferRequest.objects.create(car=self.car, recipient_email='buyer@example.com')
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
        self.assertIn(transfer.get_absolute_url(), mail.outbox[0].body)

    def test_updating_a_transfer_does_not_resend(self):
        with self.captureOnCommitCallbacks(execute=True):
            transfer = CarTransferRequest.objects.create(car=self.car, recipient_email='buyer@example.com')
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            transfer.keep_history = True
            transfer.save()
        self.assertEqual(len(mail.outbox), 0)


class FlushExpiredTransfersTests(TestCase):
    def test_expired_rows_are_deleted_and_active_kept(self):
        seller = User.objects.create_user('seller', 'seller@example.com', 'pw', tcu_pass_hash='x')
        car = Car.objects.create(
            vin='VIN0001', sms_config={}, owner=seller, tcu_configuration=TCUConfiguration.objects.create(),
            location=LocationInfo.objects.create(), ev_info=EVInfo.objects.create(),
        )
        expired = CarTransferRequest.objects.create(
            car=car, recipient_email='a@example.com', expiration_time=timezone.now() - timedelta(minutes=1))
        active = CarTransferRequest.objects.create(car=car, recipient_email='b@example.com')

        call_command('flushexpiredtransfers')

        self.assertFalse(CarTransferRequest.objects.filter(pk=expired.pk).exists())
        self.assertTrue(CarTransferRequest.objects.filter(pk=active.pk).exists())


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
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/admin/db/cartransferrequest/add/', self.data)
        transfer = CarTransferRequest.objects.get()
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
        self.assertIn(transfer.get_absolute_url(), mail.outbox[0].body)

    def test_smtp_failure_does_not_break_request(self):
        # A failed send keeps the row
        with mock.patch('db.models.send_mail', side_effect=ConnectionRefusedError):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/admin/db/cartransferrequest/add/', self.data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CarTransferRequest.objects.exists())


class UserCarTransferTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@example.com', 'pw', tcu_pass_hash='x')
        self.car = Car.objects.create(
            vin='VIN0001', sms_config={}, owner=self.seller, tcu_configuration=TCUConfiguration.objects.create(),
            location=LocationInfo.objects.create(), ev_info=EVInfo.objects.create(),
        )
        self.url = f'/car/{self.car.vin}/transfer/'
        self.client.force_login(self.seller)

    def test_owner_creates_link(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'recipient_email': 'buyer@example.com', 'keep_history': 'on'})
        transfer = CarTransferRequest.objects.get()
        self.assertTrue(transfer.keep_history)
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
        self.assertContains(self.client.get(self.url), transfer.get_absolute_url())

    def test_new_link_replaces_old_and_cancel_removes_it(self):
        self.client.post(self.url, {'recipient_email': 'a@example.com'})
        self.client.post(self.url, {'recipient_email': 'b@example.com'})
        self.assertEqual(CarTransferRequest.active().get().recipient_email, 'b@example.com')
        self.client.post(self.url, {'cancel': '1'})
        self.assertFalse(CarTransferRequest.objects.exists())

    def test_own_email_rejected(self):
        self.assertContains(self.client.post(self.url, {'recipient_email': 'SELLER@example.com'}), 'your own email')
        self.assertFalse(CarTransferRequest.objects.exists())

    def test_other_users_car_not_found(self):
        self.client.force_login(User.objects.create_user('other', 'o@example.com', 'pw', tcu_pass_hash='x'))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_2fa_required_when_enabled(self):
        self.seller.otp_key = pyotp.random_base32()
        self.seller.save()
        response = self.client.post(self.url, {'recipient_email': 'buyer@example.com'})
        self.assertContains(response, 'reverify_2fa')
        self.assertFalse(CarTransferRequest.objects.exists())
        # After the code is checked, the form is shown again, not submitted with missing data
        code = pyotp.TOTP(self.seller.otp_key).now()
        response = self.client.post(self.url, {'reverify_2fa': '1', 'otp': code})
        self.assertContains(response, 'Create transfer link')
        self.assertNotContains(response, 'This field is required')
        self.client.post(self.url, {'recipient_email': 'buyer@example.com'})
        self.assertTrue(CarTransferRequest.objects.exists())
