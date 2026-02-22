from django.db import transaction
from django.utils import timezone
from services.common.services import BaseServiceLogic
from ..models import WebsiteOrder
import logging

logger = logging.getLogger(__name__)

class ManualAssignment:
    @staticmethod
    @transaction.atomic
    def assign_to_team(order, team_id):
        """
        Placeholder for assigning a website order to a manual development team.
        """
        BaseServiceLogic.update_status(order, 'in_progress', comment=f"Order assigned to manual team {team_id}.")
        return True

    @staticmethod
    @transaction.atomic
    def accept_delivery(order, client):
        if order.client != client:
            raise Exception("Only the client can accept delivery.")
        
        BaseServiceLogic.update_status(order, 'completed', comment="Client accepted delivery. Order finalized.")
        return True
