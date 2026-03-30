import os
import json
import requests
import time
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEY = os.environ.get("OPEN_ROUTER")
# Default model from the codebase, but you can change it to a thinking model like 'deepseek/deepseek-r1'
DEFAULT_MODEL = "nousresearch/hermes-3-llama-3.1-405b:free"

def test_streaming(model_name=None):
    model = model_name or DEFAULT_MODEL
    print(f"================================================================")
    print(f"         OPENROUTER STREAMING & THINKING TESTER               ")
    print(f"================================================================")
    api_display = f"{API_KEY[:10]}...{API_KEY[-4:]}" if API_KEY else "NOT FOUND"
    print(f"Model: {model}")
    print(f"API Key: {api_display}")
    
    if not API_KEY:
        print("\nERROR: OPEN_ROUTER key not found in .env file.")
        print("Please ensure you have OPEN_ROUTER=sk-or-v1-... in your cybercraft/.env")
        return

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://techspacehub.co.ke",
        "X-Title": "TechSpaceHub Connectivity Test",
        "Accept": "text/event-stream",
    }
    
    # Request that encourages thinking/reasoning and multiple files
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": "You are an expert web developer. Use <think> tags for your reasoning if your model supports it. Generate code using the format: --- filename --- content --- filename ---."
            },
            {
                "role": "user", 
                "content": "Generate a simple React counter component. Include App.jsx and Counter.jsx."
            }
        ],
        "stream": True,
        "temperature": 0.5,
    }

    print("\n[1/3] Sending POST request to OpenRouter...")
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        
        if not response.ok:
            print(f"\n❌ HTTP Error {response.status_code}")
            print(f"Response: {response.text}")
            return

        ttft = None  # Time to first token
        has_thinking = False
        has_content = False
        token_count = 0
        raw_buffer = ""
        
        print(f"[2/3] Connection established. Waiting for chunks...\n")
        print("--- STREAM START ---")
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            if line.startswith("data: "):
                if line.strip() == "data: [DONE]":
                    print("\n--- STREAM END ---")
                    break
                
                try:
                    data = json.loads(line[6:])
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    
                    content = delta.get("content", "")
                    reasoning = delta.get("reasoning", "") # Standard field for some models
                    
                    if ttft is None and (content or reasoning):
                        ttft = time.time() - start_time
                        print(f"\n[First Token @ {ttft:.2f}s]\n")

                    if reasoning:
                        has_thinking = True
                        print(f"\033[90m{reasoning}\033[00m", end="", flush=True) # Gray text for reasoning
                    
                    if content:
                        has_content = True
                        token_count += 1
                        print(content, end="", flush=True)
                        
                        if "<think" in content.lower() or "<thought" in content.lower():
                            has_thinking = True
                            
                except Exception as e:
                    pass # Skip noise
        
        total_time = time.time() - start_time
        
        print(f"\n\n[3/3] Analysis Complete.")
        print(f"-----------------------------------------------------")
        print(f" RESULTS SUMMARY                                   ")
        print(f"-----------------------------------------------------")
        print(f" Streaming Active:   {'YES' if has_content else 'NO'}")
        print(f" Thinking Detected:  {'YES' if has_thinking else 'NO'}")
        print(f" Time to 1st Token:  {ttft:.2f}s")
        print(f" Total Time:         {total_time:.2f}s")
        print(f" Total Tokens:       {token_count}")
        print(f" Avg Speed:          {token_count/total_time:.1f} tokens/sec")
        print(f"-----------------------------------------------------")
        
    except KeyboardInterrupt:
        print("\n\nTest aborted by user.")
    except Exception as e:
        print(f"\n❌ Request failed: {e}")

if __name__ == "__main__":
    import sys
    selected_model = sys.argv[1] if len(sys.argv) > 1 else None
    test_streaming(selected_model)
