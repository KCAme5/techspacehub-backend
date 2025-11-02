# accounts/middleware.py (enhanced version)
import logging
from rest_framework_simplejwt.tokens import RefreshToken
from urllib.parse import urlencode
from django.http import HttpResponseRedirect

logger = logging.getLogger("accounts")


class SocialAuthRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Check if this is a Google callback and user is authenticated
        if (
            request.path == "/accounts/google/login/callback/"
            and request.user.is_authenticated
        ):

            try:
                logger.info(f"Social auth successful for user: {request.user.email}")

                # Generate JWT tokens
                refresh = RefreshToken.for_user(request.user)
                access_token = str(refresh.access_token)
                refresh_token = str(refresh)

                # Build frontend URL
                params = urlencode({"access": access_token, "refresh": refresh_token})
                frontend_url = f"http://localhost:5173/oauth2/redirect?{params}"

                logger.info(f"Redirecting to frontend with tokens")
                return HttpResponseRedirect(frontend_url)

            except Exception as e:
                logger.error(f"Error in social auth middleware: {e}")
                # Fallback: redirect to login with error
                return HttpResponseRedirect(
                    "http://localhost:5173/login?error=auth_failed"
                )

        return response
