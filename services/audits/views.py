from rest_framework import viewsets
from .models import AuditRequest
from .serializers import AuditRequestSerializer

class AuditRequestViewSet(viewsets.ModelViewSet):
    queryset = AuditRequest.objects.all()
    serializer_class = AuditRequestSerializer
