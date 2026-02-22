from rest_framework import serializers

class BaseServiceSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        abstract = True
