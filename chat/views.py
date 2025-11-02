# chatbot/views.py
'''from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from openai import OpenAI
import json
import os
import logging

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Enhanced system prompt for general purpose help
SYSTEM_PROMPT = """You are Cybercraft's AI teaching assistant. You are:
- EXTREMELY helpful, patient, and detailed
- You explain concepts clearly with examples when needed
- You break down complex topics into simple steps
- You provide code examples with proper formatting
- You're friendly and encouraging
- You admit when you don't know something

You help students with:
• Programming concepts (Python, JavaScript, React, etc.)
• Debugging and code explanation
• Computer science fundamentals
• Web development questions
• Best practices and design patterns
• Career advice in tech
• General learning strategies

Always be conversational and engaging. If explaining code, use clear examples."""


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        user_message = data.get("message", "").strip()
        conversation_history = data.get("history", [])

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # Build messages with conversation history
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history (last 6 messages to manage context)
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        # Get AI response
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=800,  # Allow longer responses for explanations
        )

        ai_reply = response.choices[0].message.content

        return JsonResponse(
            {"reply": ai_reply, "message_id": f"msg_{len(conversation_history) + 1}"}
        )

    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}", exc_info=True)
        return JsonResponse(
            {
                "error": "I'm having trouble responding right now. Please try again in a moment."
            },
            status=500,
        )


# Optional: Streaming endpoint for better UX
@csrf_exempt
def chat_stream(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            user_message = data.get("message", "").strip()

            def generate():
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ]

                stream = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"

                yield "data: [DONE]\n\n"

            return StreamingHttpResponse(generate(), content_type="text/plain")

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
'''
# chatbot/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import google.generativeai as genai
import json
import os
import logging
import time
from django.http import StreamingHttpResponse

logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
AVAILABLE_MODELS = []

# In your backend views.py, update the SYSTEM_PROMPT:

SYSTEM_PROMPT = """You are a helpful programming tutor for TechSpace. When providing code examples:

1. Use proper markdown formatting with code blocks
2. Specify the programming language after the triple backticks
3. Keep explanations clear and concise
4. Use bullet points for lists
5. Use **bold** for important concepts
6. Use ___ or --- or *** for horizontal lines

Example format:
```python
print("Hello, World!")

You need to use lines to separate paragraphs or sections of your chat
You must also answer all learning questions correctly except where asked to generate malicious stuffs, notify the user that it is prohibited

"""

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)

        # List available models to see what we can use
        try:
            models = genai.list_models()
            for model in models:
                if "generateContent" in model.supported_generation_methods:
                    AVAILABLE_MODELS.append(model.name)

            if AVAILABLE_MODELS:
                GEMINI_AVAILABLE = True

            else:
                logger.warning(
                    "No Gemini models available with generateContent support"
                )

        except Exception as model_error:
            logger.error(f"Failed to list Gemini models: {str(model_error)}")

    except Exception as e:
        logger.error(f"Gemini configuration failed: {str(e)}")
else:
    logger.warning("No GEMINI_API_KEY found in environment")


def get_gemini_response(messages):
    """Get response from Google Gemini using available models"""
    if not GEMINI_AVAILABLE or not AVAILABLE_MODELS:
        return None

    try:
        # Build the conversation prompt
        conversation_text = """You are a helpful programming tutor for TechSpace. Help students with coding questions, debugging, and learning programming concepts.

Conversation so far:\n"""

        # Add conversation history (last 6 messages)
        for msg in messages[-6:]:
            if msg.get("role") == "user":
                conversation_text += f"Student: {msg.get('content', '')}\n"
            else:
                conversation_text += f"Assistant: {msg.get('content', '')}\n"

        # Add the current question
        current_question = messages[-1].get("content", "") if messages else ""
        conversation_text += f"\nStudent: {current_question}\nAssistant:"

        # Try the most stable models first
        preferred_models = [
            "gemini-2.0-flash-001",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-pro-latest",
            "gemini-flash-latest",
        ]

        # Try preferred models first
        for model_name in preferred_models:
            if f"models/{model_name}" in AVAILABLE_MODELS:
                try:
                    logger.info(f"Trying preferred model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(
                        conversation_text,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,
                            max_output_tokens=800,
                        ),
                    )
                    logger.info(f"Successfully used model: {model_name}")
                    return response.text
                except Exception as model_error:
                    logger.warning(
                        f"Preferred model {model_name} failed: {str(model_error)}"
                    )
                    continue

        for model_name in AVAILABLE_MODELS:
            short_name = model_name.replace("models/", "")
            # Skip models that are clearly not for text generation
            if any(
                x in short_name
                for x in ["image", "tts", "thinking", "robotics", "computer-use"]
            ):
                continue

            try:
                logger.info(f"Trying fallback model: {short_name}")
                model = genai.GenerativeModel(short_name)
                response = model.generate_content(
                    conversation_text,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=800,
                    ),
                )
                logger.info(f"Successfully used fallback model: {short_name}")
                return response.text
            except Exception as model_error:
                logger.warning(f"Model {short_name} failed: {str(model_error)}")
                continue

        logger.error("All models failed")
        return None

    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        return None


def get_fallback_response(user_message, conversation_history):
    """Enhanced fallback responses that are actually helpful"""
    user_message_lower = user_message.lower()

    # Greetings
    if any(word in user_message_lower for word in ["hello", "hi", "hey", "hola"]):
        return "Hello, how are you doing?"


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        user_message = data.get("message", "").strip()
        conversation_history = data.get("history", [])

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # Build messages in standard format
        messages = []

        # Add conversation history
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        # Try Gemini if available
        ai_reply = None
        if GEMINI_AVAILABLE:
            ai_reply = get_gemini_response(messages)

        # If Gemini fails or isn't available, use enhanced fallback
        if not ai_reply:
            ai_reply = get_fallback_response(user_message, conversation_history)

        return JsonResponse(
            {
                "reply": ai_reply,
                "message_id": f"msg_{len(conversation_history) + 1}",
                "source": "gemini" if ai_reply and GEMINI_AVAILABLE else "fallback",
                "available_models": AVAILABLE_MODELS if GEMINI_AVAILABLE else [],
            }
        )

    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}", exc_info=True)
        return JsonResponse(
            {
                "reply": get_fallback_response(user_message, []),
                "error": "Service temporarily unavailable",
            }
        )


# Add this to see what models are available
@csrf_exempt
def test_models(request):
    return JsonResponse(
        {
            "gemini_available": GEMINI_AVAILABLE,
            "available_models": AVAILABLE_MODELS,
            "gemini_api_key_set": bool(GEMINI_API_KEY),
        }
    )


@csrf_exempt
def test_gemini_working(request):
    """Test if Gemini is actually working"""
    if not GEMINI_AVAILABLE:
        return JsonResponse({"status": "error", "message": "Gemini not available"})

    try:
        # Simple test with a stable model
        model = genai.GenerativeModel("gemini-2.0-flash-001")
        response = model.generate_content("Say 'Gemini is working!' in one sentence.")

        return JsonResponse(
            {
                "status": "success",
                "message": "Gemini is working!",
                "response": response.text,
                "tested_model": "gemini-2.0-flash-001",
            }
        )

    except Exception as e:
        return JsonResponse(
            {
                "status": "error",
                "message": f"Gemini test failed: {str(e)}",
                "available_models": AVAILABLE_MODELS,
            }
        )


# chat/views.py - Add these new functions and imports


def get_gemini_stream_response(messages):
    """Get streaming response from Google Gemini"""
    if not GEMINI_AVAILABLE or not AVAILABLE_MODELS:
        return None

    try:
        # Build the conversation prompt (same as before)
        conversation_text = """You are a helpful programming tutor for TechSpace. Help students with coding questions, debugging, and learning programming concepts.

Conversation so far:\n"""

        for msg in messages[-6:]:
            if msg.get("role") == "user":
                conversation_text += f"Student: {msg.get('content', '')}\n"
            else:
                conversation_text += f"Assistant: {msg.get('content', '')}\n"

        current_question = messages[-1].get("content", "") if messages else ""
        conversation_text += f"\nStudent: {current_question}\nAssistant:"

        # Try preferred models for streaming
        preferred_models = [
            "gemini-2.0-flash-001",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-pro-latest",
            "gemini-flash-latest",
        ]

        for model_name in preferred_models:
            if f"models/{model_name}" in AVAILABLE_MODELS:
                try:
                    logger.info(f"Trying streaming with model: {model_name}")
                    model = genai.GenerativeModel(model_name)

                    # Use streaming response
                    response = model.generate_content(
                        conversation_text,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,
                            max_output_tokens=800,
                        ),
                        stream=True,  # Enable streaming
                    )

                    # Yield chunks as they come
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
                    return

                except Exception as model_error:
                    logger.warning(
                        f"Streaming with {model_name} failed: {str(model_error)}"
                    )
                    continue

        # If streaming fails, fall back to non-streaming for one of the models
        logger.warning("Streaming failed, falling back to non-streaming")
        fallback_response = get_gemini_response(messages)
        if fallback_response:
            # Simulate streaming by yielding words with delays
            words = fallback_response.split()
            for word in words:
                yield word + " "
                time.sleep(0.05)  # Small delay between words
        else:
            yield "I'm having trouble connecting right now. Please try again."

    except Exception as e:
        logger.error(f"Gemini streaming error: {str(e)}")
        yield "Sorry, I'm experiencing technical difficulties. Please try again later."


@csrf_exempt
@require_http_methods(["POST"])
def chat_stream(request):
    """Streaming chat endpoint that returns real-time responses"""
    try:
        data = json.loads(request.body.decode("utf-8"))
        user_message = data.get("message", "").strip()
        conversation_history = data.get("history", [])

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)

        # Build messages
        messages = []
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})

        messages.append({"role": "user", "content": user_message})

        def event_stream():
            try:
                # Send start signal
                yield f"data: {json.dumps({'type': 'start'})}\n\n"

                full_response = ""
                stream_generator = get_gemini_stream_response(messages)

                if stream_generator:
                    for chunk in stream_generator:
                        full_response += chunk
                        # Send each chunk to the client
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                        time.sleep(0.02)  # Small delay for natural typing effect

                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete', 'full_response': full_response})}\n\n"

            except Exception as e:
                logger.error(f"Stream error: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'content': 'Stream interrupted'})}\n\n"

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # Disable buffering for nginx
        return response

    except Exception as e:
        logger.error(f"Chat stream setup error: {str(e)}")
        return JsonResponse({"error": "Stream setup failed"}, status=500)
