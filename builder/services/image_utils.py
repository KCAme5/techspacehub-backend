# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — builder/services/image_utils.py  (create this new file)
# Shared utility used by preview proxy, ZIP export, and future GitHub push
# ════════════════════════════════════════════════════════════════════════════

import re
from urllib.parse import unquote, quote


# ── Proxy URL helpers ─────────────────────────────────────────────────────────

PROXY_PREFIX = '/api/builder/proxy/image/?url='

def to_proxy_url(original_url: str) -> str:
    """Convert an external image URL to a proxy URL."""
    return f"{PROXY_PREFIX}{quote(original_url, safe='')}"


def from_proxy_url(proxy_url: str) -> str:
    """Extract the original URL from a proxy URL."""
    if PROXY_PREFIX in proxy_url:
        encoded = proxy_url.split(PROXY_PREFIX, 1)[1]
        return unquote(encoded)
    return proxy_url


# ── Restore proxy URLs → original URLs (used at export/download/push time) ───

def restore_image_urls(content: str) -> str:
    """
    Replace all /api/builder/proxy/image/?url=... back to original direct URLs.
    Called before generating ZIP or pushing to GitHub — proxy URLs must never
    appear in files the user receives or deploys.

    Works on HTML, CSS, JSX, JS — any text content.
    """
    def decode_match(match):
        encoded = match.group(1)
        return unquote(encoded)

    # Match proxy URL in any context: src="...", url('...'), href="...", etc.
    return re.sub(
        r'/api/builder/proxy/image/\?url=([^\s"\'`\)]+)',
        decode_match,
        content
    )


def restore_files(files: list) -> list:
    """
    Restore image URLs in a list of {"name": ..., "content": ...} file dicts.
    Pass the full files list — returns a new list with clean URLs.
    Ready to use for both ZIP export and GitHub push.
    """
    return [
        {"name": f["name"], "content": restore_image_urls(f["content"])}
        for f in files
    ]


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — Add ImageProxyView to builder/views.py
#
# Add this import at the top of views.py:
#   import requests as ext_requests
#   from urllib.parse import urlparse
#
# Then add this class anywhere in views.py:
# ════════════════════════════════════════════════════════════════════════════

"""
class ImageProxyView(APIView):
    \"\"\"
    GET /api/builder/proxy/image/?url=https://loremflickr.com/...
    Proxies external images through your server so sandboxed iframes
    can load them (null-origin CORS restriction bypass).
    AllowAny — no auth needed, images are public.
    \"\"\"
    permission_classes = [AllowAny]

    # Allowlist of domains the proxy will fetch from
    # Prevents your server being used as an open proxy
    ALLOWED_DOMAINS = {
        'loremflickr.com',
        'picsum.photos',
        'images.unsplash.com',
        'source.unsplash.com',
        'live.staticflickr.com',      # loremflickr pulls from Flickr CDN
        'farm1.staticflickr.com',
        'farm2.staticflickr.com',
        'farm3.staticflickr.com',
        'farm4.staticflickr.com',
        'farm5.staticflickr.com',
        'farm6.staticflickr.com',
        'farm7.staticflickr.com',
        'farm8.staticflickr.com',
        'farm9.staticflickr.com',
        'c1.staticflickr.com',
        'c2.staticflickr.com',
        'c3.staticflickr.com',
        'c4.staticflickr.com',
        'c5.staticflickr.com',
        'c6.staticflickr.com',
        'c7.staticflickr.com',
        'c8.staticflickr.com',
    }

    def get(self, request):
        import requests as ext_requests
        from urllib.parse import urlparse
        from django.http import HttpResponse

        url = request.query_params.get('url', '').strip()

        if not url:
            return HttpResponse(status=400)

        # Security: only allow https
        if not url.startswith('https://'):
            return HttpResponse(status=403)

        # Security: only allow known image domains
        domain = urlparse(url).netloc.lstrip('www.')
        if not any(url.startswith(f'https://{d}') or
                   url.startswith(f'https://www.{d}') or
                   domain.endswith(d)
                   for d in self.ALLOWED_DOMAINS):
            return HttpResponse(status=403)

        try:
            resp = ext_requests.get(
                url,
                timeout=15,
                headers={
                    'User-Agent': 'TechSpaceHub-ImageProxy/1.0',
                    'Accept': 'image/*,*/*',
                },
                allow_redirects=True,   # loremflickr redirects to Flickr CDN
            )

            if resp.status_code != 200:
                return HttpResponse(status=resp.status_code)

            content_type = resp.headers.get('Content-Type', 'image/jpeg')

            # Only serve actual images
            if not content_type.startswith('image/'):
                return HttpResponse(status=403)

            response = HttpResponse(resp.content, content_type=content_type)
            # Cache for 1 hour — same image URL always returns same photo
            response['Cache-Control'] = 'public, max-age=3600'
            response['Access-Control-Allow-Origin'] = '*'
            return response

        except ext_requests.exceptions.Timeout:
            return HttpResponse(status=504)
        except Exception:
            return HttpResponse(status=502)
"""


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — Add URL pattern to builder/urls.py
#
# Add this line:
#   path('api/builder/proxy/image/', ImageProxyView.as_view()),
#
# And import ImageProxyView at the top of urls.py
# ════════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — Update export/download to restore proxy URLs
#
# In your export_service.py or wherever you generate the ZIP,
# import restore_files and call it before building the ZIP:
#
#   from .services.image_utils import restore_files
#
#   def generate_project_zip(project):
#       files = project.files  # list of {"name": ..., "content": ...}
#       clean_files = restore_files(files)  # ← proxy URLs → direct URLs
#       # ... build ZIP from clean_files ...
#
# For the builder's GenerationSession ZIP download, in views.py
# SessionDetailView or wherever you serve files for download:
#
#   from .services.image_utils import restore_files
#   clean_files = restore_files(session.files)
#   # use clean_files for ZIP generation
# ════════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════════
# GITHUB PUSH — future feature design note
#
# When you implement GitHub push, the flow is:
#
#   1. User clicks "Push to GitHub"
#   2. Frontend sends: { session_id, github_token, repo_name }
#   3. Django view:
#      a. Load session.files
#      b. clean_files = restore_files(session.files)  ← same function
#      c. Create GitHub repo via API if it doesn't exist
#      d. Push each file in clean_files to the repo
#
# The restore_files() function is the single shared step that ensures
# proxy URLs never appear in any output — ZIP, GitHub, or future targets.
#
# GitHub push view skeleton (add when ready):
#
#   class PushToGithubView(APIView):
#       permission_classes = [IsAuthenticated]
#
#       def post(self, request):
#           from .services.image_utils import restore_files
#           import base64
#
#           session_id   = request.data.get('session_id')
#           github_token = request.data.get('github_token')
#           repo_name    = request.data.get('repo_name', 'my-website')
#
#           session = GenerationSession.objects.get(id=session_id, user=request.user)
#           clean_files = restore_files(session.files)
#
#           headers = {
#               'Authorization': f'token {github_token}',
#               'Accept': 'application/vnd.github.v3+json',
#           }
#
#           # Create repo
#           import requests as req
#           req.post('https://api.github.com/user/repos',
#               headers=headers,
#               json={'name': repo_name, 'auto_init': False}
#           )
#
#           # Push each file
#           username = req.get('https://api.github.com/user', headers=headers).json()['login']
#           for file in clean_files:
#               content_b64 = base64.b64encode(file['content'].encode()).decode()
#               req.put(
#                   f'https://api.github.com/repos/{username}/{repo_name}/contents/{file["name"]}',
#                   headers=headers,
#                   json={
#                       'message': f'Add {file["name"]}',
#                       'content': content_b64,
#                   }
#               )
#
#           return Response({'repo_url': f'https://github.com/{username}/{repo_name}'})
# ════════════════════════════════════════════════════════════════════════════