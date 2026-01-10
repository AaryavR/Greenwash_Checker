
import os
import json
import asyncio
from groq import Groq

# This module is the "Brain" of the operation. It runs a debate between two AI agents:
# 1. The Scientist (Strict, looks for facts)
# 2. The Critic (Skeptical, looks for loopholes)
# If they disagree, a Judge steps in. This is called "Multi-Agent Consensus". 

def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

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
AI 1 (Scientist): {status_a}
AI 2 (Critic): {status_b}
Output JSON: {{ "final_status": "RED/YELLOW/GREEN", "final_explanation": "Ruling" }}
"""

WITTY_SUMMARY_PROMPT = """
You are a sarcastic environmental activist. 
Write a ONE-LINE summary of this product.
- If it's greenwashing: Roast them ruthlessly.
- If it's sustainable: Be impressed.
- Context: The product traveled {miles} (Status: {logistics_status}).
- Keep it under 20 words.
"""

def call_ai_sync(model_name, content, all_items):
    """
    Helper function to call AI synchronously (runs within a thread).
    """
    client = get_client()
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": ANALYZER_PROMPT}, {"role": "user", "content": content}],
            temperature=0, 
            response_format={"type": "json_object"}
        )
        analysis_dict = json.loads(completion.choices[0].message.content)
        
        # Map back to original items to ensure keys match
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

async def call_tiebreaker(item, a, b):
    """Calls the Judge AI if Scientist and Critic disagree."""
    client = get_client()
    prompt = TIEBREAKER_PROMPT.format(item=item, status_a=a['status'], status_b=b['status'])
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Judge Error: {e}")
        return {"final_status": "YELLOW", "final_explanation": "Judge unavailable."}

async def merge_and_judge(all_items, analysis_a, analysis_b):
    """Compares the two reports and resolves conflicts."""
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

async def run_greenwash_audit(ingredients, claims):
    """
    Main function to orchestrate the debate.
    """
    all_items = ingredients + claims
    if not all_items: return [], "No items to analyze."

    text_input = f"Analyze: {all_items}"
    
    # Run Scientist and Critic in parallel threads
    task1 = asyncio.to_thread(call_ai_sync, "llama-3.3-70b-versatile", text_input, all_items)
    task2 = asyncio.to_thread(call_ai_sync, "llama-3.1-8b-instant", text_input, all_items)
    
    result_a, result_b = await asyncio.gather(task1, task2)
    
    final_results = await merge_and_judge(all_items, result_a, result_b)
    return final_results

async def generate_final_verdict(final_results, logistics_data):
    """Generates the witty summary using both ingredients and logistics context."""
    client = get_client()
    if not final_results: return "I couldn't read the label."
    
    # Prepare context for the writer
    context_str = str([f"{r['name']}: {r['status']}" for r in final_results])
    miles_context = logistics_data.get("roast_line", "Unknown origin")
    logistics_status = "Local" if logistics_data.get("is_local") else "Imported"
    
    # Format the prompt
    final_prompt = WITTY_SUMMARY_PROMPT.format(miles=miles_context, logistics_status=logistics_status)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": final_prompt}, {"role": "user", "content": f"Data: {context_str}"}],
            temperature=0.7 
        )
        return completion.choices[0].message.content.strip()
    except:
        return "The AI is speechless."