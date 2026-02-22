from rest_framework import serializers
from .models import WebsiteOrder, WebsiteBrief

class WebsiteOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteOrder
        fields = '__all__'
