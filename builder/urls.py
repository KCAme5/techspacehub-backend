"""
builder/urls.py — Credit system API endpoints for the AI Website Builder.
"""

from django.urls import path
from .views import (
    CreditBalanceView,
    CreditPackagesView,
    PurchaseCreditsView,
    CreditPaymentStatusView,
    MpesaCreditCallbackView,
    DeductCreditView,
    EnhancePromptView,
    GenerateView,
    SessionListView,
    SessionDetailView,
    DeleteSessionView,
)

urlpatterns = [
    path("credits/balance/", CreditBalanceView.as_view(), name="credit-balance"),
    path("credits/packages/", CreditPackagesView.as_view(), name="credit-packages"),
    path("credits/purchase/", PurchaseCreditsView.as_view(), name="credit-purchase"),
    path(
        "credits/payment-status/<uuid:payment_id>/",
        CreditPaymentStatusView.as_view(),
        name="credit-payment-status",
    ),
    path(
        "credits/mpesa-callback/",
        MpesaCreditCallbackView.as_view(),
        name="credit-mpesa-callback",
    ),
    path("credits/deduct/", DeductCreditView.as_view(), name="credit-deduct"),
    path("enhance-prompt/", EnhancePromptView.as_view(), name="enhance-prompt"),
    # Generation and session endpoints
    path("generate/", GenerateView.as_view(), name="generate"),
    path("sessions/", SessionListView.as_view(), name="session-list"),
    path(
        "sessions/<uuid:session_id>/",
        SessionDetailView.as_view(),
        name="session-detail",
    ),
    path(
        "sessions/<uuid:session_id>/delete/",
        DeleteSessionView.as_view(),
        name="session-delete",
    ),
]
