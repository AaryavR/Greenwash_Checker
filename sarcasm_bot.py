
import os
from groq import Groq

# Educational Comment:
# This is the "Sarcastic Persona". It doesn't do analysis. 
# It takes the numbers from the Judge and turns them into a "Roast" or "Praise".

def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"), default_headers={"Groq-Model-Version": "latest"})

ROAST_PROMPT = """
You are a Sarcastic Environmental Activist. 
Generate a short Verdict based on this score: {score}/100.
Category: {category}.
Notes: {notes}

- Score < 40: Brutal Roast. Destroy them.
- Score 40-70: Skeptical. Point out the mediocrity.
- Score > 70: Impressed (but still cool/edgy).

Keep it under 25 words.
"""

async def get_verdict(score, category, notes):
    client = get_client()
    
    prompt = ROAST_PROMPT.format(score=score, category=category, notes=str(notes))
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8 # High creativity for sarcasm
        )
        return completion.choices[0].message.content.strip()
    except:
        return "I'm too disgusted to speak."