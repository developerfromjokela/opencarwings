from pathlib import Path

from django.test import SimpleTestCase
from django.template import Context, Engine

from ui.serializers import RoutePlanSerializer, SendToCarLocationSerializer


class RoutePlanNameTests(SimpleTestCase):
    def route(self):
        return {
            'name': 'Test route',
            'start_name': 'Starting point', 'start_lat': '47.5', 'start_lon': '19.1',
            'finish_name': 'Destination', 'finish_lat': '47.6', 'finish_lon': '19.2',
            'point1_name': 'Waypoint', 'point1_lat': '47.55', 'point1_lon': '19.15',
        }

    def test_thirty_character_names_are_valid_for_every_route_point(self):
        data = self.route()
        for prefix in ['start', 'finish', 'point1', 'point2', 'point3', 'point4', 'point5']:
            data.update({f'{prefix}_name': 'ő' * 30, f'{prefix}_lat': '47.5', f'{prefix}_lon': '19.1'})
        serializer = RoutePlanSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_long_names_have_errors_bound_to_each_point_field(self):
        for prefix in ['start', 'finish', 'point1', 'point2', 'point3', 'point4', 'point5']:
            with self.subTest(prefix=prefix):
                data = self.route()
                data[f'{prefix}_name'] = 'ő' * 31
                serializer = RoutePlanSerializer(data=data)
                self.assertFalse(serializer.is_valid())
                self.assertEqual(serializer.errors[f'{prefix}_name'][0].code, 'max_length')

    def test_required_point_names_reject_missing_null_and_blank(self):
        for prefix in ['start', 'finish']:
            for value in [None, '', '   ']:
                with self.subTest(prefix=prefix, value=value):
                    data = self.route()
                    data[f'{prefix}_name'] = value
                    self.assertFalse(RoutePlanSerializer(data=data).is_valid())
            data = self.route()
            del data[f'{prefix}_name']
            self.assertFalse(RoutePlanSerializer(data=data).is_valid())

    def test_existing_route_without_optional_waypoints_remains_valid(self):
        data = {key: value for key, value in self.route().items() if not key.startswith('point')}
        serializer = RoutePlanSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['start_name'], 'Starting point')

    def test_send_to_car_still_accepts_thirty_two_characters(self):
        serializer = SendToCarLocationSerializer(data={'name': 'ő' * 32, 'lat': '47.5', 'lon': '19.1'})
        self.assertTrue(serializer.is_valid(), serializer.errors)


class CarLocationTemplateTests(SimpleTestCase):
    def setUp(self):
        self.source = (Path(__file__).parent / 'templates/ui/car_detail.html').read_text()
        self.engine = Engine(libraries={
            'i18n': 'django.templatetags.i18n',
            'l10n': 'django.templatetags.l10n',
            'static': 'django.templatetags.static',
            'math_filters': 'ui.templatetags.math_filters',
            'units': 'ui.templatetags.units',
        })

    def test_full_car_detail_template_compiles(self):
        self.engine.from_string(self.source)

    def test_initial_location_preserves_zero_and_handles_missing_values(self):
        line = next(line for line in self.source.splitlines() if 'let currentCarLocation =' in line)
        template = self.engine.from_string('{% load l10n %}' + line)
        for location in [{'lat': 0, 'lon': 0}, {'lat': None, 'lon': None}, {}, None]:
            with self.subTest(location=location):
                rendered = template.render(Context({'car': {'location': location}}))
                value = '0' if location and location.get('lat') == 0 else ''
                self.assertIn("lat: '" + value + "'", rendered)
                self.assertIn("lon: '" + value + "'", rendered)

    def test_location_has_selectable_coordinates_and_safe_link_hidden_until_validated(self):
        section = self.source.split('<div id="location"', 1)[1].split('<!-- Location -->', 1)[0]
        rendered = self.engine.from_string('{% load i18n %}<div id="location"' + section).render(Context({'car': {'location': None}}))
        self.assertIn('id="car-coordinates" type="text" readonly', rendered)
        self.assertIn('id="car-location-actions" hidden', rendered)
        self.assertIn('id="copy-car-coordinates" type="button"', rendered)
        self.assertIn('id="loc_last_updated">N/A</span>', rendered)
        self.assertEqual(rendered.count('referrerpolicy="no-referrer"'), 1)
        self.assertEqual(rendered.count('rel="noopener noreferrer"'), 1)
        self.assertNotIn('href=', rendered)
