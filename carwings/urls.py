"""
URL configuration for carwings project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework_simplejwt.views import TokenRefreshView

import api.views as api_views
import tculink.views as tculink_views
import ui.views as views
from api.views import CustomTokenObtainPairView

api_info = openapi.Info(
        title="OpenCARWINGS API",
        default_version='v1',
        description="API to get information about cars. API Token is accessible from your account settings",
    )

schema_view = get_schema_view(
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[TokenAuthentication,SessionAuthentication, ],
)

decorated_token_view = \
    swagger_auto_schema(method='post',
                        tags=['token'])(
        TokenRefreshView.as_view())


urlpatterns = [
    path('admin/', admin.site.urls),
    path('apidocs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('', views.car_list, name='car_list'),
    path('setup/step1', views.setup_step1, name='setup_1'),
    path('setup/step2', views.setup_step2, name='setup_2'),
    path('setup/step3', views.setup_step3, name='setup_3'),
    path('setup/step4', views.setup_step4, name='setup_4'),
    path('setup/step5', views.setup_step5, name='setup_5'),
    path('navi', views.vflash_editor),
    path('WARCondelivbas/it-m_gw10/', tculink_views.carwings_http_gateway),
    path('signup', views.signup, name='car_list'),
    path('signin', views.signin, name='signin'),
    path('signout', views.signout, name='signout'),
    path('password-reset/', views.ResetPasswordView.as_view(), name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/',
                auth_views.PasswordResetConfirmView.as_view(template_name='ui/reset_password_confirm.html'),
                name='password_reset_confirm'),
    path('password-reset-complete/',
                auth_views.PasswordResetCompleteView.as_view(template_name='ui/reset_password_complete.html'),
                name='password_reset_complete'),
    path('account', views.account, name='account'),
    path('account/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('account/reset-api-key/', views.reset_apikey, name='reset_apikey'),
    path('account/change-carwings-password/', views.change_carwings_password, name='change_carwings_password'),
    path('car/<str:vin>/', views.car_detail, name='car_detail'),
    path('api/car/<str:vin>/', api_views.CarAPIView.as_view(), name='car_api'),
    path('api/car/', api_views.cars_api, name='car_api_list'),
    path('api/alerts/<str:vin>/', api_views.alerts_api, name='alerts_api'),
    path('api/command/<str:vin>/', api_views.command_api, name='command_api'),
    path('api/token/obtain/', CustomTokenObtainPairView.as_view(), name='token_refresh'),
    path('api/token/refresh/', decorated_token_view, name='token_refresh'),
    path('api/token/update/', api_views.update_token_metadata, name='token_update'),
    path('api/token/signout/', api_views.sign_out, name='token_refresh'),
    path('api/maplink/resolve', views.resolve_maps_link, name='resolve_maps_link'),
    path('car/<str:vin>/probeviewer', views.probeviewer_home, name='probeviewer_home'),
    path('car/<str:vin>/probeviewer/trip/<int:trip>', views.probeviewer_trip, name='probeviewer_trip'),
    path('api/probe/location/<str:vin>/', api_views.probe_location_hist, name='probe_location_api'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
