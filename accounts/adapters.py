from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import redirect
from urllib.parse import urlencode
import logging
from django.conf import settings

logger = logging.getLogger("accounts")


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_login_redirect_url(self, request):
        logger.info("CustomSocialAccountAdapter.get_login_redirect_url called")
        logger.info(
            f"User: {request.user}, Authenticated: {request.user.is_authenticated}"
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(request.user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Build frontend URL with tokens - PRODUCTION
        params = urlencode({"access": access_token, "refresh": refresh_token})
        frontend_url = f"{settings.FRONTEND_URL}/oauth2/redirect?{params}"

        logger.info(f"Redirecting to: {frontend_url}")
        return frontend_url
