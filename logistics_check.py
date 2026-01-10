
import os
import json
import asyncio
from groq import Groq

# Educational Comment:
# This is the "Logistics Detective". It specializes in Geography.
# Its job is to find out where a product came from and calculate its "Food Miles" to Dubai.
# Long distance = High Carbon Footprint = Bad Score.

def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

LOGISTICS_PROMPT = """
### ROLE
You are the "Logistics Detective" for EcoScan. Your goal is to identify the origin of a product and penalize or reward it based on its "Food Miles" to Dubai, UAE.

### INSTRUCTIONS
1. **Locate Origin:** Scan the extracted text for phrases like "Made in...", "Product of...", or "Distributed from...".
2. **Dubai Distance Calculation:**
    - **Local UAE (+10 Bonus):** If origin is UAE (e.g., Al Ain Farms, Digdaga, Sharjah, Bustanica), award the "Local Hero" bonus.
    - **Regional (< 2,000km):** (GCC countries) No penalty, minor sustainability boost.
    - **International (2,000km - 8,000km):** Dock 5 points.
    - **Global Long-Haul (> 8,000km):** (e.g., Chile, USA, Brazil) Dock 15 points.
3. **Greenwash Check:** Compare the origin with any "Eco-friendly" or "Sustainable" claims. 
    - *Flag:* If a product claims to be "Climate Neutral" but traveled 12,000km from South America, mark as "High Greenwash Risk."
4. **The Sarcastic Output:** Generate a 1-sentence "Distance Roast."

### OUTPUT FORMAT (JSON)
{
  "origin_identified": "[Country Name]",
  "distance_score_adj": [-15 to +10],
  "is_local": [true/false],
  "roast_line": "[Sarcastic comment about its travel miles]"
}
"""

async def analyze_logistics(origin_text):
    """
    Sends the origin text to Llama-3.3 to figure out the food miles.
    """
    client = get_client()
    
    if not origin_text or origin_text == "Unknown":
        return {
            "origin_identified": "Unknown", 
            "distance_score_adj": 0, 
            "is_local": False, 
            "roast_line": "Origin is a mystery."
        }
        
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": LOGISTICS_PROMPT}, {"role": "user", "content": f"Product Text: {origin_text}"}],
            temperature=0, # Strict reasoning
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Logistics Error: {e}")
        return {"origin_identified": "Error", "distance_score_adj": 0, "is_local": False, "roast_line": "Logistics AI malfunction."}