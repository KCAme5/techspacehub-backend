# accounts/custom_google_provider.py
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.base import ProviderAccount


class CustomGoogleAccount(ProviderAccount):
    pass


class CustomGoogleProvider(GoogleProvider):
    id = "custom_google"
    name = "Custom Google"
    account_class = CustomGoogleAccount

    def get_login_redirect_url(self, request, sociallogin=None):
        from urllib.parse import urlencode
        from rest_framework_simplejwt.tokens import RefreshToken

        user = sociallogin.user
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        params = urlencode({"access": access_token, "refresh": refresh_token})
        return f"http://localhost:5173/oauth2/redirect?{params}"
