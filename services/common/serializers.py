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

class BaseServiceOrderSerializer(serializers.ModelSerializer):
    client_detail = UserSummarySerializer(source='client', read_only=True)
    status_history = serializers.SerializerMethodField()
    
    class Meta:
        fields = [
            'id', 'client', 'client_detail', 'service_type', 'mode', 
            'status', 'total_price', 'payment', 'consent_given', 
            'consent_timestamp', 'consent_ip', 'notes', 
            'status_history', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'client', 'status', 'payment', 'consent_given', 'consent_timestamp', 'consent_ip', 'created_at', 'updated_at']

    def get_status_history(self, obj):
        content_type = ContentType.objects.get_for_model(obj)
        history = ServiceStatusHistory.objects.filter(content_type=content_type, object_id=obj.id)
        return StatusHistorySerializer(history, many=True).data

    def validate(self, data):
        # Validation: must have consent before progressing beyond "paid"
        # This will be more relevant in the update view/service layer
        return data

class ServiceCommentSerializer(serializers.ModelSerializer):
    author_detail = UserSummarySerializer(source='author', read_only=True)
    
    class Meta:
        model = ServiceComment
        fields = ['id', 'author', 'author_detail', 'content', 'created_at']
