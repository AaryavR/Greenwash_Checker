import os
import json
import base64
import asyncio
from groq import Groq

# --- CONFIG ---
def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return None
    return Groq(api_key=api_key)

# --- PROMPTS ---
ANALYZER_PROMPT = """
You are a ruthless Environmental Scientist. Detect Greenwashing.
PRIORITY 1: PLANETARY HEALTH
- RED: High Carbon (Beef, Dairy), Deforestation (Palm Oil), Microplastics.
- YELLOW: High Water (Almonds), Imported.
- GREEN: Plant-based, Organic, Locally sourced.
Output strictly valid JSON.
"""

LOGISTICS_PROMPT = """
You are a Logistics Detective.
1. Identify the Country of Origin.
2. Calculate distance to Dubai, UAE.
   - Local (UAE): Bonus.
   - Regional (GCC): Neutral.
   - International (>2000km): Penalty.
3. Roast the food miles.
Output JSON: { "origin_identified": "Country", "distance_score_adj": -5, "is_local": false, "roast_line": "Sarcastic comment." }
"""


SCORING_PROMPT = """
You are the EcoScan Scoring Judge. 
Calculate a Sustainability Score (0-100).
Weights: Environment (40%), Social (30%), Governance (30%).
Output JSON:
{{
    "environment_score": 0,
    "social_score": 0,
    "governance_score": 0,
    "final_total_score": 0,
    "breakdown_notes": ["Note 1", "Note 2"],
    "ingredient_breakdown": [
        {{ "name": "Item", "status": "RED/YELLOW/GREEN", "explanation": "Impact", "alternative": "Switch" }}
    ]
}}
INPUT DATA: Ingredients: {ingredients}, Claims: {claims}, Origin: {origin}
"""

ROAST_PROMPT = """
You are a Sarcastic Environmental Activist. 
Generate a short Verdict based on score: {score}/100.
Category: {category}. Notes: {notes}.
Keep it under 25 words.
"""

# --- 1. VISION ENGINE ---
async def extract_data_from_image(image_file):
    client = get_client()
    image_bytes = image_file.getvalue()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """
    Extract:
    1. Product Category (e.g. Food, Cosmetic, Cleaning).
    2. Ingredients list.
    3. Claims (e.g. Natural).
    4. Origin/Made In.
    Return JSON: { "product_category": "...", "ingredients": [], "claims": [], "origin_info": "..." }
    """
    
    try:
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct", # The Working Model
            messages=[{
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        return {"claims": [f"Error reading image: {str(e)}"], "ingredients": [], "origin_info": "Unknown"}

# --- 2. CATEGORY ENGINE ---
def identify_category(text):
    if not text: return "Other"
    text = text.lower()
    if any(x in text for x in ["food", "drink", "snack"]): return "Food"
    if any(x in text for x in ["cosmetic", "skin", "soap"]): return "Cosmetic"
    if any(x in text for x in ["clean", "detergent"]): return "Cleaning"
    return "Other"

# --- 3. SCORING ENGINE ---
async def calculate_scores(category, ingredients, claims, origin):
    client = get_client()
    prompt = SCORING_PROMPT.format(category=category, ingredients=str(ingredients), claims=str(claims), origin=origin)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except:
        return {"final_total_score": 50, "breakdown_notes": ["Scoring Failed"]}

# --- 4. LOGISTICS ENGINE ---
async def analyze_logistics(origin_text):
    client = get_client()
    if not origin_text or origin_text == "Unknown":
        return {"origin_identified": "Unknown", "distance_score_adj": 0, "roast_line": "Origin hidden."}
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": LOGISTICS_PROMPT}, {"role": "user", "content": f"Origin: {origin_text}"}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except:
        return {"origin_identified": "Error", "roast_line": "Logistics AI unavailable."}

# --- 5. SARCASM ENGINE ---
async def get_verdict(score, category, notes):
    client = get_client()
    prompt = ROAST_PROMPT.format(score=score, category=category, notes=str(notes))
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        return completion.choices[0].message.content.strip()
    except:
        return "System Malfunction."