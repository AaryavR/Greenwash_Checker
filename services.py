import os
import json
import asyncio
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # <--- New Import
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- PROMPTS ---
ANALYZER_PROMPT = """
You are a ruthless Environmental Scientist. Detect Greenwashing.
PRIORITY 1: PLANETARY HEALTH (Sustainability)
- RED: High Carbon (Beef, Dairy), Deforestation (Palm Oil), Microplastics, "Uncertified" claims.
- YELLOW: High Water (Almonds), Imported/Food Miles, Industrial Monocultures.
- GREEN: Plant-based, Organic, Fair Trade, Locally sourced.

PRIORITY 2: HUMAN HEALTH
- RED: Toxic/Carcinogenic ingredients.
- YELLOW: Unhealthy (Sugar) but not toxic.

Output strictly valid JSON:
{ "ItemName": { "status": "RED", "explanation": "Reason..." } }
"""

TIEBREAKER_PROMPT = """
Two AIs disagreed on: "{item}".
AI 1: {status_a}
AI 2: {status_b}
Decide based on ENVIRONMENTAL IMPACT first.
Output JSON: { "final_status": "RED/YELLOW/GREEN", "final_explanation": "Ruling" }
"""

WITTY_SUMMARY_PROMPT = """
You are a sarcastic environmental activist. 
Write a ONE-LINE summary of this product based on these ingredients.
- If it's greenwashing: Roast them ruthlessly.
- If it's sustainable: Be skeptical but impressed.
- Keep it under 20 words.
"""

# --- 1. VISION ---
async def extract_text_from_image(image_file):
    model = genai.GenerativeModel('gemini-flash-latest')
    image_data = await image_file.read()
    prompt = "Extract ingredients and Green claims. Return JSON: {'ingredients': [], 'claims': []}"
    try:
        response = model.generate_content([prompt, {'mime_type': image_file.content_type, 'data': image_data}])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"VISION ERROR: {e}")
        return {"ingredients": [], "claims": ["Error reading image"]}

# --- 2. ANALYZERS ---
async def analyze_ingredients_parallel(data):
    ingredients = data.get("ingredients", [])
    claims = data.get("claims", [])
    all_items = ingredients + claims
    
    if not all_items: return [], "No data found."

    text_input = f"Analyze: {all_items}"
    
    # Run Parallel
    task1 = asyncio.to_thread(call_gemini_analyzer, text_input)
    task2 = asyncio.to_thread(call_groq_analyzer, text_input)
    result_a, result_b = await asyncio.gather(task1, task2)
    
    final_results = await merge_and_judge(all_items, result_a, result_b)
    summary = await generate_witty_summary(final_results)
    
    return final_results, summary

def call_gemini_analyzer(content):
    model = genai.GenerativeModel('gemini-flash-latest')
    try:
        response = model.generate_content(
            ANALYZER_PROMPT + "\nInput: " + content,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except: return {}

def call_groq_analyzer(content):
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "system", "content": ANALYZER_PROMPT}, {"role": "user", "content": content}],
            temperature=0, response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except: return {}

# --- 3. CONSENSUS ---
async def merge_and_judge(all_items, analysis_a, analysis_b):
    final_report = []
    for item in all_items:
        a = analysis_a.get(item)
        b = analysis_b.get(item)
        
        if not a: a = b
        if not b: b = a
        if not a: continue

        if a['status'] == b['status']:
            final_report.append({"name": item, "status": a['status'], "explanation": a['explanation']})
        else:
            ruling = await call_tiebreaker(item, a, b)
            final_report.append({"name": item, "status": ruling['final_status'], "explanation": ruling['final_explanation']})
    return final_report

async def call_tiebreaker(item, a, b):
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = TIEBREAKER_PROMPT.format(item=item, status_a=a['status'], status_b=b['status'])
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: return {"final_status": "YELLOW", "final_explanation": "Judge unavailable."}

# --- 4. SUMMARY (FIXED) ---
async def generate_witty_summary(final_results):
    model = genai.GenerativeModel('gemini-flash-latest')
    
    # Check if results exist
    if not final_results:
        return "I couldn't read the label, but I'm assuming it's destroying the rainforest."

    context = str([f"{r['name']}: {r['status']}" for r in final_results])
    
    # DISABLE SAFETY FILTERS (Allows "roasting")
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
        print(f"⚠️ SUMMARY ERROR: {e}") # This will show in Render Logs
        return f"The AI is silent. (Error: {str(e)[:50]}...)"