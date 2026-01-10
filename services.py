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

# BUG FIX: Double curly braces {{ }} around the JSON example so .format() ignores them
TIEBREAKER_PROMPT = """
Decide based on ENVIRONMENTAL IMPACT.
Item: {item}
AI 1 (Scientist): {status_a}
AI 2 (Critic): {status_b}
Output JSON: {{ "final_status": "RED/YELLOW/GREEN", "final_explanation": "Ruling" }}
"""

WITTY_SUMMARY_PROMPT = """
You are a sarcastic environmental activist. 
Write a ONE-LINE summary of this product based on these ingredients.
- If it's greenwashing: Roast them ruthlessly.
- If it's sustainable: Be impressed.
- Keep it under 20 words.
"""

# --- 1. VISION (Llama 4 Scout) ---
async def extract_text_from_image(image_file):
    print("--- Vision: Using Groq Llama 4 Scout ---")
    image_data = await image_file.read()
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    prompt = "Extract ingredients and Green claims. Return ONLY raw JSON: {'ingredients': [], 'claims': []}"
    
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
        return {"ingredients": [], "claims": ["Error reading image"]}

# --- 2. ANALYZERS ---
async def analyze_ingredients_parallel(data):
    ingredients = data.get("ingredients", [])
    claims = data.get("claims", [])
    all_items = ingredients + claims
    
    if not all_items: return [], "No ingredients found."

    text_input = f"Analyze: {all_items}"
    
    # Task 1: Llama 3.3 (Scientist)
    task1 = asyncio.to_thread(call_ai_model, "llama-3.3-70b-versatile", text_input, all_items)
    
    # Task 2: Llama 3.1 (Critic)
    task2 = asyncio.to_thread(call_ai_model, "llama-3.1-8b-instant", text_input, all_items)
    
    result_a, result_b = await asyncio.gather(task1, task2)
    
    final_results = await merge_and_judge(all_items, result_a, result_b)
    
    summary = await generate_witty_summary(final_results)
    return final_results, summary

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
            final_report.append({
                "name": item,
                "status": a['status'],
                "explanation": a['explanation'],
                "consensus": True 
            })
        else:
            print(f"CONFLICT on {item}: Scientist says {a['status']}, Critic says {b['status']}")
            ruling = await call_tiebreaker(item, a, b)
            final_report.append({
                "name": item,
                "status": ruling['final_status'],
                "explanation": ruling['final_explanation'],
                "consensus": False
            })
    return final_report

async def call_tiebreaker(item, a, b):
    # Judge is Llama 3.3
    # Double curly braces used in PROMPT variable, so .format() is safe now
    prompt = TIEBREAKER_PROMPT.format(item=item, status_a=a['status'], status_b=b['status'])
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Judge Error: {e}")
        return {"final_status": "YELLOW", "final_explanation": "Judge unavailable."}

# --- 4. SUMMARY ---
async def generate_witty_summary(final_results):
    if not final_results: return "I couldn't read the label."
    context = str([f"{r['name']}: {r['status']}" for r in final_results])
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": WITTY_SUMMARY_PROMPT}, {"role": "user", "content": f"Data: {context}"}],
            temperature=0.7 
        )
        return completion.choices[0].message.content.strip()
    except:
        return "The AI is speechless." 