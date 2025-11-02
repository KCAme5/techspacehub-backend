# accounts/social.py
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from urllib.parse import urlencode
from django.shortcuts import redirect


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    callback_url = "http://localhost:8000/accounts/google/callback/"

    def post(self, request, *args, **kwargs):
        # This handles the callback from Google
        response = super().post(request, *args, **kwargs)

        if request.user.is_authenticated:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(request.user)

            # Return tokens in response
            data = response.data
            data["access_token"] = str(refresh.access_token)
            data["refresh_token"] = str(refresh)

            # For API calls, return JSON; for browser, redirect
            if request.accepts("text/html"):
                params = urlencode(
                    {"access": data["access_token"], "refresh": data["refresh_token"]}
                )
                frontend_url = f"http://localhost:5173/oauth2/redirect?{params}"
                return redirect(frontend_url)

        return response
