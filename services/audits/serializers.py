from rest_framework import serializers
from .models import AuditRequest, ScanResult

class AuditRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditRequest
        fields = '__all__'
