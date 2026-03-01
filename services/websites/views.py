from rest_framework import viewsets, status, decorators, permissions
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from services.common.permissions import IsOrderOwner, IsServiceStaff, IsOwnerOrStaff
from services.common.services import BaseServiceLogic
from .models import WebsiteOrder, WebsiteRevision
from .serializers import WebsiteOrderCreateSerializer, WebsiteOrderProgressSerializer, WebsiteRevisionSerializer

class WebsiteOrderViewSet(viewsets.ModelViewSet):
    queryset = WebsiteOrder.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['management', 'staff'] or user.is_staff:
            # Hide AI sandboxes from management/staff by default
            return WebsiteOrder.objects.filter(is_ai_sandbox=False)
        return WebsiteOrder.objects.filter(client=user)

    def get_permissions(self):
        if self.action in ['generate_preview', 'generate']:  # Only loosen these for testing
            return [permissions.IsAuthenticated()]  # Allow any logged-in user
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy', 'request_revision', 'mark_consent']:
            return [IsOwnerOrStaff()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return WebsiteOrderCreateSerializer
        return WebsiteOrderProgressSerializer

    def perform_create(self, serializer):
        # Ensure service_type and total_price are set if not provided in payload
        # though payload usually has them, model level validation might fail
        # if they are not explicitly handled by the serializer correctly.
        serializer.save(
            client=self.request.user,
            service_type='website',
            status='draft'
        )

    @decorators.action(detail=True, methods=['post'], throttle_classes=[ScopedRateThrottle])
    def generate_preview(self, request, pk=None):
        self.throttle_scope = 'ai_generate'
        
        order = self.get_object()
        
        # DEBUG LOGS - very important
        print(f"[DEBUG] generate_preview called by user: {request.user.id} ({request.user.email})")
        print(f"[DEBUG] Order ID: {order.id}, Client: {order.client.id if order.client else 'None'}")
        print(f"[DEBUG] Is authenticated: {request.user.is_authenticated}")
        print(f"[DEBUG] Is staff: {request.user.is_staff}")
        
        # Temporarily force allow for testing
        # if order.client != request.user and not request.user.is_staff:
        #     return Response({"detail": "Not authorized"}, status=403)
        
        from .tasks import generate_ai_website
        task = generate_ai_website.delay(order.id)
        print(f"[DEBUG] Celery task queued: {task.id}")
        
        BaseServiceLogic.update_status(order, 'in_progress', user=request.user, comment="AI website generation triggered.")
        return Response({'status': 'generation triggered', 'task_id': task.id}, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['post'])
    def generate(self, request):
        """Legacy/Fallback endpoint for AI generation"""
        order_id = request.data.get('order_id')
        if not order_id:
            return Response({'error': 'order_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = WebsiteOrder.objects.get(id=order_id)
        except (WebsiteOrder.DoesNotExist, ValueError):
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Check permissions manually for detail=False action
        if not (request.user.role in ['management', 'staff'] or request.user.is_staff or order.client == request.user):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        # Trigger Celery task for AI generation
        from .tasks import generate_ai_website
        generate_ai_website.delay(order.id)
        
        BaseServiceLogic.update_status(order, 'in_progress', user=request.user, comment="AI website generation triggered via fallback endpoint.")
        return Response({'status': 'generation triggered'}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'])
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

    @decorators.action(detail=True, methods=['post'])
    def mark_consent(self, request, pk=None):
        order = self.get_object()
        ip = request.META.get('REMOTE_ADDR')
        BaseServiceLogic.mark_consent_given(order, ip)
        
        # If AI mode, we might want to trigger generation immediately after consent
        if order.mode == 'ai' and order.status == 'consented':
            from .tasks import generate_ai_website
            generate_ai_website.delay(order.id)
            BaseServiceLogic.update_status(order, 'in_progress', user=request.user, comment="AI website generation triggered after consent.")
            
        return Response({'status': 'consent marked'}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'])
    def convert_to_order(self, request, pk=None):
        order = self.get_object()
        if not order.is_ai_sandbox:
            return Response({"error": "This is already a formal order."}, status=400)
        
        # Mark as formal order
        order.is_ai_sandbox = False
        # Reset status if it was completed in sandbox, or keep it as is?
        # User said "pricing shall be done separately", so maybe it stays 'completed' but is now visible to staff for pricing/invoicing.
        order.save()
        
        BaseServiceLogic.update_status(order, order.status, user=request.user, comment="AI Sandbox converted to formal order by client.")
        return Response({"message": "Successfully converted to a formal order. Our team will now review and contact you for pricing."})
