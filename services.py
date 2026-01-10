import os
import json
import base64
import asyncio
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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

# Double curly braces {{ }} around the JSON example so .format() ignores them
TIEBREAKER_PROMPT = """
Decide based on ENVIRONMENTAL IMPACT.
Item: {item}
AI 1 (Scientist): {status_a}
AI 2 (Critic): {status_b}
Output JSON: {{ "final_status": "RED/YELLOW/GREEN", "final_explanation": "Ruling" }}
"""

LOGISTICS_PROMPT = """
You are a Logistics Detective.
1. Identify the Country of Origin from the text.
2. Calculate distance to Dubai, UAE.
   - Local (UAE): Bonus.
   - Regional (GCC): Neutral.
   - International (>2000km): Penalty.
3. Roast the food miles.
Output JSON: {{ "origin": "Country", "is_local": true/false, "roast": "Short sarcastic comment on distance." }}
"""

WITTY_SUMMARY_PROMPT = """
You are a sarcastic environmental activist. 
Write a ONE-LINE summary of this product.
- Context: It contains {bad_count} RED ingredients.
- Logistics: {logistics_roast}
- If it's greenwashing: Roast them ruthlessly.
- Keep it under 25 words.
"""

# --- 1. VISION (Llama 4 Scout) ---
async def extract_text_from_image(image_file):
    print("--- Vision: Using Groq Llama 4 Scout ---")
    image_data = await image_file.read()
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    # Updated to ask for Origin Info
    prompt = """
    Extract:
    1. Ingredients list.
    2. Claims (e.g. 'Natural').
    3. Origin/Made In text (e.g. 'Made in Brazil').
    Return ONLY raw JSON: {'ingredients': [], 'claims': [], 'origin_text': "..."}
    """
    
    try:
        completion = groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"!!! VISION ERROR: {e}")
        return {"ingredients": [], "claims": ["Error reading image"], "origin_text": "Unknown"}

# --- 2. LOGISTICS ---
async def analyze_logistics(origin_text):
    if not origin_text or origin_text == "Unknown":
        return {"origin": "Unknown", "is_local": False, "roast": "Origin hidden, suspicious."}
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": LOGISTICS_PROMPT}, {"role": "user", "content": f"Origin Text: {origin_text}"}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except:
        return {"origin": "Unknown", "is_local": False, "roast": "Logistics AI unavailable."}

# --- 3. ANALYZERS ---
async def analyze_ingredients_parallel(data):
    ingredients = data.get("ingredients", [])
    claims = data.get("claims", [])
    origin_text = data.get("origin_text", "Unknown")
    all_items = ingredients + claims
    
    if not all_items: return [], {}, "No ingredients found."

    text_input = f"Analyze: {all_items}"
    
    # Run Scientist, Critic, AND Logistics in parallel
    task1 = asyncio.to_thread(call_ai_model, "llama-3.3-70b-versatile", text_input, all_items)
    task2 = asyncio.to_thread(call_ai_model, "llama-3.1-8b-instant", text_input, all_items)
    task3 = analyze_logistics(origin_text)
    
    # Wait for all 3
    results = await asyncio.gather(task1, task2, task3)
    result_a, result_b, logistics_data = results[0], results[1], results[2]
    
    final_results = await merge_and_judge(all_items, result_a, result_b)
    
    summary = await generate_witty_summary(final_results, logistics_data)
    
    return final_results, logistics_data, summary

def call_ai_model(model_name, content, all_items):
    try:
        completion = groq_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": ANALYZER_PROMPT}, {"role": "user", "content": content}],
            temperature=0, 
            response_format={"type": "json_object"}
        )
        analysis_dict = json.loads(completion.choices[0].message.content)
        
        report = {}
        for item in all_items:
            found_data = None
            for key, val in analysis_dict.items():
                if item.lower() in key.lower() or key.lower() in item.lower():
                    found_data = val
                    break
            
            if found_data:
                report[item] = {
                    "status": found_data.get("status", "YELLOW"),
                    "explanation": found_data.get("explanation", "Analyzed")
                }
        return report
    except Exception as e: 
        print(f"{model_name} Error: {e}")
        return {}

# --- 4. CONSENSUS ---
async def merge_and_judge(all_items, analysis_a, analysis_b):
    final_report = []
    for item in all_items:
        a = analysis_a.get(item) 
        b = analysis_b.get(item) 
        
        if not a: a = b
        if not b: b = a
        if not a: continue 

        if a['status'] == b['status']:
            final_report.append({"name": item, "status": a['status'], "explanation": a['explanation'], "consensus": True})
        else:
            ruling = await call_tiebreaker(item, a, b)
            final_report.append({"name": item, "status": ruling['final_status'], "explanation": ruling['final_explanation'], "consensus": False})
    return final_report

async def call_tiebreaker(item, a, b):
    prompt = TIEBREAKER_PROMPT.format(item=item, status_a=a['status'], status_b=b['status'])
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except: 
        return {"final_status": "YELLOW", "final_explanation": "Judge unavailable."}

# --- 5. SUMMARY ---
async def generate_witty_summary(final_results, logistics_data):
    if not final_results: return "I couldn't read the label."
    
    # Count bad ingredients for context
    bad_count = sum(1 for r in final_results if r['status'] == 'RED')
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": WITTY_SUMMARY_PROMPT.format(bad_count=bad_count, logistics_roast=logistics_data.get('roast', ''))}, 
                {"role": "user", "content": "Generate summary."}
            ],
            temperature=0.7 
        )
        return completion.choices[0].message.content.strip()
    except:
        return "The AI is speechless."