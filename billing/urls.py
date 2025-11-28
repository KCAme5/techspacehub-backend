from django.urls import path
from .views import (
    StripeWebhookView,
    MpesaCallbackView,
    CreateStripeCheckoutSession,
    VerifyStripePayment,
    InitiateStkPushPayment,
    LipanaCallbackView,
    PaymentStatusView,
    ChoosePlanEnrollView,
    InitiateManualMpesaPayment,
)

urlpatterns = [
    path("choose-plan/", ChoosePlanEnrollView.as_view(), name="choose-plan"),
    path(
        "initiate/stripe/",
        CreateStripeCheckoutSession.as_view(),
        name="create-stripe-session",
    ),
    path("stripe-webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("verify/stripe/", VerifyStripePayment.as_view(), name="verify-stripe-payment"),
    # New Lipana STK Push endpoint (PRIMARY M-Pesa method)
    path(
        "initiate/stk-push/",
        InitiateStkPushPayment.as_view(),
        name="initiate-lipana-stk-push",
    ),
    path("lipana-callback/", LipanaCallbackView.as_view(), name="lipana-callback"),
    # Legacy M-Pesa endpoint (kept for backward compatibility)
    path(
        "initiate/manual-mpesa/",
        InitiateManualMpesaPayment.as_view(),
        name="initiate-manual-mpesa",
    ),
    path(
        "status/<str:checkout_request_id>/",
        PaymentStatusView.as_view(),
        name="payment-status",
    ),
    # Legacy Safaricom callback (kept for backward compatibility)
    path("mpesa-callback/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]
