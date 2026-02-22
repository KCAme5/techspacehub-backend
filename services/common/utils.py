import os
import uuid
from django.utils import timezone
from django.conf import settings
import pytz

def get_kenya_time():
    kenya_tz = pytz.timezone('Africa/Nairobi')
    return timezone.now().astimezone(kenya_tz)

def generate_report_filename(order_id, extension="pdf"):
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return f"report_{order_id}_{timestamp}.{extension}"

def generate_consent_pdf(order):
    """
    Placeholder for PDF generation logic (e.g. using weasyprint or pdfkit).
    Returns path to generated PDF.
    """
    filename = f"consent_{order.id}.pdf"
    directory = os.path.join(settings.MEDIA_ROOT, 'consents')
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    file_path = os.path.join(directory, filename)
    # logic to write PDF content...
    return file_path
