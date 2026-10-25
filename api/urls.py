from django.urls import path
import api.probe.views as views

urlpatterns = [
    path('<str:vin>/probe/latest', views.CRMLatestView().as_view(), name='probe_latest'),
    path('<str:vin>/probe/lifetime', views.CRMLifetimeView().as_view(), name='probe_lifetime'),
]