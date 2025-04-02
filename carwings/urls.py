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
from django.urls import path
from django.contrib.auth import views as auth_views

import ui.views as views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.car_list, name='car_list'),
    path('setup/step1', views.setup_step1, name='setup_1'),
    path('setup/step2', views.setup_step2, name='setup_2'),
    path('setup/step3', views.setup_step3, name='setup_3'),
    path('setup/step4', views.setup_step4, name='setup_4'),
    path('setup/step5', views.setup_step5, name='setup_5'),
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
    path('api/car/<str:vin>/', views.car_api, name='car_api'),
    path('api/car/', views.cars_api, name='car_api_list'),
    path('api/alerts/<str:vin>/', views.alerts_api, name='alerts_api'),
    path('api/command/<str:vin>/', views.command_api, name='command_api'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
