from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated

from api.probe.pagination import DefaultProbeSetPagination
from api.probe.permissions import IsProbeCarOwner
from api.probe.serializers import CRMLatestSerializer, CRMLifetimeSerializer, CRMExcessiveAirconRecordSerializer, \
    CRMExcessiveIdlingRecordSerializer, CRMMonthlySerializer, CRMMSNRecordSerializer, CRMChargeRecordSerializer, \
    CRMChargeHistorySerializer, CRMABSHistoryRecordSerializer, CRMTroubleRecordSerializer, CRMTripSerializer, \
    DOTFilesSerializer
from db.models import CRMLatest, CRMLifetime, CRMExcessiveAirconRecord, CRMExcessiveIdlingRecord, CRMMonthlyRecord, \
    CRMMSNRecord, CRMChargeRecord, CRMChargeHistoryRecord, CRMABSHistoryRecord, CRMDistanceRecord, CRMTroubleRecord, \
    CRMTripRecord, DOTFile
from ui.utils import order_ts_future_last

class ProbeListAPIView(ListAPIView):

    def get_queryset(self):
        return super().get_queryset().filter(car__vin=self.kwargs[self.lookup_url_kwarg], car__owner=self.request.user)

class CRMLatestView(RetrieveAPIView):
    queryset = CRMLatest.objects.all()
    serializer_class = CRMLatestSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    lookup_field = 'car__vin'
    lookup_url_kwarg = 'vin'

class CRMLifetimeView(RetrieveAPIView):
    queryset = CRMLifetime.objects.all()
    serializer_class = CRMLifetimeSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    lookup_field = 'car__vin'
    lookup_url_kwarg = 'vin'

class CRMExcessiveAirconRecordView(ProbeListAPIView):
    queryset = CRMExcessiveAirconRecord.objects.all()
    serializer_class = CRMExcessiveAirconRecordSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_field = 'car__vin'
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'start')

class CRMExcessiveIdlingRecordView(ProbeListAPIView):
    queryset = CRMExcessiveIdlingRecord.objects.all()
    serializer_class = CRMExcessiveIdlingRecordSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_field = 'car__vin'
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'start')

class CRMMonthlyView(ProbeListAPIView):
    queryset = CRMMonthlyRecord.objects.all()
    serializer_class = CRMMonthlySerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'start')

class CRMMSNRecordView(ProbeListAPIView):
    queryset = CRMMSNRecord.objects.all()
    serializer_class = CRMMSNRecordSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'timestamp')

class CRMChargePlugView(ProbeListAPIView):
    queryset = CRMChargeRecord.objects.all()
    serializer_class = CRMChargeRecordSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'start_time')

class CRMChargingHistoryView(ProbeListAPIView):
    queryset = CRMChargeHistoryRecord.objects.all()
    serializer_class = CRMChargeHistorySerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'start_time')

class CRMABSHistoryView(ProbeListAPIView):
    queryset = CRMABSHistoryRecord.objects.all()
    serializer_class = CRMABSHistoryRecordSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'timestamp')

class CRMTroubleView(ProbeListAPIView):
    queryset = CRMTroubleRecord.objects.all()
    serializer_class = CRMTroubleRecordSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'created_at')

class CRMTripView(ProbeListAPIView):
    queryset = CRMTripRecord.objects.all()
    serializer_class = CRMTripSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'start_ts')

class DotFileView(ProbeListAPIView):
    queryset = DOTFile.objects.all()
    serializer_class = DOTFilesSerializer
    permission_classes = (IsAuthenticated, IsProbeCarOwner)
    pagination_class = DefaultProbeSetPagination
    lookup_url_kwarg = 'vin'

    def get_queryset(self):
        return order_ts_future_last(super().get_queryset(), 'upload_ts')