from celery import shared_task
from .models import AuditOrder, ScanResult
from .automated.runners import ScannerRunner
from services.common.services import BaseServiceLogic
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

 @shared_task(
    bind=True,
    rate_limit='2/h',  # Max 2 scans per hour globally (free tier conservative)
    soft_time_limit=1800,  # 30 min max
    time_limit=3600,  # 1 hour hard limit
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 1},
    acks_late=True,  # Acknowledge after completion
    task_reject_on_worker_lost=True,
)
def run_automated_scan(self, order_id):
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
