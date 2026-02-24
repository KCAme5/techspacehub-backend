from rest_framework import serializers
from services.common.serializers import BaseServiceOrderSerializer, UserSummarySerializer
from .models import WebsiteOrder, WebsiteRevision

class WebsiteRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteRevision
        fields = ['id', 'request_text', 'status', 'created_at']

class WebsiteOrderCreateSerializer(BaseServiceOrderSerializer):
    class Meta(BaseServiceOrderSerializer.Meta):
        model = WebsiteOrder
        fields = BaseServiceOrderSerializer.Meta.fields + ['project_brief', 'selected_template_id', 'deadline', 'notes']

class WebsiteOrderProgressSerializer(BaseServiceOrderSerializer):
    revisions = WebsiteRevisionSerializer(many=True, read_only=True)
    
    class Meta(BaseServiceOrderSerializer.Meta):
        model = WebsiteOrder
        fields = BaseServiceOrderSerializer.Meta.fields + ['project_brief', 'selected_template_id', 'deadline', 'revision_count', 'final_url', 'brief_files', 'revisions']
