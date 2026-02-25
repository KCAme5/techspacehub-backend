from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import ServiceStatusHistory, ServiceComment
from accounts.models import User

class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']

class StatusHistorySerializer(serializers.ModelSerializer):
    changed_by_detail = UserSummarySerializer(source='changed_by', read_only=True)
    
    class Meta:
        model = ServiceStatusHistory
        fields = ['id', 'old_status', 'new_status', 'changed_by', 'changed_by_detail', 'comment', 'created_at']

class BaseServiceOrderSerializer(serializers.Serializer):
    """
    Base serializer for common ServiceOrder fields.
    Not a ModelSerializer to avoid abstract model issues.
    """
    id = serializers.UUIDField(read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    client_detail = UserSummarySerializer(source='client', read_only=True)
    service_type = serializers.CharField(max_length=20)
    mode = serializers.CharField(max_length=50)
    status = serializers.CharField(max_length=20, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    consent_given = serializers.BooleanField(read_only=True)
    consent_timestamp = serializers.DateTimeField(read_only=True, allow_null=True)
    consent_ip = serializers.IPAddressField(read_only=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status_history = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_status_history(self, obj):
        try:
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_model(obj)
            history = ServiceStatusHistory.objects.filter(content_type=content_type, object_id=obj.id)
            return StatusHistorySerializer(history, many=True).data
        except:
            return []

    class Meta:
        # Keep this for backward compatibility with child classes if they use it
        fields = [
            'id', 'client', 'client_detail', 'service_type', 'mode', 
            'status', 'total_price', 'payment', 'consent_given', 
            'consent_timestamp', 'consent_ip', 'notes', 
            'status_history', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'client', 'status', 'payment', 'consent_given', 'consent_timestamp', 'consent_ip', 'created_at', 'updated_at']

class ServiceCommentSerializer(serializers.ModelSerializer):
    author_detail = UserSummarySerializer(source='author', read_only=True)
    
    class Meta:
        model = ServiceComment
        fields = ['id', 'author', 'author_detail', 'content', 'created_at']
