from django.test import SimpleTestCase

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
