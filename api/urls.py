from django.urls import path
import api.probe.views as views

urlpatterns = [
    path('<str:vin>/probe/latest', views.CRMLatestView().as_view(), name='probe_latest'),
    path('<str:vin>/probe/excessive_aircon', views.CRMExcessiveAirconRecordView().as_view(), name='probe_excessive_aircon'),
    path('<str:vin>/probe/excessive_idling', views.CRMExcessiveIdlingRecordView().as_view(), name='probe_excessive_idling'),
    path('<str:vin>/probe/monthly', views.CRMMonthlyView().as_view(), name='probe_monthly'),
    path('<str:vin>/probe/msn', views.CRMMSNRecordView().as_view(), name='probe_msn'),
    path('<str:vin>/probe/chargeplug', views.CRMChargePlugView().as_view(), name='probe_chargeplug'),
    path('<str:vin>/probe/charging_history', views.CRMChargingHistoryView().as_view(), name='probe_charging_history'),
    path('<str:vin>/probe/abs', views.CRMABSHistoryView().as_view(), name='probe_abs'),
    path('<str:vin>/probe/lifetime', views.CRMLifetimeView().as_view(), name='probe_lifetime'),
    path('<str:vin>/probe/dtc', views.CRMTroubleView().as_view(), name='probe_dtc'),
    path('<str:vin>/probe/trips', views.CRMTripView().as_view(), name='probe_trips'),
    path('<str:vin>/probe/dotfiles', views.DotFileView().as_view(), name='probe_dotfiles'),
]