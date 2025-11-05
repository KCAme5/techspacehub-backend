from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from django.utils import timezone
from courses.models import Week, Enrollment  # Changed from Course
from accounts.models import Subscription, User
from .models import Payment
from requests.auth import HTTPBasicAuth
import requests
import stripe
import datetime
from base64 import b64encode
import logging
from accounts.views import process_referral_commission

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


# === Currency Conversion Helper ===
def convert_kes_to_usd(amount_kes, rate=None):
    if rate is None:
        rate = 130
    usd_amount = round(float(amount_kes) / rate, 2)
    return usd_amount


class ChoosePlanEnrollView(APIView):
    """
    Handles week enrollment depending on chosen plan.
    - FREE → enroll instantly
    - BASIC/PRO → returns payment info
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        plan = request.data.get("plan")  # FREE / BASIC / PRO
        week_id = request.data.get("week_id")  # Changed from course_id

        logger.info(
            f"ChoosePlanEnrollView: user={user.id}, week_id={week_id}, plan={plan}"
        )

        if not plan or not week_id:
            logger.error("Missing plan or week_id")
            return Response({"error": "Missing plan or week_id"}, status=400)

        try:
            week = Week.objects.get(id=week_id)
            logger.info(f"Week found: {week}")
        except Week.DoesNotExist:
            return Response({"error": "Week not found"}, status=404)

        if plan == "FREE":
            enrollment, created = Enrollment.objects.get_or_create(
                user=user, week=week, defaults={"plan": "FREE", "is_active": True}
            )
            if not created:
                enrollment.plan = "FREE"
                enrollment.is_active = True
                enrollment.save()
                logger.info(f"Updated existing enrollment to FREE: {enrollment.id}")
            else:
                logger.info(f"Created new FREE enrollment: {enrollment.id}")

            return Response(
                {
                    "success": True,
                    "message": "You've been enrolled in the free plan.",
                    "enrollment": {
                        "id": enrollment.id,
                        "week": enrollment.week.id,
                        "plan": enrollment.plan,
                        "enrolled_at": enrollment.enrolled_at,
                    },
                },
                status=status.HTTP_200_OK,
            )

        # BASIC or PRO → return payment details
        if plan in ["BASIC", "PRO"]:
            amount = float(week.price)  # Use week price instead of course price
            logger.info(f"Payment required: plan={plan}, amount={amount}")
            return Response(
                {
                    "requires_payment": True,
                    "plan": plan,
                    "amount": amount,
                    "message": f"Proceed to payment for {plan} plan",
                },
                status=status.HTTP_200_OK,
            )
        logger.error(f"Invalid plan: {plan}")
        return Response({"error": "Invalid plan selected"}, status=400)


class InitiateMpesaPayment(APIView):
    """Initiates an M-Pesa STK push for week payment."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.info("=== MPESA PAYMENT INITIATION STARTED ===")
        try:
            phone = request.data.get("phone")
            week_id = request.data.get("week_id")
            plan = request.data.get("plan", "BASIC")
            logger.info(f"Request data: phone={phone}, week_id={week_id}, plan={plan}")
            logger.info(f"Full request data: {request.data}")

            if not phone or not week_id:
                logger.error("Missing phone or week_id")
                return Response(
                    {"error": "Phone number and week ID are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate phone format (Kenyan format)
            original_phone = phone
            if not phone.startswith("254") and phone.startswith("0"):
                phone = "254" + phone[1:]
            elif not phone.startswith("254") and not phone.startswith("0"):
                phone = "254" + phone
            logger.info(f"Phone normalized: {original_phone} -> {phone}")

            try:
                week = Week.objects.get(id=week_id)
                logger.info(f"Week found: {week}")
            except Week.DoesNotExist:
                logger.error(f"Week not found: {week_id}")
                return Response(
                    {"error": "Week not found"}, status=status.HTTP_404_NOT_FOUND
                )

            user = request.user
            logger.info(f"User: {user.id} - {user.email}")

            # Check if already enrolled - ALLOW UPGRADES FROM FREE TO PAID PLANS
            existing_enrollment = Enrollment.objects.filter(
                user=user, week=week
            ).first()
            if existing_enrollment:
                # Allow upgrade from FREE to BASIC/PRO
                if existing_enrollment.plan == "FREE" and plan in ["BASIC", "PRO"]:
                    logger.info(
                        f"Allowing upgrade from FREE to {plan} for week {week.id}"
                    )
                elif existing_enrollment.plan == plan:
                    return Response(
                        {
                            "error": f"You are already enrolled in this week with {plan} plan"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return Response(
                        {
                            "error": f"Cannot change plan from {existing_enrollment.plan} to {plan}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Determine amount - use week price
            amount = int(float(week.price))
            logger.info(f"Amount determined: {amount} for plan {plan}")

            # Check if already enrolled
            existing_enrollment = Enrollment.objects.filter(
                user=user, week=week
            ).first()
            if existing_enrollment:
                if existing_enrollment.plan == plan:
                    return Response(
                        {
                            "error": f"You are already enrolled in this week with {plan} plan"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Get M-Pesa access token
            consumer_key = settings.MPESA_CONSUMER_KEY
            consumer_secret = settings.MPESA_CONSUMER_SECRET
            auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            r = requests.get(
                auth_url, auth=HTTPBasicAuth(consumer_key, consumer_secret)
            )
            access_token = r.json().get("access_token")
            if not access_token:
                logger.error("Failed to obtain M-Pesa token")
                return Response(
                    {"error": "Failed to obtain M-Pesa token"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            logger.info("Successfully obtained MPESA access token")

            # Prepare STK push payload
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            short_code = settings.MPESA_SHORTCODE
            passkey = settings.MPESA_PASSKEY
            password = b64encode(f"{short_code}{passkey}{timestamp}".encode()).decode(
                "utf-8"
            )

            backend_url = getattr(settings, "BACKEND_URL", None)
            if not backend_url:
                logger.error("BACKEND_URL not configured")
                return Response(
                    {"error": "BACKEND_URL not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            callback_url = f"{backend_url}/api/payments/mpesa-callback/"
            logger.info(f"Callback URL: {callback_url}")

            payload = {
                "BusinessShortCode": short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": phone,
                "PartyB": short_code,
                "PhoneNumber": phone,
                "CallBackURL": callback_url,
                "AccountReference": f"{user.id}-{week.id}-{plan}",
                "TransactionDesc": f"Payment for {week} ({plan})",
            }
            logger.info(f"STK Push payload: {payload}")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            stk_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
            logger.info("Sending STK push request...")
            response = requests.post(stk_url, json=payload, headers=headers)
            res_data = response.json()

            logger.info(f"STK push response status: {response.status_code}")
            logger.info(f"STK push response data: {res_data}")

            if response.status_code != 200:
                return Response(
                    {"error": "M-Pesa STK request failed", "details": res_data},
                    status=response.status_code,
                )

            checkout_request_id = res_data.get("CheckoutRequestID")
            if not checkout_request_id:
                logger.error("Missing CheckoutRequestID in response")
                return Response(
                    {"error": "Missing CheckoutRequestID"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            logger.info(f"CheckoutRequestID: {checkout_request_id}")

            # Save payment record
            payment = Payment.objects.create(
                user=user,
                week=week,  # Changed from course
                plan=plan,
                amount=amount,
                currency="KES",
                method="mpesa",
                status="pending",
                transaction_id=checkout_request_id,
            )
            logger.info(f"Payment record created: {payment.id}")

            return Response(
                {
                    "success": True,
                    "message": "STK Push sent. Complete payment on your phone.",
                    "CheckoutRequestID": checkout_request_id,
                    "payment_id": payment.id,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"MPESA payment initiation failed: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Payment initiation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            payment = Payment.objects.get(
                transaction_id=checkout_request_id, user=request.user
            )
            return Response(
                {
                    "success": True,
                    "status": payment.status,
                    "payment_id": payment.id,
                    "week_id": payment.week.id,  # Changed from course_id
                    "week_title": str(payment.week),  # Changed from course_title
                    "amount": payment.amount,
                    "plan": payment.plan,
                    "created_at": payment.created_at,
                }
            )
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class MpesaCallbackView(APIView):
    """Handles M-Pesa callback from Safaricom."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        transaction_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")

        logger.info(
            f"MPESA CALLBACK: transaction_id={transaction_id}, result_code={result_code}"
        )
        logger.info(f"Full callback data: {data}")

        if not transaction_id:
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            user = payment.user
            week = payment.week  # Changed from course
            plan = payment.plan
            logger.info(
                f"Processing payment: user={user.id}, week={week.id}, plan={plan}"
            )

            if str(result_code) == "0":
                payment.status = "success"
                payment.save()
                logger.info(f"Payment marked as success: {payment.id}")

                # Enroll user in week
                enrollment, created = Enrollment.objects.get_or_create(
                    user=user, week=week, defaults={"plan": plan, "is_active": True}
                )

                if not created:
                    # Update existing enrollment
                    enrollment.plan = plan
                    enrollment.is_active = True
                    enrollment.save()
                    logger.info(f"Updated existing enrollment: {enrollment.id}")
                else:
                    logger.info(f"Created new enrollment: {enrollment.id}")

                logger.info(f"=== CHECKING FOR REFERRAL COMMISSION ===")
                logger.info(f"User referred_by: {user.referred_by}")
                if user.referred_by:
                    logger.info(f"User was referred by: {user.referred_by.email}")
                else:
                    logger.info(f"User was not referred by anyone")

                commission_result = process_referral_commission(user, payment.amount)
                if commission_result:
                    logger.info(
                        f"Referral commission processed successfully for payment: {payment.id}"
                    )
                else:
                    logger.info(f"No referral commission processed for user: {user.id}")
            else:
                payment.status = "failed"
                callback_metadata = stk_callback.get("CallbackMetadata", {}).get(
                    "Item", []
                )
                for item in callback_metadata:
                    if item["Name"] == "MpesaReceiptNumber":
                        payment.mpesa_receipt = item.get("Value")
                payment.save()
                logger.error(f"Payment failed with result_code: {result_code}")

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for transaction_id: {transaction_id}")

        return Response({"status": "callback received"}, status=status.HTTP_200_OK)


class CreateStripeCheckoutSession(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.info("=== STRIPE PAYMENT INITIATION STARTED ===")

        try:
            week_id = request.data.get("week_id")
            plan = request.data.get("plan", "BASIC")
            logger.info(f"Request data: week_id={week_id}, plan={plan}")

            # --- Validate ---
            if not week_id:
                return Response(
                    {"error": "Week ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # --- Fetch week ---
            try:
                week = Week.objects.get(id=week_id)
                logger.info(f"Week found: {week} (ID: {week.id})")
            except Week.DoesNotExist:
                return Response(
                    {"error": "Week not found"}, status=status.HTTP_404_NOT_FOUND
                )

            user = request.user
            logger.info(f"User: {user.id} - {user.email}")

            # --- Check enrollment ---
            existing_enrollment = Enrollment.objects.filter(
                user=user, week=week
            ).first()

            if existing_enrollment:
                if existing_enrollment.plan == "FREE" and plan in ["BASIC", "PRO"]:
                    logger.info(f"Upgrading from FREE to {plan} for week {week.id}")
                elif existing_enrollment.plan == plan:
                    return Response(
                        {"error": f"Already enrolled in this week with {plan} plan"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return Response(
                        {
                            "error": f"Cannot change plan from {existing_enrollment.plan} to {plan}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # --- Compute Amount ---
            amount_usd = convert_kes_to_usd(float(week.price))
            amount = int(amount_usd * 100)  # Stripe requires cents
            logger.info(f"Converted amount: {week.price} KES = {amount_usd} USD")

            # --- Verify Stripe setup ---
            if not getattr(settings, "STRIPE_SECRET_KEY", None):
                logger.error("Stripe secret key not configured")
                return Response(
                    {"error": "Stripe configuration missing"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            stripe.api_key = settings.STRIPE_SECRET_KEY

            # --- URLs ---
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            # In CreateStripeCheckoutSession view, update the success_url:
            success_url = (
                f"{frontend_url}/dashboard?payment_success=true"
                f"&session_id={{CHECKOUT_SESSION_ID}}&week_id={week_id}"
                f"&plan={plan}&user_id={user.id}"
            )
            cancel_url = f"{frontend_url}/dashboard/courses?stripe_cancelled=true"

            # --- Create checkout session ---
            logger.info("Creating Stripe checkout session...")
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"{week}",
                                "description": f"Upgrade to {plan} Plan - {week}",
                            },
                            "unit_amount": amount,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=user.email,
                metadata={
                    "user_id": str(user.id),
                    "week_id": str(week.id),
                    "plan": plan,
                    "is_upgrade": str(
                        existing_enrollment is not None
                        and existing_enrollment.plan == "FREE"
                    ),
                },
            )

            logger.info(f"Stripe session created: {session.id}")

            # --- Save Payment record ---
            Payment.objects.create(
                user=user,
                week=week,
                plan=plan,
                amount=amount / 100,
                currency="USD",
                method="stripe",
                status="pending",
                transaction_id=session.id,
            )

            logger.info(f"Payment record created for {user.email}")

            return Response(
                {"checkout_url": session.url, "session_id": session.id},
                status=status.HTTP_200_OK,
            )

        # --- Handle Stripe errors safely ---
        except Exception as e:
            logger.error(f"Stripe payment initiation failed: {e}", exc_info=True)
            return Response(
                {"error": f"Payment initiation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyStripePayment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.info("=== STRIPE PAYMENT VERIFICATION STARTED ===")
        session_id = request.data.get("session_id")
        logger.info(f"Verifying session: {session_id}")

        if not session_id:
            logger.error("Missing session_id")
            return Response({"error": "Missing session_id"}, status=400)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
            logger.info(f"Session retrieved: {session.id}")
            logger.info(f"Payment status: {session.payment_status}")
            logger.info(f"Session metadata: {session.metadata}")

            if session.payment_status != "paid":
                logger.error(f"Payment not completed. Status: {session.payment_status}")
                return Response(
                    {"success": False, "message": "Payment not completed"},
                    status=400,
                )

            user_id = session.metadata.get("user_id")
            week_id = session.metadata.get("week_id")
            plan = session.metadata.get("plan", "BASIC")
            is_upgrade = session.metadata.get("is_upgrade") == "True"

            logger.info(
                f"Metadata - user_id: {user_id}, week_id: {week_id}, plan: {plan}, is_upgrade: {is_upgrade}"
            )

            # Verify the user
            if str(request.user.id) != user_id:
                logger.error(
                    f"User mismatch: logged in as {request.user.id}, but payment for {user_id}"
                )
                return Response({"error": "User mismatch"}, status=403)

            user = User.objects.filter(id=user_id).first()
            week = Week.objects.filter(id=week_id).first()

            if not user:
                logger.error(f"User not found: {user_id}")
                return Response({"error": "User not found"}, status=404)
            if not week:
                logger.error(f"Week not found: {week_id}")
                return Response({"error": "Week not found"}, status=404)

            logger.info(f"Found user: {user.email}, week: {week}")

            # Create or update enrollment
            enrollment, created = Enrollment.objects.get_or_create(
                user=user, week=week, defaults={"plan": plan, "is_active": True}
            )

            if not created:
                # Update existing enrollment with new plan (UPGRADE)
                enrollment.plan = plan
                enrollment.is_active = True
                enrollment.save()
                logger.info(
                    f"UPGRADED enrollment: {enrollment.id}, from FREE to {plan}"
                )
            else:
                logger.info(
                    f"New enrollment created: {enrollment.id}, plan: {enrollment.plan}"
                )

            # Update payment record
            payment = Payment.objects.filter(transaction_id=session_id).first()
            if payment:
                payment.status = "success"
                payment.save()
                logger.info(f"Payment record updated: {payment.id}")

                logger.info(f"Checking for referral commission for user: {user.id}")
                commission_result = process_referral_commission(user, payment.amount)
                if commission_result:
                    logger.info(
                        f"Referral commission processed for payment: {payment.id}"
                    )
                else:
                    logger.info(f"No referral commission for user: {user.id}")
            else:
                logger.warning(f"No payment record found for session: {session_id}")

            logger.info("Stripe payment verification completed successfully")

            return Response(
                {
                    "success": True,
                    "message": "Payment verified successfully"
                    + (" and plan upgraded!" if is_upgrade else ""),
                    "enrollment": {
                        "week_title": str(week),
                        "plan": plan,
                        "enrolled_at": enrollment.enrolled_at.isoformat(),
                        "is_upgrade": is_upgrade,
                    },
                },
                status=200,
            )

        except Exception as e:
            logger.error(f"Stripe verification failed: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            return Response(status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            return Response(status=400)

        logger.info(f"Stripe webhook received: {event['type']}")

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            transaction_id = session.get("id")
            plan = session["metadata"].get("plan", "BASIC")
            is_upgrade = session["metadata"].get("is_upgrade") == "True"

            logger.info(
                f"Processing completed session: {transaction_id}, is_upgrade: {is_upgrade}"
            )

            try:
                payment = Payment.objects.get(transaction_id=transaction_id)
                user = payment.user
                week = payment.week

                # Update payment status
                payment.status = "success"
                payment.save()
                logger.info(f"Payment marked as success: {payment.id}")

                # Create or update enrollment
                enrollment, created = Enrollment.objects.get_or_create(
                    user=user, week=week, defaults={"plan": plan, "is_active": True}
                )

                if not created:
                    enrollment.plan = plan
                    enrollment.is_active = True
                    enrollment.save()
                    logger.info(
                        f"UPGRADED enrollment via webhook: {enrollment.id}, from FREE to {plan}"
                    )
                else:
                    logger.info(f"Created new enrollment via webhook: {enrollment.id}")

                # Process referral commission
                logger.info(f"Checking for referral commission for user: {user.id}")
                commission_result = process_referral_commission(user, payment.amount)
                if commission_result:
                    logger.info(
                        f"Referral commission processed for payment: {payment.id}"
                    )

            except Payment.DoesNotExist:
                logger.error(f"Payment not found for transaction_id: {transaction_id}")
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")

        return Response(status=200)


class InitiateManualMpesaPayment(APIView):
    """
    Initiates a manual M-Pesa payment process.
    Creates a pending payment and returns payment instructions.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info("=== MANUAL MPESA PAYMENT INITIATION STARTED ===")

        try:
            week_id = request.data.get("week_id")
            plan = request.data.get("plan", "BASIC")

            logger.info(f"Manual M-Pesa request: week_id={week_id}, plan={plan}")

            if not week_id:
                return Response({"error": "Week ID is required"}, status=400)

            try:
                week = Week.objects.get(id=week_id)
                logger.info(f"Week found: {week}")
            except Week.DoesNotExist:
                return Response({"error": "Week not found"}, status=404)

            user = request.user
            logger.info(f"User: {user.id} - {user.email}")

            # Check existing enrollment (same logic as other payment methods)
            existing_enrollment = Enrollment.objects.filter(
                user=user, week=week
            ).first()

            if existing_enrollment:
                if existing_enrollment.plan == "FREE" and plan in ["BASIC", "PRO"]:
                    logger.info(
                        f"Allowing upgrade from FREE to {plan} for week {week.id}"
                    )
                elif existing_enrollment.plan == plan:
                    return Response(
                        {
                            "error": f"You are already enrolled in this week with {plan} plan"
                        },
                        status=400,
                    )
                else:
                    return Response(
                        {
                            "error": f"Cannot change plan from {existing_enrollment.plan} to {plan}"
                        },
                        status=400,
                    )

            # Determine amount
            amount = float(week.price)
            logger.info(f"Amount determined: {amount} for plan {plan}")

            # Create manual payment record
            payment = Payment.objects.create(
                user=user,
                week=week,
                plan=plan,
                amount=amount,
                currency="KES",
                method="manual_mpesa",
                status="pending",
                transaction_id=f"MANUAL_{user.id}_{week.id}_{int(timezone.now().timestamp())}",
            )
            logger.info(f"Manual payment record created: {payment.id}")

            # Payment instructions with YOUR ACTUAL PAYBILL
            paybill_number = "522533"
            account_number = f"WEEK{week.id}"

            instructions = {
                "paybill_number": paybill_number,
                "account_number": account_number,
                "amount": amount,
                "payment_reference": f"WEEK{week.id}",
                "steps": [
                    "1. Go to M-Pesa on your phone",
                    "2. Select Lipa Na M-Pesa",
                    "3. Select Pay Bill",
                    f"4. Enter Business No: {paybill_number}",
                    f"5. Enter Account No: {account_number}",
                    f"6. Enter Amount: {amount}",
                    "7. Enter your M-Pesa PIN",
                    "8. Confirm payment",
                ],
                "note": f" After payment, send the M-Pesa confirmation message to our WhatsApp: +254-791-633441 for quick activation.",
                "whatsapp_contact": "+254-791-633441",
                "payment_id": payment.id,
                "expected_time": "1-2 hours during business hours",
            }

            return Response(
                {
                    "success": True,
                    "message": "Manual payment initiated. Please follow the instructions below.",
                    "payment_id": payment.id,
                    "instructions": instructions,
                    "status": "pending",
                },
                status=200,
            )

        except Exception as e:
            logger.error(
                f"Manual M-Pesa payment initiation failed: {str(e)}", exc_info=True
            )
            return Response(
                {"error": f"Payment initiation failed: {str(e)}"},
                status=400,
            )
