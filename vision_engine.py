
import os
import base64
import json
import traceback
from groq import Groq

# Educational Comment: 
# This module is the "Eyes" of the operation. It uses Computer Vision (Llama-4-Scout)
# to "look" at the image and turn pixels into meaningful text data that our other AI agents can read.

def get_groq_client():
    """Initializes and returns the Groq client securely."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("API Key missing! Check your .env file.")
    # Added default header for latest versioning as requested
    return Groq(api_key=api_key, default_headers={"Groq-Model-Version": "latest"})

async def extract_data_from_image(image_file):
    """
    Takes an uploaded image file, converts it to base64, and sends it to Llama-4-Scout.
    Returns a JSON object with 'ingredients', 'claims', and 'origin_info'.
    """
    client = get_groq_client()
    
    # 1. Prepare the image for the AI (Convert bytes to Base64 string)
    # AI models can't "see" raw files, they need a text string representation (Base64).
    image_bytes = image_file.getvalue() # Streamlit uses getvalue(), not read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    print("--- Vision: Scanning Image... ---")
    
    # 2. The Prompt (Instructions for the Eyes)
    # We ask for "origin_info" specifically for our Logistics Detective.
    prompt = """
    Analyze this product label. Extract:
    1. Product Category (e.g., 'Food', 'Cosmetic', 'Cleaning', 'Other').
    2. Ingredients list (full text).
    3. Marketing claims (e.g., '100% Natural', 'Sustainably Sourced').
    4. Origin/Made In information (e.g., 'Made in UAE', 'Product of Brazil').
    
    Return ONLY raw JSON in this format: 
    {
        "product_category": "Category Name",
        "ingredients": ["item1", "item2"], 
        "claims": ["claim1", "claim2"],
        "origin_info": "extracted text about origin"
    }
    """
    
    try:
        # 3. Call the Vision Model
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct", # Updated to Llama 4 Scout as requested
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            temperature=0, # Keep it factual
            response_format={"type": "json_object"}
        )
        
        # 4. Parse response
        return json.loads(completion.choices[0].message.content)
        
    except Exception as e:
        error_msg = f"!!! VISION ERROR: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        # Return the specific error in the structure so we can potentially see it in UI if we wanted
        return {"ingredients": [], "claims": [f"Error reading image: {str(e)}"], "origin_info": "Unknown"}