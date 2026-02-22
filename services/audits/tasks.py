from celery import shared_task
from .models import AuditOrder, ScanResult
from .automated.runners import ScannerRunner
from services.common.services import BaseServiceLogic
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task
def run_automated_scan(order_id):
    try:
        order = AuditOrder.objects.get(id=order_id)
        logger.info(f"Starting automated scan for order {order_id}")
        
        runner = ScannerRunner()
        
        # 1. Run tools
        nuclei_findings = runner.execute_nuclei(order.target_url_or_ip)
        zap_findings = runner.execute_zap(order.target_url_or_ip)
        
        # 2. Save findings
        all_findings = nuclei_findings + zap_findings
        for finding in all_findings:
            ScanResult.objects.create(
                order=order,
                title=finding['title'],
                severity=finding['severity'],
                description=finding['description']
            )
        
        # 3. Finalize order
        BaseServiceLogic.update_status(order, 'completed', comment="Automated scan finished. Findings parsed.")
        
        # 4. Generate report (future logic)
        # order.report_file = generate_report(order)
        # order.save()
        
    except AuditOrder.DoesNotExist:
        logger.error(f"AuditOrder {order_id} not found for scan task.")
    except Exception as e:
        logger.error(f"Error in automated scan task {order_id}: {str(e)}")
