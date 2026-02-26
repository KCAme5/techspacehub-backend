import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from .models_conversation import ConversationMessage, CodeRevision, ProjectFile

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_conversations(days=2):
    """
    Clean up conversation messages, code revisions, and project files
    that are older than the specified number of days.
    Default: 2 days
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Delete old conversation messages
    old_messages = ConversationMessage.objects.filter(created_at__lt=cutoff_date)
    messages_count = old_messages.count()
    old_messages.delete()
    
    # Delete old code revisions
    old_revisions = CodeRevision.objects.filter(created_at__lt=cutoff_date)
    revisions_count = old_revisions.count()
    old_revisions.delete()
    
    # Delete old project files (only if order is also old - check via order.created_at)
    old_files = ProjectFile.objects.filter(created_at__lt=cutoff_date)
    files_count = old_files.count()
    old_files.delete()
    
    logger.info(
        f"Cleanup complete: Deleted {messages_count} messages, "
        f"{revisions_count} revisions, {files_count} project files "
        f"older than {days} days (before {cutoff_date})"
    )
    
    return {
        "messages_deleted": messages_count,
        "revisions_deleted": revisions_count,
        "files_deleted": files_count,
        "cutoff_date": cutoff_date.isoformat(),
    }
