# payments/views.py
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Module, Level
from .models import Payment, MpesaTransaction
from .serializers import InitiatePaymentSerializer, PaymentSerializer
from .services import initiate_stk_push, handle_callback
from progress.models import UserModuleAccess


class InitiatePaymentView(APIView):
    """POST /api/hub/payments/initiate/  — start M-Pesa STK push."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = InitiatePaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        module = level = None
        if d['payment_for'] == 'single_module' and d.get('module_id'):
            try:
                module = Module.objects.get(pk=d['module_id'])
            except Module.DoesNotExist:
                return Response({'detail': 'Module not found.'}, status=status.HTTP_404_NOT_FOUND)

        if d['payment_for'] == 'full_level' and d.get('level_id'):
            try:
                level = Level.objects.get(pk=d['level_id'])
            except Level.DoesNotExist:
                return Response({'detail': 'Level not found.'}, status=status.HTTP_404_NOT_FOUND)

        payment = Payment.objects.create(
            user=request.user,
            module=module,
            level=level,
            payment_for=d['payment_for'],
            amount=d['amount'],
        )

        ref = f"MODULE-{module.id}" if module else f"LEVEL-{level.id}"
        desc = f"TechSpaceHub {'Module' if module else 'Level'} Access"

        try:
            resp = initiate_stk_push(d['phone_number'], int(d['amount']), ref, desc)
        except Exception as e:
            payment.status = 'failed'
            payment.save()
            return Response({'detail': f'M-Pesa error: {e}'}, status=status.HTTP_502_BAD_GATEWAY)

        txn = MpesaTransaction.objects.create(
            payment=payment,
            phone_number=d['phone_number'],
            checkout_request_id=resp.get('CheckoutRequestID', ''),
            merchant_request_id=resp.get('MerchantRequestID', ''),
        )

        return Response({
            'payment_id':          payment.id,
            'checkout_request_id': txn.checkout_request_id,
            'message':             'STK push initiated. Check your phone.',
        }, status=status.HTTP_201_CREATED)


class MpesaCallbackView(APIView):
    """POST /api/hub/payments/callback/  — Safaricom callback (no JWT)."""
    permission_classes = [AllowAny]

    def post(self, request):
        handle_callback(request.data)
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class PaymentStatusView(APIView):
    """GET /api/hub/payments/status/<payment_id>/  — poll payment status."""
    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        try:
            payment = Payment.objects.get(pk=payment_id, user=request.user)
        except Payment.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'payment_id': payment.id, 'status': payment.status})


class ModuleAccessCheckView(APIView):
    """GET /api/hub/payments/access/module/<module_id>/  — check learner access."""
    permission_classes = [IsAuthenticated]

    def get(self, request, module_id):
        try:
            module = Module.objects.get(pk=module_id)
        except Module.DoesNotExist:
            return Response({'detail': 'Module not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_free   = module.order <= 2
        has_paid  = UserModuleAccess.objects.filter(
            user=request.user, module=module
        ).exists()

        return Response({
            'module_id': module_id,
            'is_free':   is_free,
            'has_access': is_free or has_paid,
        })
