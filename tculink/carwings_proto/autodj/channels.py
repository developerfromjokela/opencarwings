from django.utils.text import format_lazy

from tculink.carwings_proto.autodj.opencarwings import get_infochannel, get_energy_information_channel, \
    get_eco_tree_channel
from tculink.carwings_proto.autodj.routeplanner import handle_routeplanner
from tculink.carwings_proto.autodj.sendtocar import handle_send_to_car_adj, handle_send_to_car
from tculink.carwings_proto.autodj.weather import get_weather_forecast

STANDARD_AUTODJ_FOLDERS = [
    {
        'id': 1,
        'internal_id': 0x1001,
        'name1': 'OpenCARWINGS',
        'name2': 'OpenCARWINGS',
        'icon': 0x00,
        'flag': 0x01,
    },
    {
        'id': 2,
        'internal_id': 0x1002,
        'name1': 'Route Planning & Navigation',
        'name2': 'Route Planner',
        'icon': 0x00,
        'flag': 0x03,
    },
    {
        'id': 3,
        'internal_id': 0x1003,
        'name1': 'Online Services',
        'name2': 'Online Services',
        'icon': 0x00,
        'flag': 0x04,
    },
    {
        'id': 4,
        'internal_id': 0x1004,
        'name1': 'Custom channels',
        'name2': 'Custom channels',
        'icon': 0x00,
        'flag': 0x05,
    }
]

STANDARD_AUTODJ_CHANNELS = [
    {
        'id': 0x0000,
        'internal_id': 0x8080,
        'name1': 'Info from OpenCARWINGS',
        'name2': 'Any new announcements or features can be shown here',
        'folder_id': 1,
        'icon': 0x0400,
        'enabled': True,
        'auth': False,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': get_infochannel
    },
    {
        'id': 0x0010,
        'internal_id': 0x8081,
        'name1': 'Energy Economy',
        'name2': 'Get latest energy economy information',
        'folder_id': 1,
        'icon': 0x0400,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': get_energy_information_channel
    },
    {
        'id': 0x0011,
        'internal_id': 0x8082,
        'name1': 'Eco Trees',
        'name2': 'Get latest eco tree information',
        'folder_id': 1,
        'icon': 0x0400,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': get_eco_tree_channel
    },

    # route planner
    {
        'id': 0x000A,
        'internal_id': 0x001A,
        'name1': format_lazy('Route Plan {num}', num=1),
        'name2': format_lazy('Route Plan {num}', num=1),
        'folder_id': 2,
        'icon': 2,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_routeplanner
    },
    {
        'id': 0x000B,
        'internal_id': 0x001B,
        'name1': format_lazy('Route Plan {num}', num=2),
        'name2': format_lazy('Route Plan {num}', num=2),
        'folder_id': 2,
        'icon': 3,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_routeplanner
    },
    {
        'id': 0x000C,
        'internal_id': 0x001C,
        'name1': format_lazy('Route Plan {num}', num=3),
        'name2': format_lazy('Route Plan {num}', num=3),
        'folder_id': 2,
        'icon': 4,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_routeplanner
    },
    {
        'id': 0x000D,
        'internal_id': 0x001D,
        'name1': format_lazy('Route Plan {num}', num=4),
        'name2': format_lazy('Route Plan {num}', num=4),
        'folder_id': 2,
        'icon': 5,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_routeplanner
    },
    {
        'id': 0x000E,
        'internal_id': 0x001E,
        'name1': format_lazy('Route Plan {num}', num=5),
        'name2': format_lazy('Route Plan {num}', num=5),
        'folder_id': 2,
        'icon': 6,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_routeplanner
    },
    {
        'id': 0x000F,
        'internal_id': 0x001F,
        'name1': 'Google Send To Car',
        'name2': 'Download Google Send To Car',
        'folder_id': 2,
        'icon': 0x0400,
        'enabled': True,
        'internal': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_send_to_car
    },
    {
        'id': 0x00EA,
        'internal_id': 0x001A,
        'name1': 'Google Send To Car',
        'name2': 'Download Google Send To Car',
        'folder_id': 2,
        'icon': 0x0400,
        'enabled': True,
        'auth': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': handle_send_to_car_adj
    },
    # online services
    {
        'id': 0x1020,
        'internal_id': 0x0020,
        'name1': 'Weather Forecast',
        'name2': 'Download Weather Forecast for your area',
        'folder_id': 3,
        'icon': 0x310,
        'enabled': True,
        'auth': False,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00,
        'processor': get_weather_forecast
    }
]