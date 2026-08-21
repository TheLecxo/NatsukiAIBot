import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
print('KEY_SET=', bool(key))
client = genai.Client(api_key=key)
models = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.5-pro',
    'gemini-flash-latest',
    'gemini-3.1-flash-lite',
    'gemini-3-flash-preview'
]
for model in models:
    try:
        response = client.models.generate_content(model=model, contents='Say hello in one short sentence.')
        text = getattr(response, 'text', str(response))
        print('MODEL_OK=', model)
        print(text[:200])
        break
    except Exception as e:
        print('MODEL_FAIL=', model, type(e).__name__, e)
