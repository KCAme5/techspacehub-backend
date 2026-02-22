from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from services.common.permissions import IsOrderOwner, IsServiceStaff
from services.common.services import BaseServiceLogic
from .models import WebsiteOrder, WebsiteRevision
from .serializers import WebsiteOrderCreateSerializer, WebsiteOrderProgressSerializer, WebsiteRevisionSerializer

class WebsiteOrderViewSet(viewsets.ModelViewSet):
    queryset = WebsiteOrder.objects.all()
    permission_classes = [IsOrderOwner | IsServiceStaff]

    def get_serializer_class(self):
        if self.action == 'create':
            return WebsiteOrderCreateSerializer
        return WebsiteOrderProgressSerializer

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

    @decorators.action(detail=True, methods=['post'], permission_classes=[IsOrderOwner])
    def generate_preview(self, request, pk=None):
        order = self.get_object()
        # Trigger Celery task for AI generation
        from .tasks import generate_ai_website
        generate_ai_website.delay(order.id)
        
        BaseServiceLogic.update_status(order, 'in_progress', user=request.user, comment="AI website generation triggered.")
        return Response({'status': 'generation triggered'}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'], permission_classes=[IsOrderOwner])
    def request_revision(self, request, pk=None):
        order = self.get_object()
        if order.revision_count <= 0:
            return Response({'error': 'No revisions remaining'}, status=status.HTTP_400_BAD_REQUEST)
        
        request_text = request.data.get('request_text')
        if not request_text:
            return Response({'error': 'Revision request text required'}, status=status.HTTP_400_BAD_REQUEST)

        WebsiteRevision.objects.create(order=order, request_text=request_text)
        order.revision_count -= 1
        order.save()
        
        BaseServiceLogic.update_status(order, 'in_progress', user=request.user, comment="Revision requested by client.")
        return Response({'status': 'revision requested'}, status=status.HTTP_200_OK)
