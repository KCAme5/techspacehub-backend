from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from services.common.permissions import IsOrderOwner, IsServiceStaff
from services.common.services import BaseServiceLogic
from .models import AuditOrder, ScanResult
from .serializers import AuditOrderCreateSerializer, AuditOrderDetailSerializer, ScanResultSerializer

class AuditOrderViewSet(viewsets.ModelViewSet):
    queryset = AuditOrder.objects.all()
    permission_classes = [IsOrderOwner | IsServiceStaff]

    def get_serializer_class(self):
        if self.action == 'create':
            return AuditOrderCreateSerializer
        return AuditOrderDetailSerializer

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

    @decorators.action(detail=True, methods=['post'], permission_classes=[IsOrderOwner])
    def mark_consent(self, request, pk=None):
        order = self.get_object()
        ip = request.META.get('REMOTE_ADDR')
        BaseServiceLogic.mark_consent_given(order, ip)
        return Response({'status': 'consent marked'}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'], permission_classes=[IsOrderOwner | IsServiceStaff])
    def trigger_scan(self, request, pk=None):
        order = self.get_object()
        if not order.consent_given:
            return Response({'error': 'Consent must be given before scanning'}, status=status.HTTP_400_OK)
        
        # Trigger Celery task here
        from .tasks import run_automated_scan
        run_automated_scan.delay(order.id)
        
        BaseServiceLogic.update_status(order, 'in_progress', user=request.user, comment="Automated scan triggered.")
        return Response({'status': 'scan triggered'}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'], permission_classes=[IsServiceStaff])
    def claim(self, request, pk=None):
        order = self.get_object()
        from .manned.marketplace import AuditMarketplace
        try:
            assignment = AuditMarketplace.claim_audit(order, request.user)
            return Response({'status': 'claimed', 'assignment_id': assignment.id}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'], permission_classes=[IsServiceStaff])
    def submit_report(self, request, pk=None):
        order = self.get_object()
        report_file = request.FILES.get('report_file')
        if not report_file:
            return Response({'error': 'No report file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .manned.marketplace import AuditMarketplace
        try:
            AuditMarketplace.submit_report(order, request.user, report_file)
            return Response({'status': 'report submitted'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['get'], permission_classes=[IsOrderOwner | IsServiceStaff])
    def results(self, request, pk=None):
        order = self.get_object()
        results = ScanResult.objects.filter(order=order)
        serializer = ScanResultSerializer(results, many=True)
        return Response(serializer.data)
