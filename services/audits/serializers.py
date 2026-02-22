from rest_framework import serializers
from services.common.serializers import BaseServiceOrderSerializer, UserSummarySerializer
from .models import AuditOrder, ScanResult, AgentAssignment

class ScanResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanResult
        fields = ['id', 'title', 'severity', 'description', 'evidence_url', 'fixed', 'created_at']

class AgentAssignmentSerializer(serializers.ModelSerializer):
    agent_detail = UserSummarySerializer(source='agent', read_only=True)
    
    class Meta:
        model = AgentAssignment
        fields = ['id', 'agent', 'agent_detail', 'claimed_at', 'completed_at', 'payout_amount']

class AuditOrderCreateSerializer(BaseServiceOrderSerializer):
    class Meta(BaseServiceOrderSerializer.Meta):
        model = AuditOrder
        fields = BaseServiceOrderSerializer.Meta.fields + ['target_url_or_ip', 'scope_text', 'authenticated_scan']

class AuditOrderDetailSerializer(BaseServiceOrderSerializer):
    scan_results = ScanResultSerializer(many=True, read_only=True)
    assignments = AgentAssignmentSerializer(many=True, read_only=True)
    
    class Meta(BaseServiceOrderSerializer.Meta):
        model = AuditOrder
        fields = BaseServiceOrderSerializer.Meta.fields + ['target_url_or_ip', 'scope_text', 'authenticated_scan', 'report_file', 'scan_results', 'assignments']
