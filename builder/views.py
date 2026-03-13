import json
import logging
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import UserCredits, CreditPackage, CreditPayment, GenerationSession
from .serializers import UserCreditsSerializer, CreditPackageSerializer
from .ai import GroqBuilderClient, GeminiBuilderClient

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
        package_id = request.data.get("package_id")
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
            from payments.services import initiate_stk_push

            # Cast to string explicitly for IDE type checking
            payment_id_str = str(payment.id)
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
            # Also return the user's new credit balance
            try:
                data["credits"] = request.user.ai_credits.credits
            except UserCredits.DoesNotExist:
                data["credits"] = payment.credits
        return Response(data)


class MpesaCreditCallbackView(APIView):
    """
    POST /api/builder/credits/mpesa-callback/
    Called by Safaricom upon payment completion/failure.
    This is AllowAny — no JWT, Safaricom doesn't send auth.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        stk = data.get("Body", {}).get("stkCallback", {})
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
            # Extract receipt number
            items = stk.get("CallbackMetadata", {}).get("Item", [])
            for item in items:
                if item.get("Name") == "MpesaReceiptNumber":
                    payment.mpesa_receipt = str(item.get("Value", ""))

            with transaction.atomic():
                payment.status = "completed"
                payment.completed_at = timezone.now()
                payment.save()

                # Atomically add credits to user's balance
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
                credits_obj.credits -= 1
                credits_obj.total_used += 1
                credits_obj.save()
                return Response({"credits": credits_obj.credits})
        except UserCredits.DoesNotExist:
            return Response(
                {"error": "No credit account found."}, status=status.HTTP_404_NOT_FOUND
            )


class EnhancePromptView(APIView):
    """
    POST /api/builder/enhance-prompt/
    Free feature to enhance user prompts without consuming credits.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get("prompt", "").strip()

        if not prompt:
            return Response(
                {"error": "Prompt is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Simple enhancement logic (can be replaced with AI service later)
        enhanced = self._enhance_prompt_locally(prompt)

        return Response(
            {
                "original_prompt": prompt,
                "enhanced_prompt": enhanced,
                "message": "Prompt enhanced successfully.",
            }
        )

    def _enhance_prompt_locally(self, prompt):
        """Client-side enhancement logic as fallback"""
        enhanced = prompt

        # Add specificity if missing
        prompt_lower = prompt.lower()

        if not any(
            word in prompt_lower for word in ["responsive", "mobile", "devices"]
        ):
            enhanced += "\n\nMake it fully responsive for all devices (mobile, tablet, desktop)."

        if not any(
            word in prompt_lower for word in ["modern", "contemporary", "current"]
        ):
            enhanced += "\n\nUse modern design principles and best practices."

        if not any(word in prompt_lower for word in ["color", "colors", "palette"]):
            enhanced += "\n\nInclude a cohesive color scheme with proper contrast."

        if not any(
            word in prompt_lower for word in ["user experience", "ux", "user-friendly"]
        ):
            enhanced += (
                "\n\nFocus on excellent user experience and intuitive navigation."
            )

        if not any(
            word in prompt_lower for word in ["performance", "fast", "optimized"]
        ):
            enhanced += "\n\nEnsure fast loading and optimal performance."

        return enhanced.strip()


class GenerateView(APIView):
    """POST /api/builder/generate/ — Stream AI generation with Server-Sent Events"""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get('prompt', '').strip()
        output_type = request.data.get('output_type', 'html')
        style_preset = request.data.get('style_preset', '')
        
        # Validate prompt
        if not prompt:
            return Response(
                {'error': 'Prompt is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(prompt) < 10:
            return Response(
                {'error': 'Prompt must be at least 10 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(prompt) > 1000:
            return Response(
                {'error': 'Prompt must be less than 1000 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check credits
        try:
            user_credits = UserCredits.objects.get(user=request.user)
            if user_credits.credits <= 0:
                return Response(
                    {'error': 'NO_CREDITS'},
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )
        except UserCredits.DoesNotExist:
            return Response(
                {'error': 'NO_CREDITS'},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # AI Model Selection
        selected_model = request.data.get('model', 'llama') # Default to llama
        
        # Deduct credit first
        with transaction.atomic():
            UserCredits.objects.filter(user=request.user).update(
                credits=F('credits') - 1,
                total_used=F('total_used') + 1
            )

        # Create session
        session = GenerationSession.objects.create(
            user=request.user,
            prompt=prompt,
            output_type=output_type,
            style_preset=style_preset,
            status='generating',
            credits_used=1
        )

        def stream_response():
            """Stream the generation response from the selected AI model"""
            try:
                
                if selected_model == 'gemini':
                    client = GeminiBuilderClient()
                else:
                    client = GroqBuilderClient()
                
                full_raw_text = ""
                
                # Start initial progress
                yield f'data: {json.dumps({"progress": "Initializing Forge..."})}\n\n'
                
                for chunk in client.stream_generation(prompt):
                    # Check if it's an error from the client
                    if isinstance(chunk, str) and '"error"' in chunk:
                        yield chunk
                        break
                        
                    full_raw_text += chunk
                    # We can't easily parse partial files during stream for now, 
                    # so we just send the raw chunks for the frontend to show.
                    yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                
                # Finalize
                files = client.parse_multi_file_output(full_raw_text)
                model_name = str(selected_model)  # Explicit cast for linting
                explanation = f"Generated using {model_name.capitalize()} based on your prompt."
                
                yield f'data: {json.dumps({"done": True, "files": files, "explanation": explanation, "session_id": str(session.id)})}\n\n'
                
                # Update session
                session.files = files
                session.explanation = explanation
                session.status = 'done'
                session.raw_response = full_raw_text
                session.save()
                
            except Exception as e:
                logger.error(f"Generation error for user {request.user.username}: {e}")
                session.status = 'error'
                session.save()
                
                # Send error response
                yield f'data: {json.dumps({"error": str(e)})}\n\n'

        return Response(
            stream_response(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
            }
        )

    def _get_mock_response(self, prompt, output_type, style_preset):
        """Generate mock response for testing - replace with actual Groq API"""
        if output_type == 'react':
            return {
                "files": [
                    {
                        "name": "App.jsx",
                        "content": f"""import React, {{ useState }} from 'react';

function App() {{
  const [count, setCount] = useState(0);

  return (
    <div style={{{{ 
      padding: '20px', 
      fontFamily: 'Arial, sans-serif',
      textAlign: 'center',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center'
    }}}}>
      <h1 style={{{{ color: '#333', marginBottom: '20px' }}}}>
        {prompt[:50]}...
      </h1>
      <p style={{{{ fontSize: '18px', marginBottom: '20px' }}}}>
        Count: {{count}}
      </p>
      <button 
        onClick={{{{() => setCount(count + 1)}}}}
        style={{{{
          padding: '10px 20px',
          fontSize: '16px',
          backgroundColor: '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer'
        }}}}
      >
        Increment
      </button>
    </div>
  );
}}

export default App;"""
                    },
                    {
                        "name": "style.css",
                        "content": """/* Generated styles */
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
}

* {
  box-sizing: border-box;
}"""
                    }
                ],
                "explanation": f"Created a React component based on: {prompt[:100]}... The component uses useState for interactivity and includes responsive styling."
            }
        else:
            return {
                "files": [
                    {
                        "name": "index.html",
                        "content": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{prompt[:50]}...</title>
</head>
<body>
    <div style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #333;">{prompt[:50]}...</h1>
        <p style="font-size: 18px; color: #666;">Generated website</p>
        <button onclick="alert('Hello!')" style="padding: 10px 20px; font-size: 16px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
            Click Me
        </button>
    </div>
</body>
</html>"""
                    },
                    {
                        "name": "style.css",
                        "content": """/* Generated styles */
body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

* {
    box-sizing: border-box;
}"""
                    },
                    {
                        "name": "script.js",
                        "content": """// Generated JavaScript
console.log('Website loaded!');

// Add some interactivity
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded');
});"""
                    }
                ],
                "explanation": f"Created a responsive HTML page based on: {prompt[:100]}... The page includes semantic HTML5 structure, modern CSS with gradients, and interactive JavaScript."
            }


class SessionListView(APIView):
    """GET /api/builder/sessions/ — List user's generation sessions"""
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = GenerationSession.objects.filter(user=request.user)[:20]  # Last 20 sessions
        from .serializers import GenerationSessionSerializer
        return Response(GenerationSessionSerializer(sessions, many=True).data)


class SessionDetailView(APIView):
    """GET /api/builder/sessions/<id>/ — Get specific session"""
    
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = GenerationSession.objects.get(id=session_id, user=request.user)
            from .serializers import GenerationSessionSerializer
            return Response(GenerationSessionSerializer(session).data)
        except GenerationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DeleteSessionView(APIView):
    """DELETE /api/builder/sessions/<id>/ — Delete a session"""
    
    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id):
        try:
            session = GenerationSession.objects.get(id=session_id, user=request.user)
            session.delete()
            return Response({'success': True})
        except GenerationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
