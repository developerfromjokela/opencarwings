from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from api.probe.permissions import IsProbeCarOwner
from api.probe.serializers import CRMLatestSerializer, CRMLifetimeSerializer
from db.models import CRMLatest, CRMLifetime


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

