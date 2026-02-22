from rest_framework import viewsets
from .models import WebsiteOrder
from .serializers import WebsiteOrderSerializer

class WebsiteOrderViewSet(viewsets.ModelViewSet):
    queryset = WebsiteOrder.objects.all()
    serializer_class = WebsiteOrderSerializer
