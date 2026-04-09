# builder/views.py
import json
import logging
import io
import zipfile
import base64
import re
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
from .services.credit_service import get_or_create_credits
from .services.prompt_validator import get_prompt_validator
from .services.error_extractor import get_error_extractor
from .services.error_fixer import get_error_fixer
from .services.runtime_provider import get_runtime_provider
from .ai import GroqBuilderClient, GeminiBuilderClient
from .ai.stepfun_client import OpenRouterBuilderClient

from payments.services import initiate_stk_push
from .serializers import GenerationSessionSerializer, CreditPackageSerializer
import requests as ext_requests
from urllib.parse import urlparse
from django.http import HttpResponse

logger = logging.getLogger(__name__)


BUILDER_MODEL_MAP = {
    "stepfun": "stepfun/step-3.5-flash:free",
    "trinity": "arcee-ai/trinity-large-preview:free",
    "gpt-oss": "openai/gpt-oss-120b:free",
    "nemotron": "nvidia/nemotron-3-super-120b-a12b:free",
    "glm": "z-ai/glm-4.5-air:free",
    "minimax": "minimax/minimax-m2.5:free",
}

# Capability-ranked fallback chain for code generation (strongest to weakest)
# This is used for automatic model selection - users cannot override
BUILDER_MODEL_FALLBACK_CHAIN = [
    "openai/gpt-oss-120b:free",  # 1. Strongest - GPT-4 distilled
    "nvidia/nemotron-3-super-120b-a12b:free",  # 2. Very strong
    "z-ai/glm-4.5-air:free",  # 3. Strong coding capability
    "arcee-ai/trinity-large-preview:free",  # 4. Good capability
    "minimax/minimax-m2.5:free",  # 5. Decent capability
    "stepfun/step-3.5-flash:free",  # 6. Fallback (fast but less capable)
]

DEFAULT_BUILDER_MODEL = "gpt-oss"  # Strongest model is default


def route_builder_message(prompt, has_existing_project=False):
    """Classify a builder message before generation or edit work starts."""
    validator = get_prompt_validator()
    return validator.route(prompt, has_existing_project=has_existing_project)


def get_builder_model_fallback_chain():
    """
    Return the fallback chain for builder model selection.
    Models are ordered by coding capability (strongest to weakest).
    Do not use user input to override this chain.
    """
    return BUILDER_MODEL_FALLBACK_CHAIN


def resolve_builder_model(use_fallback_chain=False):
    """
    Resolve the builder model to use.

    Args:
        use_fallback_chain: If True, returns the ordered fallback chain for sequential retry.
                          If False, returns only the primary (strongest) model.

    Returns:
        str: Single model name if use_fallback_chain=False
        list: Ordered list of model names if use_fallback_chain=True
    """
    if use_fallback_chain:
        return get_builder_model_fallback_chain()
    # Return strongest model only
    return BUILDER_MODEL_FALLBACK_CHAIN[0]


def derive_project_name(prompt):
    text = (prompt or "").strip()
    if not text:
        return "Untitled Project"

    patterns = [
        (r"([\w\s]+?)\s+portfolio", "{} Portfolio"),
        (r"([\w\s]+?)\s+(?:agency|company|business|firm|studio)", "{} Agency"),
        (r"([\w\s]+?)\s+(?:restaurant|cafe|coffee|bakery|bistro)", "{} Restaurant"),
        (r"([\w\s]+?)\s+landing\s+page", "{} Landing Page"),
        (r"([\w\s]+?)\s+(?:saas|app|platform|tool|service)", "{} App"),
        (r"(?:website|site|page|app)\s+(?:for|about)\s+([\w\s]+)", "{} Site"),
    ]
    for pattern, template in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            name = re.sub(r"\s+", " ", match.group(1)).strip().title()
            if len(name) > 2:
                return template.format(name)[:100]

    words = [word for word in re.findall(r"[a-zA-Z0-9]+", text) if len(word) > 2][:4]
    if not words:
        return "Untitled Project"
    return (" ".join(word.title() for word in words) + " Site")[:100]


def _clean_project_title(value):
    candidate = re.sub(r"\s+", " ", (value or "")).strip()
    if not candidate:
        return ""
    invalid_titles = {
        "TechSpace AI Builder",
        "TechSpace Builder",
        "Vite App",
        "React App",
        "Untitled Project",
    }
    if candidate in invalid_titles:
        return ""
    return candidate[:100]


def derive_project_name_from_files(files, fallback_name="Untitled Project"):
    normalized_files = files or []

    def get_file_content(path):
        for file_data in normalized_files:
            if file_data.get("name", "").lower() == path.lower():
                return file_data.get("content", "")
        return ""

    index_html = get_file_content("index.html")
    if index_html:
        title_match = re.search(
            r"<title>\s*(.*?)\s*</title>", index_html, flags=re.IGNORECASE | re.DOTALL
        )
        title = _clean_project_title(title_match.group(1) if title_match else "")
        if title:
            return title

    for entry in ("src/App.jsx", "src/app.jsx", "src/main.jsx"):
        source = get_file_content(entry)
        if not source:
            continue
        heading_match = re.search(
            r"<h1[^>]*>\s*([^<{][^<]{2,80}?)\s*</h1>",
            source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        heading = _clean_project_title(heading_match.group(1) if heading_match else "")
        if heading:
            return heading

    package_json = get_file_content("package.json")
    if package_json:
        try:
            package_data = json.loads(package_json)
            package_name = package_data.get("name", "").replace("-", " ").title()
            package_title = _clean_project_title(package_name)
            if package_title:
                return package_title
        except Exception:
            pass

    return fallback_name[:100]


def restore_generation_credit(user):
    """Refund one builder credit after a failed generation/edit attempt."""
    try:
        UserCredits.objects.filter(user=user).update(
            credits=F("credits") + 1,
            total_used=F("total_used") - 1,
        )
    except Exception as exc:
        logger.error("Credit restore failed for %s: %s", user.username, exc)


def _append_build_log(logs, message):
    if not message:
        return
    text = str(message).strip()
    if text:
        logs.append(text[:1000])


def _find_file_content(files, file_path):
    if not file_path:
        return ""
    normalized = file_path.lower()
    for file_data in files or []:
        if file_data.get("name", "").lower() == normalized:
            return file_data.get("content", "")
    return ""


def _apply_fix_to_session_files(files, fix_data, preferred_file_path=""):
    updated_files = [dict(file_data) for file_data in (files or [])]
    target_files = fix_data.get("files_to_update") or []
    if preferred_file_path:
        target_files = [preferred_file_path, *target_files]

    chosen_path = next((path for path in target_files if path), "")
    fixed_code = fix_data.get("fixed_code", "")
    if not chosen_path or not fixed_code:
        return None

    chosen_path = _normalize_fix_target_path(chosen_path)
    if not chosen_path:
        return None

    for file_data in updated_files:
        if file_data.get("name", "").lower() == chosen_path:
            file_data["content"] = fixed_code
            return updated_files

    if chosen_path in _allowed_new_fix_targets():
        updated_files.append({"name": chosen_path, "content": fixed_code})
        return updated_files

    return None


def _normalize_fix_target_path(path):
    candidate = (path or "").replace("\\", "/").strip().lower()
    candidate = re.sub(r"^\.\/", "", candidate)
    if (
        not candidate
        or ".." in candidate
        or candidate.startswith("/")
        or ":" in candidate
    ):
        return ""
    if not re.match(r"^[a-z0-9_./-]+\.(jsx|js|css|html|json)$", candidate):
        return ""
    return candidate


def _allowed_new_fix_targets():
    return {
        "src/app.jsx",
        "src/main.jsx",
        "src/index.css",
        "index.html",
        "package.json",
        "vite.config.js",
        "tailwind.config.js",
        "postcss.config.js",
    }
    return updated_files


def stream_and_persist_session(
    stream, session, user, fallback_explanation, restore_credit_on_failure=False
):
    """
    Proxy streamed SSE events to the client while persisting session lifecycle state.
    """
    raw_events = []
    build_logs = list(session.build_logs or [])
    last_files = list(session.files or [])
    explanation = session.explanation or fallback_explanation
    preview_url = session.preview_url or ""
    last_error = ""
    completed = False
    completion_persisted = False

    def persist_completed_state():
        project_name = derive_project_name_from_files(
            last_files, fallback_name=session.project_name or "Untitled Project"
        )
        session.files = last_files
        session.project_name = project_name
        session.explanation = explanation
        session.preview_url = preview_url
        session.last_error = ""
        session.status = "done"
        session.build_status = "completed"
        session.verification_status = "pending"
        session.raw_response = "".join(raw_events)
        session.build_logs = build_logs[-200:]
        if session.runtime_provider == "none":
            session.runtime_status = "prepared"
        session.save(
            update_fields=[
                "files",
                "project_name",
                "explanation",
                "raw_response",
                "status",
                "build_status",
                "build_logs",
                "last_error",
                "preview_url",
                "runtime_status",
                "verification_status",
                "updated_at",
            ]
        )

    try:
        for event in stream:
            if isinstance(event, str) and event.startswith("data: "):
                raw_events.append(event)
                data_str = event[6:].strip()
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    payload = None

                if payload:
                    _append_build_log(build_logs, payload.get("status"))
                    _append_build_log(build_logs, payload.get("progress"))
                    _append_build_log(build_logs, payload.get("log"))

                    if "files" in payload:
                        last_files = payload["files"]
                    if payload.get("explanation"):
                        explanation = payload["explanation"]
                    elif payload.get("summary"):
                        explanation = payload["summary"]
                    if payload.get("preview_url"):
                        preview_url = payload["preview_url"]
                    if payload.get("error"):
                        last_error = payload["error"]
                        _append_build_log(build_logs, payload["error"])
                    if payload.get("complete") or payload.get("done"):
                        completed = True
                        persist_completed_state()
                        completion_persisted = True
            yield event
    except Exception as exc:
        logger.error(
            "Stream persistence error for session %s: %s",
            session.id,
            exc,
            exc_info=True,
        )
        last_error = str(exc)
        _append_build_log(build_logs, last_error)
        yield f"data: {json.dumps({'error': last_error})}\n\n"
    finally:
        session.raw_response = "".join(raw_events)
        session.build_logs = build_logs[-200:]

        if completed:
            if not completion_persisted:
                persist_completed_state()
        else:
            session.last_error = (
                last_error or "Generation did not complete successfully."
            )
            session.status = "error"
            session.build_status = "failed"
            session.runtime_status = "failed"
            session.verification_status = "failed"
            if restore_credit_on_failure:
                restore_generation_credit(user)

        session.save(
            update_fields=[
                "files",
                "explanation",
                "raw_response",
                "status",
                "build_status",
                "build_logs",
                "last_error",
                "preview_url",
                "runtime_status",
                "verification_status",
                "updated_at",
            ]
        )


class CreditBalanceView(APIView):
    """GET /api/builder/credits/balance/ — Return the user's current credit balance."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info(f"Fetching credits for user {request.user.username}")

        try:
            credits_obj, created = get_or_create_credits(request.user)

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


class ValidatePromptView(APIView):
    """
    POST /api/builder/validate-prompt/
    Validates that a user's prompt is actually requesting website generation.

    Body: { prompt: str }

    Response:
    {
        "is_valid": true/false,
        "reason": str,
        "suggestion": str (only if invalid)
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get("prompt", "").strip()

        if not prompt:
            return Response(
                {
                    "is_valid": False,
                    "reason": "Prompt cannot be empty",
                    "suggestion": "Try: 'Create a landing page for my coffee shop'",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = route_builder_message(prompt)

            logger.info(
                f"Prompt validation for user {request.user.username}: "
                f"intent={result['intent']}, valid={result['is_valid']}, reason={result['reason']}"
            )

            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Validation error: {e}")
            # On error, allow request (validation skipped)
            return Response(
                {
                    "is_valid": False,
                    "intent": "unclear",
                    "should_generate": False,
                    "response": "I can help with chat or website building. Tell me what you want to create.",
                    "reason": "Validation service temporarily unavailable",
                },
                status=status.HTTP_200_OK,
            )


class AssistantMessageView(APIView):
    """
    POST /api/builder/assistant/message/
    Routes a user message before the frontend decides whether to chat or generate.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        session_id = request.data.get("session_id")

        if not message:
            return Response(
                {"error": "Message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = None
        if session_id:
            session = get_object_or_404(
                GenerationSession, id=session_id, user=request.user
            )

        route = route_builder_message(
            message,
            has_existing_project=bool(session and session.files),
        )
        payload = {
            "message": message,
            "session_id": str(session.id) if session else None,
            **route,
        }
        return Response(payload, status=status.HTTP_200_OK)


class FixErrorView(APIView):
    """
    POST /api/builder/fix-error/
    Analyzes a console error and generates AI-suggested fixes.

    Body: {
        "error_message": str,
        "code_snippet": str (optional),
        "file_path": str (optional),
        "language": str (optional, defaults to "javascript")
    }

    Response:
    {
        "success": bool,
        "error_info": {
            "error_type": str,
            "message": str,
            "language": str,
            "severity": str,
            "file_path": str,
            "line_number": int,
            "suggestion": str
        },
        "fix": {
            "explanation": str,
            "fixed_code": str,
            "files_to_update": list,
            "alternative": str (optional)
        }
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        error_message = request.data.get("error_message", "").strip()

        if not error_message:
            return Response(
                {
                    "success": False,
                    "error": "error_message is required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 1. Extract error information
            extractor = get_error_extractor()
            error_info = extractor.extract(error_message)

            error_info_dict = {
                "error_type": error_info.error_type,
                "message": error_info.message,
                "language": error_info.language,
                "severity": error_info.severity,
                "file_path": error_info.file_path,
                "line_number": error_info.line_number,
                "suggestion": error_info.suggestion,
                "is_blocking": error_info.is_blocking,
            }

            # 2. Generate AI fix
            fixer = get_error_fixer()
            fix_context = {
                "error_message": error_message,
                "code_snippet": request.data.get("code_snippet", ""),
                "file_path": request.data.get("file_path", "unknown"),
                "language": request.data.get("language", error_info.language),
            }

            ai_fix = fixer.get_ai_fix(fix_context)

            logger.info(
                f"Error fix generated for user {request.user.username}: "
                f"error_type={error_info.error_type}, has_fix={ai_fix is not None}"
            )

            response_data = {
                "success": True,
                "error_info": error_info_dict,
                "fix": ai_fix,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fixing failed: {e}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "error": "Failed to analyze error and generate fix",
                    "error_info": {
                        "error_type": "UnknownError",
                        "message": error_message[:200],
                        "language": "unknown",
                    },
                },
                status=status.HTTP_200_OK,  # Still 200 to allow frontend to handle gracefully
            )

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

                user_credits, _ = get_or_create_credits(payment.user)

                # Update existing credits - use F() objects for atomicity
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


class PurchaseCreditsView(APIView):
    """
    POST /api/builder/credits/purchase/
    Initiates a credit purchase via M-Pesa STK push.
    Body: { package_id: uuid } OR { credits: int, phone: str }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            package_id = request.data.get("package_id")
            phone = request.data.get("phone", "").strip()
            credits = request.data.get("credits")

            # Option 1: Purchase by package
            if package_id:
                package = get_object_or_404(
                    CreditPackage, id=package_id, is_active=True
                )
                credits = package.credits
                amount = package.price_kes
                package_name = package.name
            # Option 2: Custom amount
            elif credits and phone:
                credits = int(credits)
                if credits < 10:
                    return Response(
                        {"error": "Minimum 10 credits required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                amount = credits * 10
                package_name = f"Custom {credits} credits"
            else:
                return Response(
                    {"error": "Either provide package_id or credits + phone"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Clean phone number
            phone = phone.replace(" ", "")
            if phone.startswith("07"):
                phone = "254" + phone[1:]
            elif phone.startswith("+254"):
                phone = phone[1:]
            elif phone.startswith("254"):
                pass
            else:
                return Response(
                    {"error": "Invalid phone format. Use 07xxxxxxxxx or 254xxxxxxxxx"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create payment record
            with transaction.atomic():
                payment = CreditPayment.objects.create(
                    user=request.user,
                    package=package if package_id else None,
                    amount=amount,
                    credits=credits,
                    phone_number=phone,
                    status="pending",
                )

                ref = f"BUILDER-{payment.id}"
                description = f"Purchase {credits} credits ({package_name})"
                result = initiate_stk_push(
                    phone=phone,
                    amount=float(amount),
                    ref=ref,
                    description=description,
                )

                payment.mpesa_checkout_id = result.get("CheckoutRequestID", "")
                payment.save()

            return Response(
                {
                    "payment_id": str(payment.id),
                    "status": "pending",
                    "checkout_request_id": payment.mpesa_checkout_id,
                }
            )

        except Exception as e:
            logger.error(f"Purchase credits error for {request.user.username}: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        existing_files = request.data.get("existing_files", None)

        # Note: Model selection is NO LONGER USER-CONFIGURABLE
        # System uses capability-ranked fallback chain automatically

        # Validation
        if not prompt:
            return Response(
                {"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        route = route_builder_message(prompt, has_existing_project=bool(existing_files))
        if not route["should_generate"]:
            return Response(
                {
                    "error": "NON_BUILD_INTENT",
                    "intent": route["intent"],
                    "reason": route["reason"],
                    "assistant_response": route["response"],
                    "suggestion": route["suggestion"],
                    "should_generate": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Credit check
        try:
            with transaction.atomic():
                user_credits, _ = get_or_create_credits(request.user)
                # Refresh from DB to get the latest locked row
                user_credits = UserCredits.objects.select_for_update().get(
                    pk=user_credits.pk
                )

                if user_credits.credits <= 0:
                    return Response(
                        {"error": "NO_CREDITS"}, status=status.HTTP_402_PAYMENT_REQUIRED
                    )
                user_credits.credits -= 1
                user_credits.total_used += 1
                user_credits.save()
        except Exception as e:
            logger.error(f"Credit check error: {e}")
            return Response(
                {"error": "NO_CREDITS"}, status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # Create session
        session = GenerationSession.objects.create(
            user=request.user,
            project_name=derive_project_name(prompt),
            prompt=prompt,
            output_type=output_type,
            style_preset=style_preset,
            status="generating",
            intent_type=route["intent"],
            build_status="generating",
            build_attempts=1,
            credits_used=1,
        )

        # Get the primary (strongest) model - no user override
        model_name = resolve_builder_model(use_fallback_chain=False)

        def stream_response():
            """Generator yielding SSE events via AgentOrchestrator."""
            from .services.agent_orchestrator import AgentOrchestrator

            # The frontend should ideally send a session_id, but for now we generate one
            orchestrator = AgentOrchestrator(session_id=str(session.id))

            try:
                stream = orchestrator.stream_build(
                    prompt=prompt,
                    model_chain=model_chain,
                    existing_files=existing_files,
                    is_chat=False,
                )
                yield from stream_and_persist_session(
                    stream=stream,
                    session=session,
                    user=request.user,
                    fallback_explanation="Generated the requested website.",
                    restore_credit_on_failure=True,
                )
            except Exception as e:
                logger.error(f"Generate stream error: {e}", exc_info=True)
                session.status = "error"
                session.build_status = "failed"
                session.last_error = str(e)
                session.save(
                    update_fields=["status", "build_status", "last_error", "updated_at"]
                )
                restore_generation_credit(request.user)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(
            stream_response(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class SessionListView(APIView):
    """GET /api/builder/sessions/ — List user's last 20 generation sessions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            sessions = GenerationSession.objects.filter(user=request.user)[:20]
            serializer = GenerationSessionSerializer(sessions, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error serializing sessions: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to load sessions: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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


class RuntimeSessionDetailView(APIView):
    """GET /api/builder/sessions/<id>/runtime/ - Return runtime state for a session."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        return Response(
            {
                "session_id": str(session.id),
                "runtime_provider": session.runtime_provider,
                "runtime_status": session.runtime_status,
                "runtime_session_id": session.runtime_session_id,
                "runtime_metadata": session.runtime_metadata,
                "preview_url": session.preview_url,
                "build_status": session.build_status,
                "files_count": len(session.files or []),
            }
        )


class RuntimePrepareView(APIView):
    """POST /api/builder/sessions/<id>/runtime/prepare/ - Build runtime bootstrap payload."""

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)

        if not session.files:
            return Response(
                {"error": "SESSION_HAS_NO_FILES"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = get_runtime_provider(session.output_type)
        runtime_bundle = provider.prepare(session)

        session.runtime_provider = runtime_bundle.provider
        session.runtime_status = runtime_bundle.runtime_status
        session.runtime_session_id = runtime_bundle.runtime_session_id
        session.runtime_metadata = {
            **(session.runtime_metadata or {}),
            "prepare_count": int(
                (session.runtime_metadata or {}).get("prepare_count", 0)
            )
            + 1,
            "output_type": session.output_type,
            "provider_payload_version": 1,
        }
        session.save(
            update_fields=[
                "runtime_provider",
                "runtime_status",
                "runtime_session_id",
                "runtime_metadata",
                "updated_at",
            ]
        )

        return Response(
            {
                "session_id": str(session.id),
                "runtime_provider": session.runtime_provider,
                "runtime_status": session.runtime_status,
                "runtime_session_id": session.runtime_session_id,
                "runtime": runtime_bundle.payload,
            }
        )


class RuntimeEventView(APIView):
    """POST /api/builder/sessions/<id>/runtime/event/ - Persist runtime events from the frontend."""

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        runtime_status = request.data.get("runtime_status", "").strip()
        runtime_session_id = request.data.get("runtime_session_id", "").strip()
        preview_url = request.data.get("preview_url", "").strip()
        metadata = request.data.get("runtime_metadata", {}) or {}
        log_entry = request.data.get("log", "").strip()
        browser_errors = request.data.get("browser_errors")

        valid_runtime_states = {
            "prepared",
            "booting",
            "running",
            "ready",
            "failed",
        }
        if runtime_status and runtime_status not in valid_runtime_states:
            return Response(
                {"error": "INVALID_RUNTIME_STATUS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if runtime_session_id:
            session.runtime_session_id = runtime_session_id
        if runtime_status:
            session.runtime_status = runtime_status
        if preview_url:
            session.preview_url = preview_url

        merged_metadata = dict(session.runtime_metadata or {})
        if isinstance(metadata, dict):
            merged_metadata.update(metadata)
        if browser_errors is not None:
            merged_metadata["browser_errors"] = browser_errors
        session.runtime_metadata = merged_metadata

        if log_entry:
            build_logs = list(session.build_logs or [])
            _append_build_log(build_logs, f"[runtime] {log_entry}")
            session.build_logs = build_logs[-200:]

        if runtime_status == "failed":
            session.last_error = (
                request.data.get("error", "").strip() or session.last_error
            )
            if session.last_error:
                session.build_status = "failed"

        session.save(
            update_fields=[
                "runtime_session_id",
                "runtime_status",
                "runtime_metadata",
                "preview_url",
                "build_logs",
                "last_error",
                "build_status",
                "updated_at",
            ]
        )

        return Response(
            {
                "session_id": str(session.id),
                "runtime_provider": session.runtime_provider,
                "runtime_status": session.runtime_status,
                "runtime_session_id": session.runtime_session_id,
                "preview_url": session.preview_url,
            }
        )


class RuntimeVerifyView(APIView):
    """POST /api/builder/sessions/<id>/runtime/verify/ - Persist verification result from runtime."""

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        runtime_status = request.data.get("runtime_status", "").strip()
        error_message = request.data.get("error_message", "").strip()
        browser_errors = request.data.get("browser_errors", []) or []
        build_errors = request.data.get("build_errors", []) or []

        session.verification_attempts += 1

        has_errors = bool(
            error_message
            or browser_errors
            or build_errors
            or runtime_status == "failed"
        )
        if has_errors:
            combined_errors = []
            if error_message:
                combined_errors.append(error_message)
            combined_errors.extend(str(err) for err in browser_errors if err)
            combined_errors.extend(str(err) for err in build_errors if err)
            session.last_error = "\n".join(combined_errors)[:4000]
            session.verification_status = "failed"
            session.build_status = "failed"
            if runtime_status:
                session.runtime_status = runtime_status
            logs = list(session.build_logs or [])
            _append_build_log(logs, f"[verify] {session.last_error}")
            session.build_logs = logs[-200:]
        else:
            session.verification_status = "verified"
            session.build_status = "completed"
            session.runtime_status = runtime_status or "ready"
            session.last_error = ""
            logs = list(session.build_logs or [])
            _append_build_log(logs, "[verify] Runtime verification passed.")
            session.build_logs = logs[-200:]

        session.save(
            update_fields=[
                "verification_attempts",
                "verification_status",
                "build_status",
                "runtime_status",
                "last_error",
                "build_logs",
                "updated_at",
            ]
        )

        return Response(
            {
                "session_id": str(session.id),
                "verification_status": session.verification_status,
                "verification_attempts": session.verification_attempts,
                "build_status": session.build_status,
                "last_error": session.last_error,
            }
        )


class RuntimeAutoFixView(APIView):
    """POST /api/builder/sessions/<id>/runtime/auto-fix/ - Suggest and apply a bounded runtime fix."""

    permission_classes = [IsAuthenticated]
    MAX_AUTO_FIX_ATTEMPTS = 2

    def post(self, request, session_id):
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)
        if session.auto_fix_attempts >= self.MAX_AUTO_FIX_ATTEMPTS:
            return Response(
                {"error": "AUTO_FIX_LIMIT_REACHED"},
                status=status.HTTP_409_CONFLICT,
            )

        error_message = (
            request.data.get("error_message", "").strip() or session.last_error
        )
        if not error_message:
            return Response(
                {"error": "ERROR_MESSAGE_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_path = request.data.get("file_path", "").strip()
        code_snippet = request.data.get("code_snippet", "").strip()
        if not code_snippet:
            code_snippet = _find_file_content(session.files, file_path)

        extractor = get_error_extractor()
        error_info = extractor.extract(error_message)
        fixer = get_error_fixer()
        fix_data = fixer.get_ai_fix(
            {
                "error_message": error_message,
                "code_snippet": code_snippet,
                "file_path": file_path or error_info.file_path or "unknown",
                "language": request.data.get("language", error_info.language),
            }
        )
        if not fix_data:
            return Response(
                {"error": "AUTO_FIX_UNAVAILABLE"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        updated_files = _apply_fix_to_session_files(
            session.files, fix_data, preferred_file_path=file_path
        )
        if updated_files is None:
            return Response(
                {"error": "UNSAFE_FIX_TARGET"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.auto_fix_attempts += 1
        session.verification_status = "retrying"
        session.build_status = "generating"
        session.status = "generating"
        session.last_error = error_message
        session.files = updated_files

        logs = list(session.build_logs or [])
        _append_build_log(
            logs,
            f"[auto-fix] Attempt {session.auto_fix_attempts}: {fix_data.get('explanation', 'Applied runtime fix.')}",
        )
        session.build_logs = logs[-200:]

        runtime_metadata = dict(session.runtime_metadata or {})
        runtime_metadata["last_auto_fix"] = {
            "error_type": error_info.error_type,
            "file_path": file_path or error_info.file_path,
            "files_to_update": fix_data.get("files_to_update", []),
        }
        session.runtime_metadata = runtime_metadata

        session.save(
            update_fields=[
                "auto_fix_attempts",
                "verification_status",
                "build_status",
                "status",
                "last_error",
                "files",
                "build_logs",
                "runtime_metadata",
                "updated_at",
            ]
        )

        return Response(
            {
                "session_id": str(session.id),
                "verification_status": session.verification_status,
                "auto_fix_attempts": session.auto_fix_attempts,
                "fix": fix_data,
                "error_info": {
                    "error_type": error_info.error_type,
                    "language": error_info.language,
                    "file_path": error_info.file_path,
                    "line_number": error_info.line_number,
                },
                "files": session.files,
            }
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

        # Note: Model selection is NO LONGER USER-CONFIGURABLE
        # System uses capability-ranked fallback chain automatically

        if not user_message:
            return Response(
                {"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get the existing session
        session = get_object_or_404(GenerationSession, id=session_id, user=request.user)

        route = route_builder_message(user_message, has_existing_project=True)
        if not route["should_generate"]:
            return Response(
                {
                    "intent": route["intent"],
                    "reason": route["reason"],
                    "assistant_response": route["response"],
                    "suggestion": route["suggestion"],
                    "should_generate": False,
                    "session_id": str(session.id),
                },
                status=status.HTTP_200_OK,
            )

        # Get conversation history
        conversation = session.conversation or []

        # Add user message to conversation
        conversation.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": timezone.now().isoformat(),
            }
        )

        # Credit check - for follow-up generations
        try:
            with transaction.atomic():
                user_credits, _ = get_or_create_credits(request.user)
                # Refresh from DB to get the latest locked row
                user_credits = UserCredits.objects.select_for_update().get(
                    pk=user_credits.pk
                )

                if user_credits.credits <= 0:
                    return Response(
                        {"error": "NO_CREDITS"}, status=status.HTTP_402_PAYMENT_REQUIRED
                    )
                user_credits.credits -= 1
                user_credits.total_used += 1
                user_credits.save()
        except Exception as e:
            logger.error(f"Credit check error in ChatView: {e}")
            return Response(
                {"error": "NO_CREDITS"}, status=status.HTTP_402_PAYMENT_REQUIRED
            )

        session.intent_type = route["intent"]
        session.status = "generating"
        session.build_status = "generating"
        session.build_attempts += 1
        session.last_error = ""
        session.save(
            update_fields=[
                "intent_type",
                "status",
                "build_status",
                "build_attempts",
                "last_error",
                "updated_at",
            ]
        )

        # Build context for AI
        existing_files = session.files
        output_type = session.output_type

        # Get the primary (strongest) model - no user override
        model_name = resolve_builder_model(use_fallback_chain=False)

        def stream_response():
            try:
                from .services.agent_orchestrator import AgentOrchestrator

                orchestrator = AgentOrchestrator(session_id=str(session.id))

                gen = orchestrator.stream_build(
                    prompt=user_message,
                    model_name=model_name,
                    existing_files=existing_files,
                    is_chat=True,
                )
                yield from stream_and_persist_session(
                    stream=gen,
                    session=session,
                    user=request.user,
                    fallback_explanation="Updated the website based on your instructions.",
                    restore_credit_on_failure=True,
                )

                session.refresh_from_db(
                    fields=["status", "files", "explanation", "preview_url"]
                )
                if session.status == "done":
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": session.explanation,
                            "files": session.files,
                            "timestamp": timezone.now().isoformat(),
                        }
                    )
                    session.conversation = conversation
                    session.save(update_fields=["conversation", "updated_at"])
                    yield f"data: {json.dumps({'complete': True, 'build_verified': False, 'preview_url': session.preview_url, 'files': session.files, 'conversation': conversation})}\n\n"

            except Exception as e:
                logger.error(f"Chat generation error: {e}")
                session.status = "error"
                session.build_status = "failed"
                session.last_error = str(e)
                session.save(
                    update_fields=["status", "build_status", "last_error", "updated_at"]
                )
                restore_generation_credit(request.user)

                yield f"data: {json.dumps({'error': str(e)})}\n\n"

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

    def _build_context_prompt(
        self, user_message, conversation_history, existing_files, output_type
    ):
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
