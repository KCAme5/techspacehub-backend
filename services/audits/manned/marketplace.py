from django.db import transaction
from django.utils import timezone
from services.common.services import BaseServiceLogic
from ..models import AuditOrder, AgentAssignment
import logging

logger = logging.getLogger(__name__)

class AuditMarketplace:
    @staticmethod
    def get_claimable_orders(user):
        """
        Returns orders that are:
        - mode='manned'
        - status='consented'
        - have no active assignment
        # TODO: Add logic to check user qualifications
        """
        # Logic to check if user is a qualified agent
        if user.role not in ['staff', 'management']:
            return AuditOrder.objects.none()

        return AuditOrder.objects.filter(
            mode='manned',
            status='consented'
        ).exclude(assignments__completed_at__isnull=True)

    @staticmethod
    @transaction.atomic
    def claim_audit(order, agent):
        # 1. Check if already claimed
        if AgentAssignment.objects.filter(order=order, completed_at__isnull=True).exists():
            raise Exception("Order already claimed by another agent.")

        # 2. Check if order is claimable
        if order.status != 'consented' or order.mode != 'manned':
            raise Exception("Order is not in a claimable state.")

        # 3. Create assignment
        assignment = AgentAssignment.objects.create(
            order=order,
            agent=agent
        )

        # 4. Update order status
        BaseServiceLogic.update_status(order, 'in_progress', user=agent, comment=f"Order claimed by agent {agent.username}.")
        
        return assignment

    @staticmethod
    @transaction.atomic
    def submit_report(order, agent, report_file):
        assignment = AgentAssignment.objects.filter(order=order, agent=agent, completed_at__isnull=True).first()
        if not assignment:
            raise Exception("No active assignment found for this agent and order.")

        # 1. Save report and update completion
        order.report_file = report_file
        order.status = 'completed'
        order.save()

        assignment.completed_at = timezone.now()
        
        # 2. Calculate payout
        platform_fee = BaseServiceLogic.calculate_platform_fee(order)
        assignment.payout_amount = order.total_price - platform_fee
        assignment.save()

        # 3. Release payment logic (trigger billing)
        BaseServiceLogic.release_payment_to_agent(order, agent)

        # 4. Log status change
        BaseServiceLogic.update_status(order, 'completed', user=agent, comment="Manned audit report submitted. Order completed.")
        
        return assignment
