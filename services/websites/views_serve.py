from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from .models import WebsiteOrder

def serve_generated_website(request, order_id):
    """Serve the generated HTML file for a website order."""
    order = get_object_or_404(WebsiteOrder, id=order_id)
    
    if not order.brief_files:
        raise Http404("Website not yet generated")
    
    try:
        # Read the file content
        with order.brief_files.open('r') as f:
            content = f.read()
        
        return HttpResponse(content, content_type='text/html')
    except Exception as e:
        raise Http404(f"Could not load website: {str(e)}")
