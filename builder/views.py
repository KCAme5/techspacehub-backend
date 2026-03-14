import json
import logging
from django.db import transaction
from django.db.models import F
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import UserCredits, CreditPackage, CreditPayment, GenerationSession
from .serializers import UserCreditsSerializer, CreditPackageSerializer
from .ai import GroqBuilderClient, GeminiBuilderClient
from .ai.stepfun_client import OpenRouterBuilderClient
from payments.services import initiate_stk_push
from .serializers import GenerationSessionSerializer


logger = logging.getLogger(__name__)


class CreditBalanceView(APIView):
    """GET /api/builder/credits/balance/ — Return the user's current credit balance."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info(f"Fetching credits for user {request.user.username}")

        try:
            credits_obj, created = UserCredits.objects.get_or_create(
                user=request.user,
                defaults={
                    "credits": 20,
                    "total_purchased": 0,
                    "total_used": 0,
                    "is_free_tier": True,
                },
            )

            if created:
                logger.info(
                    f"Created new credits record for {request.user.username} with 20 credits"
                )
            else:
                logger.info(
                    f"Found existing credits for {request.user.username}: {credits_obj.credits} credits"
                )

            serializer_data = UserCreditsSerializer(credits_obj).data
            logger.info(f"Returning credit data: {serializer_data}")

            return Response(serializer_data)

        except Exception as e:
            logger.error(f"Error fetching credits for {request.user.username}: {e}")
            return Response(
                {"error": "Failed to fetch credit balance"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
        package_id   = request.data.get("package_id")
        phone_number = request.data.get("phone_number", "").strip()

        if not package_id or not phone_number:
            return Response(
                {"error": "package_id and phone_number are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        package = get_object_or_404(CreditPackage, id=package_id, is_active=True)

        # Normalize phone: ensure it starts with 2547
        if phone_number.startswith("0"):
            phone_number = "254" + phone_number[1:]
        elif phone_number.startswith("+"):
            phone_number = phone_number[1:]

        # Create pending payment record
        payment = CreditPayment.objects.create(
            user=request.user,
            package=package,
            amount=package.price_kes,
            credits=package.credits,
            phone_number=phone_number,
            status="pending",
        )

        # Initiate M-Pesa STK push
        try:

            payment_id_str    = str(payment.id)
            payment_ref_suffix = payment_id_str[:8].upper()
            result = initiate_stk_push(
                phone=phone_number,
                amount=int(package.price_kes),
                ref=f"CREDITS-{payment_ref_suffix}",
                description=f"TechSpaceHub {package.credits} AI Credits",
            )
            logger.info(f"M-Pesa STK result for payment {payment.id}: {result}")

            if "CheckoutRequestID" in result:
                payment.mpesa_checkout_id = result["CheckoutRequestID"]
                payment.save()
                return Response(
                    {
                        "payment_id": str(payment.id),
                        "message": "STK push sent. Check your phone.",
                    }
                )
            else:
                payment.status = "failed"
                payment.save()
                error_msg = (
                    result.get("errorMessage")
                    or result.get("CustomerMessage")
                    or "M-Pesa initiation failed"
                )
                return Response(
                    {"error": error_msg}, status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"STK push error for payment {payment.id}: {e}")
            payment.status = "failed"
            payment.save()
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class CreditPaymentStatusView(APIView):
    """
    GET /api/builder/credits/payment-status/<payment_id>/
    Frontend polls this every 3 seconds to know if payment succeeded.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(CreditPayment, id=payment_id, user=request.user)
        data = {
            "status": payment.status,
            "credits": 0,
        }
        if payment.status == "completed":
            try:
                data["credits"] = request.user.ai_credits.credits
            except UserCredits.DoesNotExist:
                data["credits"] = payment.credits
        return Response(data)


class MpesaCreditCallbackView(APIView):
    """
    POST /api/builder/credits/mpesa-callback/
    Called by Safaricom upon payment completion/failure.
    AllowAny — Safaricom does not send JWT auth.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        data        = request.data
        stk         = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID", "")
        result_code = str(stk.get("ResultCode", ""))

        logger.info(
            f"M-Pesa Credit Callback: checkout_id={checkout_id}, result_code={result_code}"
        )

        try:
            payment = CreditPayment.objects.get(mpesa_checkout_id=checkout_id)
        except CreditPayment.DoesNotExist:
            logger.warning(f"No CreditPayment found for checkout_id: {checkout_id}")
            return Response({"status": "ignored"})

        if payment.status == "completed":
            # Idempotency — already processed
            return Response({"status": "ok"})

        if result_code == "0":
            items = stk.get("CallbackMetadata", {}).get("Item", [])
            for item in items:
                if item.get("Name") == "MpesaReceiptNumber":
                    payment.mpesa_receipt = str(item.get("Value", ""))

            with transaction.atomic():
                payment.status       = "completed"
                payment.completed_at = timezone.now()
                payment.save()

                user_credits, _ = UserCredits.objects.get_or_create(
                    user=payment.user, defaults={"credits": 0, "is_free_tier": True}
                )
                UserCredits.objects.filter(pk=user_credits.pk).update(
                    credits=F("credits") + payment.credits,
                    total_purchased=F("total_purchased") + payment.credits,
                    is_free_tier=False,
                )
                logger.info(
                    f"Granted {payment.credits} credits to {payment.user.username}"
                )
        else:
            payment.status = "failed"
            payment.save()
            logger.warning(
                f"M-Pesa payment failed for {payment.user.username}: {stk.get('ResultDesc', '')}"
            )

        return Response({"status": "ok"})


class DeductCreditView(APIView):
    """
    POST /api/builder/credits/deduct/
    Called internally after a successful AI generation to record credit usage.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            with transaction.atomic():
                credits_obj = UserCredits.objects.select_for_update().get(
                    user=request.user
                )
                if credits_obj.credits <= 0:
                    return Response(
                        {"error": "Not enough credits."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                credits_obj.credits    -= 1
                credits_obj.total_used += 1
                credits_obj.save()
                return Response({"credits": credits_obj.credits})
        except UserCredits.DoesNotExist:
            return Response(
                {"error": "No credit account found."},
                status=status.HTTP_404_NOT_FOUND
            )


class EnhancePromptView(APIView):
    """
    POST /api/builder/enhance-prompt/
    Uses AI to rewrite and improve the user's prompt.
    Free — does not consume credits.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get("prompt", "").strip()

        if not prompt:
            return Response(
                {"error": "Prompt is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = GroqBuilderClient(model='llama')
            enhanced = self._ai_enhance(client, prompt)
            return Response({
                "original_prompt": prompt,
                "enhanced_prompt": enhanced,
                "message": "Prompt enhanced successfully.",
            })
        except Exception as e:
            logger.error(f"Enhance prompt error: {e}")
            # Fallback to local enhancement if AI fails
            return Response({
                "original_prompt": prompt,
                "enhanced_prompt": self._local_enhance(prompt),
                "message": "Prompt enhanced.",
            })

    def _ai_enhance(self, client, prompt: str) -> str:
        """Use Groq to rewrite the prompt into a detailed, specific instruction."""
        if not client.client:
            logger.warning("Enhance: Groq client not initialized, using local fallback")
            return self._local_enhance(prompt)

        system = (
            "You are a prompt engineer for an AI website builder. "
            "Rewrite the user's prompt into a detailed, specific build instruction. "
            "Include: exact sections needed, realistic content (real product names/prices if relevant), "
            "color scheme, image suggestions using picsum.photos URLs, interactive features. "
            "Return ONLY the rewritten prompt. No explanation. No preamble. Just the improved prompt text."
        )

        try:
            response = client.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": f"Enhance this website prompt: {prompt}"},
                ],
                model=client.model,
                temperature=0.6,
                max_tokens=600,
                stream=False,
            )
            result = response.choices[0].message.content.strip()
            logger.info(f"Prompt enhanced successfully: {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"AI enhance failed, using local fallback: {e}")
            return self._local_enhance(prompt)

    def _local_enhance(self, prompt: str) -> str:
        """Fallback enhancement without AI."""
        enhanced     = prompt
        prompt_lower = prompt.lower()

        if not any(w in prompt_lower for w in ["responsive", "mobile"]):
            enhanced += "\n\nMust be fully responsive for mobile, tablet, and desktop."
        if not any(w in prompt_lower for w in ["color", "colors", "theme"]):
            enhanced += "\n\nUse a modern, cohesive color scheme with high contrast."
        if not any(w in prompt_lower for w in ["navigation", "navbar", "menu"]):
            enhanced += "\n\nInclude a clean navigation bar with smooth scroll to sections."
        if not any(w in prompt_lower for w in ["image", "photo", "visual"]):
            enhanced += "\n\nInclude relevant images using real Unsplash photo URLs."

        return enhanced.strip()


class GenerateView(APIView):
    """POST /api/builder/generate/ — Stream AI generation via Server-Sent Events."""

    permission_classes = [IsAuthenticated]

    def post(self, request):

        prompt         = request.data.get('prompt', '').strip()
        output_type    = request.data.get('output_type', 'html')
        style_preset   = request.data.get('style_preset', '')
        selected_model = request.data.get('model', 'llama')

        # ── Validation ────────────────────────────────────────────────────────
        if not prompt:
            return Response({'error': 'Prompt is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(prompt) < 10:
            return Response({'error': 'Prompt must be at least 10 characters'},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(prompt) > 5000:
            return Response({'error': 'Prompt must be less than 5000 characters'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ── Credit check ──────────────────────────────────────────────────────
        try:
            user_credits = UserCredits.objects.get(user=request.user)
            if user_credits.credits <= 0:
                return Response({'error': 'NO_CREDITS'},
                                status=status.HTTP_402_PAYMENT_REQUIRED)
        except UserCredits.DoesNotExist:
            return Response({'error': 'NO_CREDITS'},
                            status=status.HTTP_402_PAYMENT_REQUIRED)

        # ── Deduct 1 credit atomically before generation starts ───────────────
        with transaction.atomic():
            UserCredits.objects.filter(user=request.user).update(
                credits=F('credits') - 1,
                total_used=F('total_used') + 1
            )

        # ── Existing files — edit mode ────────────────────────────────────────
        # Frontend sends current files when user is editing an existing project
        existing_files = request.data.get('existing_files', None)

        # ── Create session record ─────────────────────────────────────────────
        session = GenerationSession.objects.create(
            user=request.user,
            prompt=prompt,
            output_type=output_type,
            style_preset=style_preset,
            status='generating',
            credits_used=1,
        )

        # ── SSE generator ─────────────────────────────────────────────────────
        def stream_response():
            try:
                if selected_model == 'gemini':
                    client = GeminiBuilderClient()

                elif selected_model == 'stepfun':
                    client = OpenRouterBuilderClient()
                else:
                    client = GroqBuilderClient(model=selected_model)

                full_raw_text = ""

                for sse_line in client.stream_generation(
                    prompt,
                    existing_files=existing_files,
                    output_type=output_type,
                ):

                    # Accumulate raw text from chunk events so we can save
                    # the full response to the session after streaming ends.
                    try:
                        if sse_line.startswith("data: "):
                            payload = json.loads(sse_line[6:].strip())
                            if "chunk" in payload:
                                full_raw_text += payload["chunk"]
                    except Exception:
                        pass  # progress / done / error lines — not chunks

                    # Send the SSE line to the browser as-is
                    yield sse_line

                # ── Persist completed session to DB ───────────────────────────
                try:
                    files = client.parse_multi_file_output(full_raw_text)
                    session.files        = files
                    session.raw_response = full_raw_text
                    session.explanation  = f"Generated using {selected_model.capitalize()}."
                    session.status       = 'done'
                    session.save()
                except Exception as save_err:
                    logger.error(f"Session save error: {save_err}")

            except Exception as e:
                logger.error(
                    f"Generation error for {request.user.username}: {e}"
                )
                session.status = 'error'
                session.save()
                yield f'data: {json.dumps({"error": str(e)})}\n\n'

        # ── StreamingHttpResponse — sends each yield immediately ──────────────
        # DO NOT use DRF Response() here — it buffers the entire generator
        # before sending, which completely breaks SSE streaming.
        response = StreamingHttpResponse(
            stream_response(),
            content_type='text/event-stream',
        )
        response['Cache-Control']               = 'no-cache'
        response['X-Accel-Buffering']           = 'no'  # disables Nginx buffering
        response['Access-Control-Allow-Origin'] = '*'
        return response


class SessionListView(APIView):
    """GET /api/builder/sessions/ — List user's last 20 generation sessions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = GenerationSession.objects.filter(user=request.user)[:20]
        return Response(GenerationSessionSerializer(sessions, many=True).data)


class SessionDetailView(APIView):
    """GET /api/builder/sessions/<id>/ — Get a specific session."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = GenerationSession.objects.get(
                id=session_id, user=request.user
            )
            return Response(GenerationSessionSerializer(session).data)
        except GenerationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DeleteSessionView(APIView):
    """DELETE /api/builder/sessions/<id>/ — Delete a session."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id):
        try:
            session = GenerationSession.objects.get(
                id=session_id, user=request.user
            )
            session.delete()
            return Response({'success': True})
        except GenerationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )