import os
import json
import asyncio
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# USE THE MODEL FROM YOUR LIST (Lite version = Higher Limits)
GOOGLE_MODEL_NAME = 'gemini-2.0-flash-lite-preview-02-05'

# --- PROMPTS ---
ANALYZER_PROMPT = """
You are a ruthless Environmental Scientist. Detect Greenwashing.
PRIORITY 1: PLANETARY HEALTH
- RED: High Carbon (Beef, Dairy), Deforestation (Palm Oil), Microplastics.
- YELLOW: High Water (Almonds), Imported.
- GREEN: Plant-based, Organic, Locally sourced.
Output strictly valid JSON:
{ "ItemName": { "status": "RED", "explanation": "Reason..." } }
"""

TIEBREAKER_PROMPT = """
Decide based on ENVIRONMENTAL IMPACT.
Item: {item}
AI 1: {status_a}
AI 2: {status_b}
Output JSON: { "final_status": "RED/YELLOW/GREEN", "final_explanation": "Ruling" }
"""

WITTY_SUMMARY_PROMPT = """
You are a sarcastic environmental activist. 
Write a ONE-LINE summary.
- Greenwashing: Roast them.
- Sustainable: Be skeptical but impressed.
- Keep it under 20 words.
"""

# --- 1. VISION ---
async def extract_text_from_image(image_file):
    print(f"--- Vision: Using {GOOGLE_MODEL_NAME} ---")
    model = genai.GenerativeModel(GOOGLE_MODEL_NAME)
    image_data = await image_file.read()
    
    prompt = "Extract ingredients and claims. Return JSON: {'ingredients': [], 'claims': []}"
    
    try:
        response = model.generate_content([prompt, {'mime_type': image_file.content_type, 'data': image_data}])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"!!! VISION ERROR: {e}")
        # Fallback: Return empty so the app doesn't crash, just says "No data"
        return {"ingredients": [], "claims": ["Error reading image"]}

# --- 2. ANALYZERS (FAIL-SAFE) ---
async def analyze_ingredients_parallel(data):
    ingredients = data.get("ingredients", [])
    claims = data.get("claims", [])
    all_items = ingredients + claims
    
    if not all_items: return [], "No ingredients found."

    text_input = f"Analyze: {all_items}"
    
    # Run Parallel - IF GOOGLE FAILS, IT WON'T KILL THE APP
    task1 = asyncio.to_thread(call_gemini_analyzer, text_input)
    task2 = asyncio.to_thread(call_groq_analyzer, text_input)
    
    # return_exceptions=True prevents one crash from stopping the other
    results = await asyncio.gather(task1, task2, return_exceptions=True)
    
    result_a = results[0] if not isinstance(results[0], Exception) else {}
    result_b = results[1] if not isinstance(results[1], Exception) else {}
    
    if isinstance(results[0], Exception): print(f"⚠️ Google Analyzer Failed: {results[0]}")

    final_results = await merge_and_judge(all_items, result_a, result_b)
    summary = await generate_witty_summary(final_results)
    
    return final_results, summary

def call_gemini_analyzer(content):
    model = genai.GenerativeModel(GOOGLE_MODEL_NAME)
    response = model.generate_content(
        ANALYZER_PROMPT + "\nInput: " + content,
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def call_groq_analyzer(content):
    # Groq is our Safety Net. It rarely fails.
    completion = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "system", "content": ANALYZER_PROMPT}, {"role": "user", "content": content}],
        temperature=0, response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

# --- 3. CONSENSUS ---
async def merge_and_judge(all_items, analysis_a, analysis_b):
    final_report = []
    for item in all_items:
        a = analysis_a.get(item)
        b = analysis_b.get(item)
        
        # If Google Failed (Empty A), use Groq (B)
        if not a: a = b
        # If Groq Failed (Empty B), use Google (A)
        if not b: b = a
        
        if not a: continue # If both failed, skip

        if a['status'] == b['status']:
            final_report.append({"name": item, "status": a['status'], "explanation": a['explanation']})
        else:
            ruling = await call_tiebreaker(item, a, b)
            final_report.append({"name": item, "status": ruling['final_status'], "explanation": ruling['final_explanation']})
    return final_report

async def call_tiebreaker(item, a, b):
    model = genai.GenerativeModel(GOOGLE_MODEL_NAME)
    prompt = TIEBREAKER_PROMPT.format(item=item, status_a=a['status'], status_b=b['status'])
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: 
        # If Judge fails, default to Caution
        return {"final_status": "YELLOW", "final_explanation": "Judge unavailable (Quota Limit)."}

# --- 4. SUMMARY ---
async def generate_witty_summary(final_results):
    model = genai.GenerativeModel(GOOGLE_MODEL_NAME)
    
    if not final_results: return "I couldn't read the label."

    context = str([f"{r['name']}: {r['status']}" for r in final_results])
    
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        response = model.generate_content(
            WITTY_SUMMARY_PROMPT + f"\nData: {context}",
            safety_settings=safety_settings
        )
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Summary Failed: {e}")
        return "I'm speechless (literally, the API crashed)."