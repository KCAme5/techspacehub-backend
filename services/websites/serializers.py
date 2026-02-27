from rest_framework import serializers
from services.common.serializers import BaseServiceOrderSerializer, UserSummarySerializer
from .models import WebsiteOrder, WebsiteRevision

class WebsiteRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteRevision
        fields = ['id', 'request_text', 'status', 'created_at']

class WebsiteOrderCreateSerializer(serializers.ModelSerializer, BaseServiceOrderSerializer):
    class Meta:
        model = WebsiteOrder
        fields = BaseServiceOrderSerializer.Meta.fields + ['project_brief', 'selected_template_id', 'deadline']
        read_only_fields = BaseServiceOrderSerializer.Meta.read_only_fields

class WebsiteOrderProgressSerializer(serializers.ModelSerializer, BaseServiceOrderSerializer):
    revisions = WebsiteRevisionSerializer(many=True, read_only=True)
    
    class Meta:
        model = WebsiteOrder
        fields = BaseServiceOrderSerializer.Meta.fields + ['project_brief', 'selected_template_id', 'deadline', 'revision_count', 'final_url', 'brief_files', 'generated_zip', 'revisions']
        read_only_fields = BaseServiceOrderSerializer.Meta.read_only_fields
