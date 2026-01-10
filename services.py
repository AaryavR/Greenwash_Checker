import os
import json
import asyncio
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- PROMPTS ---
ANALYZER_PROMPT = """
You are a food safety expert. Analyze these ingredients AND claims. 
For every item, assign a status: 'GREEN' (Safe/Verified), 'YELLOW' (Caution), or 'RED' (Avoid/Lie).

Rules for Ingredients:
1. Sugar, Corn Syrup, Red 40, Titanium Dioxide -> RED.
2. Natural preservatives, processed oils -> YELLOW.
3. Whole foods, water, vitamins -> GREEN.

Rules for Claims (e.g., "Natural", "No Sugar"):
1. If the claim is TRUE based on ingredients -> GREEN.
2. If the claim is misleading (e.g., "Natural" but has chemicals) -> RED.
3. If the claim is vague -> YELLOW.

Output strictly valid JSON:
{
  "ItemName": { "status": "RED", "explanation": "Reason here" }
}
"""

TIEBREAKER_PROMPT = """
Two AIs disagreed on this item: "{item}".
AI 1: {status_a}
AI 2: {status_b}
Decide the scientific truth. Output JSON: { "final_status": "RED/YELLOW/GREEN", "final_explanation": "Ruling" }
"""

WITTY_SUMMARY_PROMPT = """
You are a sarcastic, witty food critic. Look at this list of ingredients and their safety status (Red/Yellow/Green).
Write a ONE-LINE summary of this product. 
- If it's healthy, be begrudgingly impressed.
- If it's unhealthy, roast it ruthlessly but funny.
- Keep it under 20 words.
"""

# --- 1. VISION ---
async def extract_text_from_image(image_file):
    model = genai.GenerativeModel('gemini-flash-latest')
    image_data = await image_file.read()
    
    prompt = "Extract ingredients and marketing claims (e.g. 'Low Fat', 'Natural'). Return JSON: {'ingredients': [], 'claims': []}"
    
    try:
        response = model.generate_content([prompt, {'mime_type': image_file.content_type, 'data': image_data}])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return {"ingredients": [], "claims": ["Error reading image"]}

# --- 2. ANALYZERS ---
async def analyze_ingredients_parallel(data):
    ingredients = data.get("ingredients", [])
    claims = data.get("claims", [])
    
    # Combine list for analysis
    all_items = ingredients + claims
    
    if not all_items: return [], "No data found."

    text_input = f"Analyze these items: {all_items}. Ingredients list for context: {ingredients}"

    task1 = asyncio.to_thread(call_gemini_analyzer, text_input)
    task2 = asyncio.to_thread(call_groq_analyzer, text_input)

    result_a, result_b = await asyncio.gather(task1, task2)
    
    final_results = await merge_and_judge(all_items, result_a, result_b)
    
    # Generate Witty Summary based on final results
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
            temperature=0, 
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except: return {}

# --- 3. CONSENSUS & WIT ---
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
    prompt = TIEBREAKER_PROMPT.format(item=item, status_a=a, status_b=b)
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: return {"final_status": "YELLOW", "final_explanation": "Judge unavailable."}

async def generate_witty_summary(final_results):
    model = genai.GenerativeModel('gemini-flash-latest')
    # Convert results to a simple string for the AI to read
    context = str([f"{r['name']}: {r['status']}" for r in final_results])
    try:
        response = model.generate_content(WITTY_SUMMARY_PROMPT + f"\nData: {context}")
        return response.text.strip()
    except:
        return "I'm speechless."