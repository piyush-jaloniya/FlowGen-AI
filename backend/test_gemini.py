"""Test Gemini API connection"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key: {api_key[:20]}..." if api_key else "No API key found")

if api_key:
    try:
        genai.configure(api_key=api_key)
        
        # List available models
        print("\n📋 Listing available models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Test with simple code
        test_code = """
def swap(a, b):
    return b, a
"""
        
        prompt = f"""Analyze this Python code and provide a concise 1-2 sentence description of what it does.

Code:
```python
{test_code}
```

Description:"""
        
        print("\n🔍 Sending test request to Gemini...")
        response = model.generate_content(prompt)
        print(f"✅ Response: {response.text}")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ GEMINI_API_KEY not found in .env file")
