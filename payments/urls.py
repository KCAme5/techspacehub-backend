# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/',                        views.InitiatePaymentView.as_view(),   name='initiate'),
    path('callback/',                        views.MpesaCallbackView.as_view(),     name='callback'),
    path('status/<int:payment_id>/',         views.PaymentStatusView.as_view(),     name='status'),
    path('access/module/<int:module_id>/',   views.ModuleAccessCheckView.as_view(), name='module-access'),
]
