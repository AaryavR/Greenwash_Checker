
import os
import json
import asyncio
from groq import Groq

# Educational Comment:
# This is the "Judge". It calculates a detailed Scorecard (0-100) based on weighted criteria.
# The weights change depending on the category!
# - Food: Cares more about Ingredients (Health/Environment).
# - Cosmetics: Cares more about Toxicity.
# - Cleaning: Cares more about biodegradable packaging.

def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"), default_headers={"Groq-Model-Version": "latest"})

SCORING_PROMPT = """
You are the EcoScan Scoring Judge. 
Calculate a Sustainability Score and Audit Ingredients for a: {category}.

### 1. CONTEXTUAL AUDIT RULES
- **IF FOOD**: Flag Palm Oil (Deforestation), Beef/Dairy (High Carbon), Artificial Dyes (Health), Plastic Packaging.
- **IF COSMETIC**: Flag Parabens/Phthalates (Endocrine Disruptors), Microbeads (Ocean Plastic), Animal Testing.
- **IF CLEANING**: Flag Phosphates (Algal Blooms), Chlorine Bleach (Toxicity).

### 2. SCORING WEIGHTS
- Environment (40%)
- Social (30%)
- Governance (30%)

### 3. OUTPUT JSON (Strict Format)
{{
    "environment_score": [0-100],
    "social_score": [0-100],
    "governance_score": [0-100],
    "final_total_score": [0-100],
    "breakdown_notes": ["Note 1", "Note 2"],
    "ingredient_breakdown": [
        {{
            "name": "Ingredient Name",
            "status": "RED/YELLOW/GREEN",
            "explanation": "Ruthless explanation of impact (Health/Env).",
            "alternative": "Sustainable switch (e.g. 'Shea Butter' instead of 'Petrolatum')"
        }}
    ]
}}

INPUT DATA:
- Ingredients: {ingredients}
- Claims: {claims}
- Origin: {origin}
"""

async def calculate_scores(category, ingredients, claims, origin):
    client = get_client()
    
    # Format the prompt
    prompt = SCORING_PROMPT.format(
        category=category, 
        ingredients=str(ingredients), 
        claims=str(claims), 
        origin=origin
    )
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Scoring Error: {e}")
        # Default average score to prevent crash
        return {
            "environment_score": 50, "social_score": 50, "governance_score": 50, "final_total_score": 50, 
            "breakdown_notes": ["Error calculating score."]
        }