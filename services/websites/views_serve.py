from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from .models import WebsiteOrder

def serve_generated_website(request, order_id):
    """Serve the generated HTML file for a website order."""
    order = get_object_or_404(WebsiteOrder, id=order_id)
    
    if not order.brief_files:
        return HttpResponse("""
            <html>
                <body style="background: #0a0a0a; color: #00f5ff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif;">
                    <div style="border: 4px solid #1e3a8a; border-top: 4px solid #00f5ff; border-radius: 50%; width: 50px; height: 50px; animate: spin 1s linear infinite;"></div>
                    <h2 style="margin-top: 20px;">AI is generating your site...</h2>
                    <p style="color: #64748b;">Please wait a moment while we deploy the assets.</p>
                    <script>setTimeout(() => window.location.reload(), 5000);</script>
                    <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
                </body>
            </html>
        """, status=200)
    
    try:
        if not order.brief_files:
            raise FileNotFoundError("No preview file generated yet.")
            
        # Check if the file actually exists in storage
        if not order.brief_files.storage.exists(order.brief_files.name):
            return HttpResponse("""
                <html>
                    <body style="background: #0a0a0a; color: #64748b; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif; text-align: center; padding: 20px;">
                        <h2 style="color: #ef4444;">Preview File Not Found</h2>
                        <p>The code was generated but the entry file is missing from storage.</p>
                        <p style="font-size: 13px; opacity: 0.7;">This can happen if the background task failed during the final save step.</p>
                        <button onclick="window.location.reload()" style="margin-top: 20px; padding: 10px 20px; background: #1e3a8a; color: white; border: none; border-radius: 8px; cursor: pointer;">Retry Refresh</button>
                    </body>
                </html>
            """, status=404)

        # Read the file content as binary and decode to handle UTF-8 safely
        with order.brief_files.open('rb') as f:
            content = f.read().decode('utf-8')
        
        return HttpResponse(content, content_type='text/html')
    except Exception as e:
        return HttpResponse(f"Error loading preview: {str(e)}", status=500)
