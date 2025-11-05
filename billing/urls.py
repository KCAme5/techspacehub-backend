from django.urls import path
from .views import (
    StripeWebhookView,
    MpesaCallbackView,
    CreateStripeCheckoutSession,
    VerifyStripePayment,
    InitiateMpesaPayment,
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
    path(
        "initiate/mpesa/", InitiateMpesaPayment.as_view(), name="initiate-mpesa-payment"
    ),
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
    path("mpesa-callback/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]
