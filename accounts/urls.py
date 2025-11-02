from django.urls import path
from .social import GoogleLogin  # GitHubLogin
from .views import (
    RegisterView,
    LoginView,
    PasswordResetRequestView,
    SetNewPasswordView,
    ProfileView,
    VerifyEmailView,
    ResendVerificationView,
    WalletView,
    WalletTransactionsView,
    ReferralStatsView,
    ReferralListView,
    WithdrawalRequestView,
    UserPreferencesView,
    ChangePasswordView,
    UpdateProfileView,
    DebugReferralView,
)
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        SetNewPasswordView.as_view(),
        name="password_reset_confirm",
    ),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("me/", views.me, name="me"),
    path(
        "verify-email/<uidb64>/<token>/", VerifyEmailView.as_view(), name="verify_email"
    ),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path("wallet/", WalletView.as_view(), name="wallet"),
    path(
        "wallet/transactions/",
        WalletTransactionsView.as_view(),
        name="wallet-transactions",
    ),
    path("referrals/stats/", ReferralStatsView.as_view(), name="referral-stats"),
    path("referrals/list/", ReferralListView.as_view(), name="referral-list"),
    path("withdrawals/", WithdrawalRequestView.as_view(), name="withdrawals"),
    path("preferences/", UserPreferencesView.as_view(), name="user-preferences"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("update-profile/", UpdateProfileView.as_view(), name="update-profile"),
    path("debug-referral/", DebugReferralView.as_view(), name="debug-referral"),
    path("google/", GoogleLogin.as_view(), name="google_login"),
    # path("github/", GitHubLogin.as_view(), name="github_login"),
]
