"""
builder/views.py — Credit system API views for the AI Website Builder.
"""
import logging
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import UserCredits, CreditPackage, CreditPayment
from .serializers import UserCreditsSerializer, CreditPackageSerializer

logger = logging.getLogger(__name__)


class CreditBalanceView(APIView):
    """GET /api/builder/credits/balance/ — Return the user's current credit balance."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        credits_obj, _ = UserCredits.objects.get_or_create(
            user=request.user,
            defaults={'credits': 20, 'is_free_tier': True}
        )
        return Response(UserCreditsSerializer(credits_obj).data)


class CreditPackagesView(APIView):
    """GET /api/builder/credits/packages/ — Return available credit packages."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        packages = CreditPackage.objects.filter(is_active=True)
        return Response(CreditPackageSerializer(packages, many=True).data)


class PurchaseCreditsView(APIView):
    """
    POST /api/builder/credits/purchase/
    Body: { package_id, phone_number }
    Creates a pending CreditPayment and initiates an M-Pesa STK push.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        package_id   = request.data.get('package_id')
        phone_number = request.data.get('phone_number', '').strip()

        if not package_id or not phone_number:
            return Response(
                {'error': 'package_id and phone_number are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        package = get_object_or_404(CreditPackage, id=package_id, is_active=True)

        # Normalize phone: ensure it starts with 2547
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            phone_number = phone_number[1:]

        # Create pending payment record
        payment = CreditPayment.objects.create(
            user=request.user,
            package=package,
            amount=package.price_kes,
            credits=package.credits,
            phone_number=phone_number,
            status='pending',
        )

        # Initiate M-Pesa STK push
        try:
            from payments.services import initiate_stk_push
            result = initiate_stk_push(
                phone=phone_number,
                amount=int(package.price_kes),
                ref=f'CREDITS-{str(payment.id)[:8].upper()}',
                description=f'TechSpaceHub {package.credits} AI Credits',
            )
            logger.info(f"M-Pesa STK result for payment {payment.id}: {result}")

            if 'CheckoutRequestID' in result:
                payment.mpesa_checkout_id = result['CheckoutRequestID']
                payment.save()
                return Response({
                    'payment_id': str(payment.id),
                    'message': 'STK push sent. Check your phone.',
                })
            else:
                payment.status = 'failed'
                payment.save()
                error_msg = result.get('errorMessage') or result.get('CustomerMessage') or 'M-Pesa initiation failed'
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"STK push error for payment {payment.id}: {e}")
            payment.status = 'failed'
            payment.save()
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class CreditPaymentStatusView(APIView):
    """
    GET /api/builder/credits/payment-status/<payment_id>/
    Frontend polls this every 3 seconds to know if payment succeeded.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(CreditPayment, id=payment_id, user=request.user)
        data = {
            'status': payment.status,
            'credits': 0,
        }
        if payment.status == 'completed':
            # Also return the user's new credit balance
            try:
                data['credits'] = request.user.ai_credits.credits
            except UserCredits.DoesNotExist:
                data['credits'] = payment.credits
        return Response(data)


class MpesaCreditCallbackView(APIView):
    """
    POST /api/builder/credits/mpesa-callback/
    Called by Safaricom upon payment completion/failure.
    This is AllowAny — no JWT, Safaricom doesn't send auth.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data        = request.data
        stk         = data.get('Body', {}).get('stkCallback', {})
        checkout_id = stk.get('CheckoutRequestID', '')
        result_code = str(stk.get('ResultCode', ''))

        logger.info(f"M-Pesa Credit Callback: checkout_id={checkout_id}, result_code={result_code}")

        try:
            payment = CreditPayment.objects.get(mpesa_checkout_id=checkout_id)
        except CreditPayment.DoesNotExist:
            logger.warning(f"No CreditPayment found for checkout_id: {checkout_id}")
            return Response({'status': 'ignored'})

        if payment.status == 'completed':
            # Idempotency — already processed
            return Response({'status': 'ok'})

        if result_code == '0':
            # Extract receipt number
            items = stk.get('CallbackMetadata', {}).get('Item', [])
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    payment.mpesa_receipt = str(item.get('Value', ''))

            with transaction.atomic():
                payment.status       = 'completed'
                payment.completed_at = timezone.now()
                payment.save()

                # Atomically add credits to user's balance
                user_credits, _ = UserCredits.objects.get_or_create(
                    user=payment.user,
                    defaults={'credits': 0, 'is_free_tier': True}
                )
                UserCredits.objects.filter(pk=user_credits.pk).update(
                    credits=F('credits') + payment.credits,
                    total_purchased=F('total_purchased') + payment.credits,
                    is_free_tier=False,
                )
                logger.info(f"Granted {payment.credits} credits to {payment.user.username}")
        else:
            payment.status = 'failed'
            payment.save()
            logger.warning(f"M-Pesa payment failed for {payment.user.username}: {stk.get('ResultDesc', '')}")

        return Response({'status': 'ok'})


class DeductCreditView(APIView):
    """
    POST /api/builder/credits/deduct/
    Called internally after a successful AI generation to record credit usage.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            with transaction.atomic():
                credits_obj = UserCredits.objects.select_for_update().get(user=request.user)
                if credits_obj.credits <= 0:
                    return Response({'error': 'Not enough credits.'}, status=status.HTTP_402_PAYMENT_REQUIRED)
                credits_obj.credits   -= 1
                credits_obj.total_used += 1
                credits_obj.save()
                return Response({'credits': credits_obj.credits})
        except UserCredits.DoesNotExist:
            return Response({'error': 'No credit account found.'}, status=status.HTTP_404_NOT_FOUND)
