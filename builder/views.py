# builder/views.py
import json
import logging
import io
import zipfile
import base64
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
from .services.daytona_runner import DaytonaRunner
from payments.services import initiate_stk_push
from .serializers import GenerationSessionSerializer
import requests as ext_requests
from urllib.parse import urlparse
from django.http import HttpResponse

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
            items = stk.get("CallbackMetadata", {}).get("Item", [])
            for item in items:
                if item.get("Name") == "MpesaReceiptNumber":
                    payment.mpesa_receipt = str(item.get("Value", ""))

            with transaction.atomic():
                payment.status = "completed"
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
            client = GroqBuilderClient(model="llama")
            enhanced = self._ai_enhance(client, prompt)
            return Response(
                {
                    "original_prompt": prompt,
                    "enhanced_prompt": enhanced,
                    "message": "Prompt enhanced successfully.",
                }
            )
        except Exception as e:
            logger.error(f"Enhance prompt error: {e}")
            # Fallback to local enhancement if AI fails
            return Response(
                {
                    "original_prompt": prompt,
                    "enhanced_prompt": self._local_enhance(prompt),
                    "message": "Prompt enhanced.",
                }
            )

    def _ai_enhance(self, client, prompt: str) -> str:
        """Use Groq to rewrite the prompt into a detailed, specific instruction."""
        if not client.client:
            logger.warning("Enhance: Groq client not initialized, using local fallback")
            return self._local_enhance(prompt)

        system = (
            "You are a Senior Technical Product Manager & UI/UX Designer at a world-class digital agency. "
            "Your goal is to transform a simple user request into a DETAILED, HIGH-FIDELITY technical specification for an AI coder. "
            "\n\nFOLLOW THESE CORE PRINCIPLES:"
            "\n1. DEPTH: Break the request into at least 4-6 specialized, high-converting sections."
            "\n2. AESTHETICS: Define a sophisticated, premium color palette (using HEX codes) and a modern typography style."
            "\n3. IMAGES: STOP using generic placeholders or picsum URLs. Instead, describe high-quality professional photography keywords "
            "that the builder can map to Unsplash IDs (e.g., 'A professional, high-resolution shot of a minimalist office with warm lighting')."
            "\n4. CONTENT: Write REAL, compelling marketing copy. Do not use 'Lorem Ipsum'. Create specific service names, prices, and features."
            "\n5. INTERACTIVITY: Include specific modern features like Glassmorphism, Framer Motion hover effects, smooth scroll, and dark-mode transitions."
            "\n6. COMPONENT ARCHITECTURE: Suggest specific React components or layout structures if relevant."
            "\n\nReturn ONLY the rewritten prompt. No explanation. No preamble. No markdown blocks. Just the improved, professional prompt text."
        )

        try:
            response = client.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": f"Enhance this website prompt: {prompt}",
                    },
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
        """Robust fallback enhancement without AI side-effects."""
        enhanced = prompt
        prompt_lower = prompt.lower()

        extra_specs = []

        if not any(w in prompt_lower for w in ["responsive", "mobile", "device"]):
            extra_specs.append(
                "Ensure the layout is fully responsive, looking pixel-perfect on mobile (iPhone 14), tablet (iPad Pro), and 4k desktops."
            )

        if not any(
            w in prompt_lower for w in ["color", "colors", "theme", "aesthetic"]
        ):
            extra_specs.append(
                "Use a premium, cohesive color palette with deep backgrounds (#0D1214), high-contrast accents (#48CAE4), and soft readability levels."
            )

        if not any(
            w in prompt_lower for w in ["navigation", "navbar", "menu", "header"]
        ):
            extra_specs.append(
                "Include a sticky, glassmorphism-style navigation bar with smooth-scroll links and a prominent Call-to-Action button."
            )

        if not any(
            w in prompt_lower for w in ["image", "photo", "visual", "photography"]
        ):
            extra_specs.append(
                "Use high-quality, professional photography from the Unsplash library. Avoid generic placeholders or picsum photos."
            )

        if not any(w in prompt_lower for w in ["modern", "animation", "motion", "ui"]):
            extra_specs.append(
                "Implement subtle micro-animations (fade-ins, hover lifts) and modern UI elements like cards with soft shadows and glassmorphism overlays."
            )

        if extra_specs:
            enhanced += "\n\nADDITIONAL TECHNICAL SPECIFICATIONS:\n- " + "\n- ".join(
                extra_specs
            )

        return enhanced.strip()


class GenerateView(APIView):
    """POST /api/builder/generate/ - Stream AI generation via SSE."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get("prompt", "").strip()
        output_type = request.data.get("output_type", "react")
        style_preset = request.data.get("style_preset", "")
        selected_model = request.data.get("model", "trinity")
        existing_files = request.data.get("existing_files", None)

        # Validation
        if not prompt:
            return Response(
                {"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Credit check
        try:
            with transaction.atomic():
                user_credits = UserCredits.objects.select_for_update().get(
                    user=request.user
                )
                if user_credits.credits <= 0:
                    return Response(
                        {"error": "NO_CREDITS"}, status=status.HTTP_402_PAYMENT_REQUIRED
                    )
                user_credits.credits -= 1
                user_credits.total_used += 1
                user_credits.save()
        except UserCredits.DoesNotExist:
            return Response(
                {"error": "NO_CREDITS"}, status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # Create session
        session = GenerationSession.objects.create(
            user=request.user,
            prompt=prompt,
            output_type=output_type,
            style_preset=style_preset,
            status="generating",
            credits_used=1,
        )

        # Model mapping
        model_map = {
            "trinity": "arcee-ai/trinity-large-preview:free",
            "gpt-oss": "openai/gpt-oss-120b:free",
            "nemotron": "nvidia/nemotron-3-super-120b-a12b:free",
            "stepfun": "stepfun/step-3.5-flash",
            "glm": "z-ai/glm-4.5-air:free",
            "hunter": "openrouter/hunter-alpha",
            "healer": "openrouter/healer-alpha",
            "minimax": "minimax/minimax-m2.5:free",
        }
        model_name = model_map.get(selected_model, model_map["trinity"])

        def stream_response():
            """Generator yielding SSE events immediately."""
            full_raw_text = ""
            client = None

            try:
                client = OpenRouterBuilderClient(model=model_name)
                current_prompt = prompt
                max_attempts = 3
                
                for attempt in range(1, max_attempts + 1):
                    full_raw_text = ""
                    last_files = []
                    
                    # 1. Stream from AI
                    for sse_event in client.stream_generation(
                        current_prompt,
                        existing_files=existing_files,
                        output_type=output_type,
                        suppress_done=True,
                    ):
                        yield sse_event
                        
                        # Accumulate for validation and session save
                        try:
                            if sse_event.startswith("data: "):
                                payload = json.loads(sse_event[6:].strip())
                                if "chunk" in payload:
                                    full_raw_text += payload["chunk"]
                                if "thinking" in payload:
                                    full_raw_text += payload["thinking"]
                                if "files" in payload:
                                    last_files = payload["files"]
                        except:
                            pass

                    # If no files were parsed, we can't validate; stop here
                    if not last_files:
                        break

                    # 2. Build Test in Daytona
                    yield f'data: {json.dumps({"progress": "Verifying code in Daytona sandbox..."})}\n\n'
                    
                    runner = DaytonaRunner()
                    success, logs = runner.run_build_test(last_files)
                    
                    if success:
                        yield f'data: {json.dumps({"progress": "Build successful! ✨"})}\n\n'
                        break
                    else:
                        if attempt < max_attempts:
                            yield f'data: {json.dumps({"progress": f"Build failed. Self-healing (Attempt {attempt}/{max_attempts})..."})}\n\n'
                            logger.warning(f"Self-healing {attempt} started due to build errors: {logs[:200]}...")
                            
                            # Update prompt for next attempt
                            current_prompt = (
                                f"The previous code had build errors. Please fix them.\n"
                                f"ERROR LOGS:\n{logs}\n\n"
                                f"Provide the COMPLETE corrected file set starting from the beginning."
                            )
                        else:
                            yield f'data: {json.dumps({"progress": "Build failed after max attempts. Returning best effort."})}\n\n'
                            logger.error(f"Self-healing failed after {max_attempts} attempts.")

                # Finalize session
                try:
                    explanation = client.extract_description(full_raw_text)
                    session.files = last_files
                    session.raw_response = full_raw_text
                    session.explanation = explanation
                    session.status = "done"
                    session.save()

                    # Yield final done event to frontend
                    yield f'data: {json.dumps({"done": True, "files": last_files, "explanation": explanation})}\n\n'
                except Exception as save_err:
                    logger.error(f"Session save error: {save_err}")

            except Exception as e:
                logger.error(f"Generation error: {e}")
                session.status = "error"
                session.save()

                # Restore credits
                try:
                    UserCredits.objects.filter(user=request.user).update(
                        credits=F("credits") + 1, total_used=F("total_used") - 1
                    )
                except Exception as rollback_err:
                    logger.error(f"Credit restore failed: {rollback_err}")

                yield f'data: {json.dumps({"error": str(e)})}\n\n'

        # CRITICAL: Headers to prevent any buffering
        response = StreamingHttpResponse(
            stream_response(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["X-Accel-Buffering"] = "no"
        response["Content-Encoding"] = "identity"
        response["Connection"] = "keep-alive"

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
            session = GenerationSession.objects.get(id=session_id, user=request.user)
            return Response(GenerationSessionSerializer(session).data)
        except GenerationSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )


class DeleteSessionView(APIView):
    """DELETE /api/builder/sessions/<id>/ — Delete a session."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id):
        try:
            session = GenerationSession.objects.get(id=session_id, user=request.user)
            session.delete()
            return Response({"success": True})
        except GenerationSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )


class ImageProxyView(APIView):
    """
    GET /api/builder/proxy/image/?url=https://loremflickr.com/...
    Proxies external images through your server so sandboxed iframes
    can load them (null-origin CORS restriction bypass).
    AllowAny — no auth needed, images are public.
    """

    permission_classes = [AllowAny]

    # Allowlist of domains the proxy will fetch from
    # Prevents your server being used as an open proxy
    ALLOWED_DOMAINS = {
        "loremflickr.com",
        "picsum.photos",
        "images.unsplash.com",
        "source.unsplash.com",
        "live.staticflickr.com",  # loremflickr pulls from Flickr CDN
        "farm1.staticflickr.com",
        "farm2.staticflickr.com",
        "farm3.staticflickr.com",
        "farm4.staticflickr.com",
        "farm5.staticflickr.com",
        "farm6.staticflickr.com",
        "farm7.staticflickr.com",
        "farm8.staticflickr.com",
        "farm9.staticflickr.com",
        "c1.staticflickr.com",
        "c2.staticflickr.com",
        "c3.staticflickr.com",
        "c4.staticflickr.com",
        "c5.staticflickr.com",
        "c6.staticflickr.com",
        "c7.staticflickr.com",
        "c8.staticflickr.com",
    }

    def get(self, request):

        url = request.query_params.get("url", "").strip()
        logger.info(f"ImageProxy: Requested URL: {url}")

        if not url:
            logger.warning("ImageProxy: No URL provided")
            return HttpResponse(status=400)

        # Security: only allow https
        if not url.startswith("https://"):
            logger.warning(f"ImageProxy: Non-HTTPS URL blocked: {url}")
            return HttpResponse(status=403)

        # Security: only allow known image domains (improved validation)
        # Use proper domain extraction to prevent subdomain attacks
        try:
            from tldextract import tldextract

            extracted = tldextract.extract(url)
            # Get the registered domain (e.g., "unsplash.com" from "images.unsplash.com")
            registered_domain = extracted.registered_domain

            # Check if the registered domain is in our allowed list
            allowed = False
            for allowed_domain in self.ALLOWED_DOMAINS:
                # Exact match or subdomain of an allowed domain
                if registered_domain == allowed_domain or registered_domain.endswith(
                    "." + allowed_domain
                ):
                    allowed = True
                    break

            if not allowed:
                logger.warning(
                    f"ImageProxy: Domain blocked: {registered_domain} for URL: {url}"
                )
                return HttpResponse(status=403)

        except ImportError:
            # Fallback: use basic urlparse (less secure but works without tldextract)
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix for comparison
            if domain.startswith("www."):
                domain = domain[4:]

            # Check exact domain match or subdomain
            allowed = False
            for allowed_domain in self.ALLOWED_DOMAINS:
                if domain == allowed_domain or domain.endswith("." + allowed_domain):
                    allowed = True
                    break

            if not allowed:
                logger.warning(f"ImageProxy: Domain blocked: {domain} for URL: {url}")
                return HttpResponse(status=403)

        try:
            resp = ext_requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "image/*,*/*",
                },
                allow_redirects=True,
            )

            logger.info(
                f"ImageProxy: Unsplash/External response status: {resp.status_code} for {url}"
            )

            if resp.status_code != 200:
                return HttpResponse(status=resp.status_code)

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            logger.info(f"ImageProxy: Content-Type: {content_type}")

            # Only serve actual images
            if not content_type.startswith("image/"):
                logger.warning(
                    f"ImageProxy: Non-image content type blocked: {content_type}"
                )
                return HttpResponse(status=403)

            response = HttpResponse(resp.content, content_type=content_type)
            response["Cache-Control"] = "public, max-age=3600"
            response["Access-Control-Allow-Origin"] = "*"
            return response

        except ext_requests.exceptions.Timeout:
            logger.error(f"ImageProxy: Timeout fetching {url}")
            return HttpResponse(status=504)
        except Exception as e:
            logger.error(f"ImageProxy: Error fetching {url}: {str(e)}")
            return HttpResponse(status=502)


def get_boilerplate_files(output_type, project_name="my-website"):
    """Returns a list of boilerplate files needed to run the project locally."""
    boilerplate = []

    if output_type == "react":
        # package.json
        package_json = {
            "name": project_name.lower().replace(" ", "-"),
            "private": True,
            "version": "0.1.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "lucide-react": "^0.263.1",
                "framer-motion": "^10.12.16",
                "react-icons": "^4.11.0",
                "clsx": "^2.0.0",
                "tailwind-merge": "^2.0.0",
            },
            "devDependencies": {
                "@types/react": "^18.2.15",
                "@types/react-dom": "^18.2.7",
                "@vitejs/plugin-react": "^4.0.3",
                "autoprefixer": "^10.4.14",
                "postcss": "^8.4.27",
                "tailwindcss": "^3.3.3",
                "vite": "^4.4.5",
            },
        }
        boilerplate.append(
            {"name": "package.json", "content": json.dumps(package_json, indent=2)}
        )

        # vite.config.js
        vite_config = "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n\nexport default defineConfig({\n  plugins: [react()],\n})"
        boilerplate.append({"name": "vite.config.js", "content": vite_config})

        # tailwind.config.js
        tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}"""
        boilerplate.append({"name": "tailwind.config.js", "content": tailwind_config})

        # postcss.config.js
        postcss_config = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}"""
        boilerplate.append({"name": "postcss.config.js", "content": postcss_config})

        # index.html (root)
        index_html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>"""
        boilerplate.append({"name": "index.html", "content": index_html})

        # src/main.jsx (Entry Point)
        main_jsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)"""
        boilerplate.append({"name": "src/main.jsx", "content": main_jsx})

        # README.md
        readme = f"""# {project_name}

This project was generated by TechSpace AI Website Builder.

## Local Setup
1. Unzip the files into a folder.
2. Open a terminal in that folder.
3. Run `npm install` to install dependencies.
4. Run `npm run dev` to start the local development server.
5. Open the provided local URL (usually http://localhost:5173).
"""
        boilerplate.append({"name": "README.md", "content": readme})

    else:
        # Static HTML README.md
        readme = f"""# {project_name}

This project was generated by TechSpace AI Website Builder.

## How to View
1. Open the folder.
2. Double-click `index.html` to view the website in your browser.
"""
        boilerplate.append({"name": "README.md", "content": readme})

    return boilerplate


class DownloadZipView(APIView):
    """
    GET /api/builder/sessions/<id>/download/
    Generates a ZIP archive of the session files and serves it for download.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        from .services.image_utils import restore_files

        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        # 1. Restore original image URLs (proxy removal)
        clean_files = restore_files(session.files)

        # 2. Inject boilerplate files
        boilerplate = get_boilerplate_files(session.output_type, session.project_name)

        # Filter out boilerplate files that might already exist in session
        existing_names = {f["name"] for f in clean_files}
        final_files = clean_files + [
            b for b in boilerplate if b["name"] not in existing_names
        ]

        # 3. Create ZIP
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in final_files:
                zip_file.writestr(file_data["name"], file_data["content"])

        buffer.seek(0)
        filename = f"{session.project_name.replace(' ', '_')}.zip"
        response = HttpResponse(buffer.read(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PushToGithubView(APIView):
    """
    POST /api/builder/sessions/<id>/push-to-github/
    Pushes session files to a GitHub repository.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        from .services.image_utils import restore_files
        import requests as req

        github_token = request.data.get("github_token")
        repo_name = request.data.get("repo_name", "my-website")

        if not github_token:
            return Response(
                {"error": "GitHub token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        # 1. Restore original image URLs
        clean_files = restore_files(session.files)

        # 2. Inject boilerplate
        boilerplate = get_boilerplate_files(session.output_type, session.project_name)
        existing_names = {f["name"] for f in clean_files}
        final_files = clean_files + [
            b for b in boilerplate if b["name"] not in existing_names
        ]

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # 1. Get username and validate token scopes
        try:
            user_resp = req.get("https://api.github.com/user", headers=headers)
            if user_resp.status_code != 200:
                return Response(
                    {"error": "Invalid GitHub token or authentication failed."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            user_data = user_resp.json()
            username = user_data["login"]

            # Check token scopes - need 'repo' scope for full write access
            scopes = user_resp.headers.get("X-OAuth-Scopes", "").split(", ")
            if "repo" not in scopes:
                # Also check for token type - classic tokens have scopes, fine-grained have different structure
                # For now, warn but allow if no clear scope info
                logger.warning(f"GitHub token may lack repo scope. Scopes: {scopes}")
        except Exception as e:
            return Response(
                {"error": f"Failed to connect to GitHub: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 2. Create repository (ignore if already exists)
        req.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={"name": repo_name, "auto_init": False},
        )

        # 3. Push files
        try:
            for file in final_files:
                path = file["name"]
                content_b64 = base64.b64encode(file["content"].encode()).decode()

                # GitHub API requires the SHA of the file if it already exists for updates
                file_url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{path}"
                get_resp = req.get(file_url, headers=headers)
                sha = (
                    get_resp.json().get("sha") if get_resp.status_code == 200 else None
                )

                put_data = {
                    "message": f"Add {path} via AI Builder",
                    "content": content_b64,
                }
                if sha:
                    put_data["sha"] = sha

                req.put(file_url, headers=headers, json=put_data)

            return Response({"repo_url": f"https://github.com/{username}/{repo_name}"})
        except Exception as e:
            return Response(
                {"error": f"Failed to push files to GitHub: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatView(APIView):
    """
    POST /api/builder/sessions/<id>/chat/
    Continue a conversation with context - the agentic workflow.
    This allows users to iteratively edit their generated website
    by providing follow-up instructions that the AI understands
    in the context of the previous generations.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """Continue conversation with context."""
        user_message = request.data.get("message", "").strip()
        
        if not user_message:
            return Response(
                {"error": "Message is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the existing session
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        
        # Get conversation history
        conversation = session.conversation or []
        
        # Add user message to conversation
        conversation.append({
            "role": "user",
            "content": user_message,
            "timestamp": timezone.now().isoformat()
        })

        # Credit check - for follow-up generations
        try:
            with transaction.atomic():
                user_credits = UserCredits.objects.select_for_update().get(
                    user=request.user
                )
                if user_credits.credits <= 0:
                    return Response(
                        {"error": "NO_CREDITS"},
                        status=status.HTTP_402_PAYMENT_REQUIRED
                    )
                user_credits.credits -= 1
                user_credits.total_used += 1
                user_credits.save()
        except UserCredits.DoesNotExist:
            return Response(
                {"error": "NO_CREDITS"},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # Build context for AI
        existing_files = session.files
        output_type = session.output_type
        
        # Model selection (use same as original session)
        model_map = {
            "trinity": "arcee-ai/trinity-large-preview:free",
            "gpt-oss": "openai/gpt-oss-120b:free",
            "nemotron": "nvidia/nemotron-3-super-120b-a12b:free",
            "stepfun": "stepfun/step-3.5-flash",
            "glm": "z-ai/glm-4.5-air:free",
            "hunter": "openrouter/hunter-alpha",
            "healer": "openrouter/healer-alpha",
            "minimax": "minimax/minimax-m2.5:free",
        }
        model_name = model_map.get("trinity", model_map["trinity"])

        def stream_response():
            """Stream chat response with context awareness."""
            full_raw_text = ""
            
            try:
                client = OpenRouterBuilderClient(model=model_name)
                
                # Build a context-aware prompt that includes previous conversation
                context_prompt = self._build_context_prompt(
                    user_message, 
                    conversation[:-1],  # Previous messages only
                    existing_files,
                    output_type
                )
                
                yield f"data: {json.dumps({'progress': 'Thinking with context...'})}\n\n"
                
                for sse_event in client.stream_generation(
                    context_prompt,
                    existing_files=existing_files,
                    output_type=output_type,
                ):
                    yield sse_event
                    
                    # Accumulate for session save
                    try:
                        if sse_event.startswith("data: "):
                            payload = json.loads(sse_event[6:].strip())
                            if "chunk" in payload:
                                full_raw_text += payload["chunk"]
                            if "thinking" in payload:
                                full_raw_text += payload["thinking"]
                    except:
                        pass
                
                # Save updated conversation
                try:
                    files = client.parse_multi_file_output(full_raw_text)
                    
                    # Add assistant response to conversation
                    explanation = client.extract_description(full_raw_text)
                    conversation.append({
                        "role": "assistant",
                        "content": explanation or "Updated the website based on your feedback.",
                        "files": files,
                        "timestamp": timezone.now().isoformat()
                    })
                    
                    # Update session with new files and conversation
                    if files:
                        # Merge with existing files
                        merged_files = {f["name"]: f["content"] for f in existing_files}
                        for f in files:
                            merged_files[f["name"]] = f["content"]
                        session.files = [{"name": k, "content": v} for k, v in merged_files.items()]
                    
                    session.conversation = conversation
                    session.raw_response = full_raw_text
                    session.explanation = explanation
                    session.credits_used += 1
                    session.status = "done"
                    session.save()
                    
                    yield f"data: {json.dumps({'done': True, 'conversation': conversation})}\n\n"
                    
                except Exception as save_err:
                    logger.error(f"Chat session save error: {save_err}")
                    
            except Exception as e:
                logger.error(f"Chat generation error: {e}")
                session.status = "error"
                session.save()
                
                # Restore credits
                try:
                    UserCredits.objects.filter(user=request.user).update(
                        credits=F("credits") + 1,
                        total_used=F("total_used") - 1
                    )
                except Exception as rollback_err:
                    logger.error(f"Credit restore failed: {rollback_err}")
                
                yield f'data: {json.dumps({"error": str(e)})}\n\n'

        # Streaming response
        response = StreamingHttpResponse(
            stream_response(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["X-Accel-Buffering"] = "no"
        response["Content-Encoding"] = "identity"
        response["Connection"] = "keep-alive"
        
        return response

    def _build_context_prompt(self, user_message, conversation_history, existing_files, output_type):
        """
        Build a context-aware prompt that includes previous conversation.
        This helps the AI understand the full context of edits.
        """
        context_parts = []
        
        # Add conversation history as context
        if conversation_history:
            context_parts.append("CONVERSATION HISTORY:")
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_parts.append(f"{role.upper()}: {content}")
            context_parts.append("")
        
        # Current files context
        if existing_files:
            context_parts.append("CURRENT PROJECT FILES:")
            for f in existing_files[:10]:  # First 10 files
                context_parts.append(f"--- {f.get('name', 'unknown')} ---")
                # Include first 500 chars of each file as context
                content = f.get("content", "")[:500]
                context_parts.append(content)
                context_parts.append("")
        
        # Current user request
        context_parts.append(f"USER REQUEST: {user_message}")
        context_parts.append("")
        context_parts.append(
            "Based on the conversation history and current files above, "
            "make the requested changes. Preserve working code that doesn't need to change. "
            "Return only the files that were modified using the --- filename --- format."
        )
        
        return "\n".join(context_parts)


class FixErrorsView(APIView):
    """
    POST /api/builder/fix-errors/
    
    Self-healing endpoint: receives errors from frontend preview,
    sends them to AI for fixing, returns corrected code.
    
    This is FREE - doesn't charge credits for fix attempts.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        errors = request.data.get('errors', [])
        files = request.data.get('files', [])
        prompt = request.data.get('prompt', '')
        attempt = request.data.get('attempt', 1)

        if not errors:
            return Response(
                {'error': 'No errors provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not files:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"FixErrors attempt {attempt}: {len(errors)} errors received")

        # Build error context for AI
        error_context = self._build_error_context(errors)

        # Build fix prompt
        fix_prompt = self._build_fix_prompt(prompt, files, error_context, attempt)

        try:
            # Use Groq for AI fixing - more reliable than OpenRouter
            from .ai.groq_client import GroqBuilderClient
            client = GroqBuilderClient(model="llama")
            
            if not client.client:
                return Response(
                    {'error': 'Groq API not configured. Set LLAMA_API_KEY.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Get the output type from files
            output_type = 'react' if any(f.get('name', '').endswith(('.jsx', '.tsx')) for f in files) else 'html'

            # Generate fixed code using Groq
            full_response = ""
            for chunk in client.stream_generation(
                fix_prompt,
                existing_files=files,
                output_type=output_type
            ):
                try:
                    if chunk.startswith('data: '):
                        data = json.loads(chunk[6:])
                        if 'chunk' in data:
                            full_response += data['chunk']
                        if 'thinking' in data:
                            full_response += data['thinking']
                except:
                    pass

            # Parse the response
            fixed_files = client.parse_multi_file_output(full_response)

            if not fixed_files:
                return Response(
                    {'error': 'Failed to generate fixed code', 'details': 'AI returned empty response'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            logger.info(f"FixErrors success: Generated {len(fixed_files)} fixed files")

            return Response({
                'files': fixed_files,
                'success': True,
                'attempt': attempt,
                'message': f'Fixed {len(errors)} errors on attempt {attempt}'
            })

        except Exception as e:
            logger.error(f"FixErrors error: {e}")
            return Response(
                {'error': str(e), 'success': False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_error_context(self, errors):
        """Build a readable error context for the AI."""
        error_lines = []
        
        for i, err in enumerate(errors, 1):
            level = err.get('level', 'error')
            message = err.get('message', 'Unknown error')
            line = err.get('line', '')
            stack = err.get('stack', '')
            
            error_lines.append(f"{i}. [{level.upper()}] {message}")
            if line:
                error_lines.append(f"   Line: {line}")
            if stack:
                # Truncate stack trace
                error_lines.append(f"   Stack: {stack[:200]}...")
        
        return "\n".join(error_lines)

    def _build_fix_prompt(self, original_prompt, files, error_context, attempt):
        """Build a prompt that instructs the AI to fix errors."""
        
        # List current files
        file_list = "\n".join([f"- {f.get('name', 'unknown')}" for f in files])
        
        prompt = f"""
You are an expert React/JavaScript developer fixing errors in generated code.

ORIGINAL USER PROMPT:
{original_prompt}

CURRENT FILES:
{file_list}

ERRORS TO FIX (Attempt {attempt}):
{error_context}

INSTRUCTIONS:
1. Analyze each error carefully
2. Fix all syntax errors, missing imports, undefined variables, and component errors
3. Ensure the code is valid JavaScript/React that will render without errors
4. Return ONLY the corrected files using this format:

--- filename.jsx ---
// corrected code here
--- filename.css ---
/* corrected code here */

Focus on making the code work. Do NOT change functionality unless necessary to fix errors.
"""
        return prompt
