"""
ChemCheck - Production-ready FastAPI Backend for Product Analysis
"""
import os
import re
import json
import traceback
from typing import Optional, List
from decimal import Decimal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from pydantic import BaseModel, Field, field_validator
from supabase import create_client, Client
from groq import Groq
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="ChemCheck API",
    description="Universal Multi-Category Product Auditor",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CONFIGURATION ====================
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Groq
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Initialize Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    gemini_model = None

# Initialize Geopy with required user_agent
geolocator = Nominatim(user_agent="ChemCheckApp/1.0")

# HTTP client headers for Open Food Facts
OFF_HEADERS = {"User-Agent": "ChemCheckApp/1.0 (contact@example.com)"}
HTTP_TIMEOUT = 3.0

# Target location for food miles calculation
DUBAI_COORDS = (25.2048, 55.2708)  # Dubai, UAE
FOOD_MILES_THRESHOLD = 6437  # ~4000 miles in km

# ==================== DATA MODELS ====================

class AnalyzeRequest(BaseModel):
    """Request model for product analysis."""
    barcode: Optional[str] = None
    front_text: Optional[str] = Field(None, description="Text from front of product label")
    back_text: Optional[str] = Field(None, description="Text from back of product label (ingredients, etc.)")
    origin_country: Optional[str] = Field(None, description="Country of origin")
    user_country: str = Field(..., description="User's location country for food miles calculation")
    language: str = Field(default="English", description="Language for localization")

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        supported = ['English', 'Arabic', 'Spanish', 'French', 'German', 'Chinese']
        if v not in supported:
            return 'English'
        return v


class ClaimAnalysis(BaseModel):
    """Individual claim analysis result."""
    claim: str = Field(..., description="The marketing claim analyzed")
    status: str = Field(..., pattern="^(Green|Yellow|Red)$", description="Status: Green, Yellow, or Red")
    explanation: str = Field(..., description="Explanation for the status")


class IngredientAnalysis(BaseModel):
    """Individual ingredient analysis result."""
    ingredient: str = Field(..., description="Ingredient name")
    status: str = Field(..., pattern="^(Green|Yellow|Red)$", description="Status: Green, Yellow, or Red")
    explanation: str = Field(..., description="Explanation for the status")


class AlternativeProduct(BaseModel):
    """Alternative product suggestion."""
    product_name: str = Field(..., description="Name of the alternative product")
    better_ingredients_summary: str = Field(..., description="Why this product is better")


class AnalyzeResponse(BaseModel):
    """Response model for product analysis."""
    final_score: int = Field(..., ge=0, le=100, description="Final sustainability score (0-100)")
    base_health_score: int = Field(..., ge=0, le=100, description="Base health score before penalties")
    food_miles_penalty: int = Field(..., ge=0, le=10, description="Penalty for long-distance shipping")
    overall_summary: str = Field(..., description="Localized roast/summary")
    claims_analysis: List[ClaimAnalysis] = Field(default_factory=list, description="Analysis of marketing claims")
    ingredients_analysis: List[IngredientAnalysis] = Field(default_factory=list, description="Analysis of ingredients")
    alternatives: List[AlternativeProduct] = Field(default_factory=list, description="Better alternative products")


# ==================== UTILITY FUNCTIONS ====================

def strip_markdown_json(raw_text: str) -> str:
    """
    Strip markdown formatting from LLM output before JSON parsing.
    Removes markdown code blocks (```json, ```) and extra whitespace.
    """
    if not raw_text:
        return ""

    # Remove markdown code blocks
    text = raw_text.strip()

    # Remove ```json or ``` at the start
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    # Remove ``` at the end
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ==================== EXTERNAL ASYNC FUNCTIONS ====================

async def fetch_product_from_off(barcode: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch product name and ingredients from Open Food Facts.
    Returns (product_name, ingredients_text) tuple or (None, None) if not found.
    """
    if not barcode:
        return None, None

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=OFF_HEADERS) as client:
        try:
            product_response = await client.get(
                f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
            )
            if product_response.status_code == 200:
                product_data = product_response.json()
                if product_data.get("product"):
                    product = product_data["product"]

                    # Try multiple fields for product name
                    name = (
                        product.get("product_name")
                        or product.get("product_name_en")
                        or product.get("generic_name")
                        or product.get("code")
                    )

                    # Try multiple fields for ingredients text
                    ingredients = (
                        product.get("ingredients_text")
                        or product.get("ingredients_text_en")
                        or product.get("ingredients_text_de")
                        or product.get("ingredients_text_fr")
                        or product.get("ingredients_text_es")
                    )

                    # Fallback: join ingredients_tags if available
                    if not ingredients and product.get("ingredients_tags"):
                        ingredients_tags = product["ingredients_tags"]
                        if isinstance(ingredients_tags, list):
                            # Remove language prefixes (e.g., "en:sugar" -> "sugar")
                            cleaned_tags = [tag.split(":", 1)[-1] if ":" in tag else tag for tag in ingredients_tags]
                            ingredients = ", ".join(cleaned_tags)
                        elif isinstance(ingredients_tags, str):
                            ingredients = ingredients_tags

                    return name, ingredients
        except Exception:
            pass

    return None, None


async def fetch_alternatives(barcode: Optional[str]) -> tuple[List[AlternativeProduct], Optional[str]]:
    """
    Fetch alternative products from Open Food Facts.
    Returns (alternatives_list, product_category).
    """
    if not barcode:
        return [], None

    category = None

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=OFF_HEADERS) as client:
        # First, fetch product to get category
        try:
            product_response = await client.get(
                f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
            )
            if product_response.status_code == 200:
                product_data = product_response.json()
                if product_data.get("product"):
                    category = (
                        product_data["product"].get("categories_tags")
                        or product_data["product"].get("category_tag")
                    )
                    if isinstance(category, list) and category:
                        category = category[0].replace("en:", "") if category else None
                    elif isinstance(category, str):
                        category = category.replace("en:", "")
        except Exception:
            pass

        # Then search for alternatives if we have a category, or search generally
        if category:
            search_params = {
                "search_terms": category,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 2,
                "sort_by": "unique_scans_n",
            }
        else:
            search_params = {
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 2,
                "sort_by": "unique_scans_n",
            }

        try:
            search_response = await client.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params=search_params
            )
            if search_response.status_code == 200:
                search_data = search_response.json()
                products = search_data.get("products", [])

                alternatives = []
                for product in products[:2]:
                    name = product.get("product_name") or product.get("code", "Unknown Product")
                    ingredients = product.get("ingredients_text", "") or product.get("ingredients_text_en", "")

                    alternatives.append(
                        AlternativeProduct(
                            product_name=name,
                            better_ingredients_summary=f"Alternative with ingredients: {ingredients[:200]}..."
                        )
                    )

                return alternatives, category
        except Exception:
            pass

    return [], category


def calculate_food_miles_penalty(origin_country: Optional[str], user_country: str) -> int:
    """
    Calculate food miles penalty based on distance from origin to user's location.
    Returns 10 points penalty if distance > 4000 miles.
    """
    if not origin_country:
        return 0

    try:
        # Geocode origin country
        origin_location = geolocator.geocode(origin_country)
        if not origin_location:
            return 0

        # Geocode user country
        user_location = geolocator.geocode(user_country)
        if not user_location:
            return 0

        origin_coords = (origin_location.latitude, origin_location.longitude)
        user_coords = (user_location.latitude, user_location.longitude)

        # Calculate distance in km
        distance_km = geodesic(origin_coords, user_coords).kilometers

        # Convert to miles
        distance_miles = distance_km * 0.621371

        if distance_miles > FOOD_MILES_THRESHOLD:
            return 10

        return 0
    except Exception:
        return 0


async def check_banned_additives(text: str) -> tuple[int, List[str]]:
    """
    Check Supabase 'banned_additives' table for text matches.
    Returns (match_count, matched_additives).
    """
    try:
        result = supabase.table("banned_additives").select("*").execute()

        if not result.data:
            return 0, []

        matches = []
        text_lower = text.lower()

        for additive in result.data:
            additive_name = additive.get("name", "").lower()
            if additive_name and additive_name in text_lower:
                matches.append(additive.get("name", additive_name))

        return len(matches), matches
    except Exception:
        return 0, []


# ==================== LLM FUNCTIONS ====================

async def call_llm_analysis(
    front_text: str,
    back_text: str,
    banned_flags: List[str],
    language: str
) -> dict:
    """
    Call LLM for product analysis with Groq (primary) and Gemini fallback.
    Returns parsed JSON response.
    """
    system_prompt = f"""You are RedFlag, a product sustainability auditor. Analyze the product and return a valid JSON response with this exact structure:

{{
    "base_health_score": <int 0-100>,
    "overall_summary": "<witty localized summary in {language}>",
    "claims_analysis": [
        {{"claim": "<exact claim text>", "status": "Green|Yellow|Red", "explanation": "<why>"}}
    ],
    "ingredients_analysis": [
        {{"ingredient": "<name>", "status": "Green|Yellow|Red", "explanation": "<why>"}}
    ]
}}

Scoring Rules:
- Green: Safe, verified, certified sustainable
- Yellow: Caution, vague claims (e.g., "natural"), moderate impact
- Red: Toxic ingredients, false claims, harmful

Consider these banned/harmful additives found: {', '.join(banned_flags) if banned_flags else 'None'}
"""

    user_prompt = f"""Front label text: {front_text}
Back label text (ingredients/nutrition): {back_text}"""

    # Try Groq first
    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content
            cleaned_json = strip_markdown_json(raw_content)
            return json.loads(cleaned_json)
        except Exception as e:
            # Fall through to Gemini
            print(f"GROQ ERROR: {e}")

    # Fallback to Gemini
    if gemini_model:
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = gemini_model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    response_mime_type="application/json"
                )
            )

            raw_content = response.text
            cleaned_json = strip_markdown_json(raw_content)
            return json.loads(cleaned_json)
        except Exception as e:
            print(f"GEMINI ERROR: {e}")

    # Ultimate fallback
    return {
        "base_health_score": 50,
        "overall_summary": "Analysis unavailable - service temporarily down.",
        "claims_analysis": [],
        "ingredients_analysis": []
    }


# ==================== API ENDPOINT ====================

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_product(
    request: AnalyzeRequest,
    authorization: Optional[str] = Header(None)
) -> AnalyzeResponse:
    """
    Analyze a product for sustainability, health, and greenwashing.

    Args:
        request: Product data including barcode, label text, origin, and language
        authorization: Optional Bearer token for user authentication

    Returns:
        Comprehensive analysis with scores, summaries, and alternatives
    """
    # Step 1: Fetch product data from Open Food Facts if barcode provided
    product_name = "Manual Entry"
    off_front_text = None
    off_back_text = None

    if request.barcode:
        off_name, off_ingredients = await fetch_product_from_off(request.barcode)
        if off_name:
            product_name = off_name

        # If user provided empty texts but barcode exists, try to use OFF data
        if (not request.front_text or not request.back_text) and request.barcode:
            if off_ingredients:
                off_back_text = off_ingredients
                # For front text, we can use product name if available
                off_front_text = off_name or ""
            else:
                # Barcode found but no ingredients available - trigger fallback
                raise HTTPException(
                    status_code=404,
                    detail="Product found in Open Food Facts but no ingredients data available. Please scan the product label manually."
                )

    # Determine final front_text and back_text (prefer user input, fallback to OFF)
    front_text = request.front_text or off_front_text or ""
    back_text = request.back_text or off_back_text or ""

    # Step 2: Get user ID from authorization token if provided
    user_id = None
    print(f"Auth Header: {authorization}")  # Debug: Check if token arrives in Render logs
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            # Use Supabase to get user from token
            user_response = supabase.auth.get_user(token)
            if user_response and user_response.user:
                user_id = user_response.user.id
        except Exception as e:
            # If token validation fails, continue without user_id
            print(f"Token validation failed: {e}")

    # Step 3: Check Supabase for banned additives
    banned_count, banned_flags = await check_banned_additives(back_text)

    # Step 4: Calculate food miles penalty
    food_miles_penalty = calculate_food_miles_penalty(request.origin_country, request.user_country)

    # Step 5: Fetch alternatives (runs in parallel with LLM)
    alternatives_task = fetch_alternatives(request.barcode)

    # Step 6: Call LLM analysis
    llm_result = await call_llm_analysis(
        front_text=front_text,
        back_text=back_text,
        banned_flags=banned_flags,
        language=request.language
    )

    # Step 7: Get alternatives result
    alternatives, _ = await alternatives_task

    # Step 8: Calculate final score
    base_health_score = llm_result.get("base_health_score", 50)

    # Apply zero-tolerance policy for banned additives
    if banned_count > 0:
        final_score = 0
    else:
        final_score = max(0, base_health_score - food_miles_penalty)

    # Step 9: Build response Pydantic models first
    overall_summary = llm_result.get("overall_summary", "Analysis completed.")

    # Build Pydantic models for claims and ingredients
    claims_analysis_models = [
        ClaimAnalysis(**claim) for claim in llm_result.get("claims_analysis", [])
    ]
    ingredients_analysis_models = [
        IngredientAnalysis(**ingredient) for ingredient in llm_result.get("ingredients_analysis", [])
    ]

    # Step 10: Save to scan_history if user is authenticated
    if user_id:
        try:
            # Convert Pydantic models to dicts for Supabase JSONB column
            ingredients_analysis_dicts = [ing.model_dump() for ing in ingredients_analysis_models]

            supabase.table("scan_history").insert({
                "user_id": user_id,
                "product_name": product_name,
                "final_score": final_score,
                "overall_summary": overall_summary,
                "ingredients_analysis": ingredients_analysis_dicts
            }).execute()
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to save to scan_history: {e}")

    return AnalyzeResponse(
        final_score=final_score,
        base_health_score=base_health_score,
        food_miles_penalty=food_miles_penalty,
        overall_summary=overall_summary,
        claims_analysis=claims_analysis_models,
        ingredients_analysis=ingredients_analysis_models,
        alternatives=alternatives
    )


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "ChemCheck API",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    status = {
        "service": "ChemCheck API",
        "status": "healthy",
        "dependencies": {}
    }

    # Check Supabase
    try:
        supabase.table("banned_additives").select("count").limit(1).execute()
        status["dependencies"]["supabase"] = "connected"
    except Exception:
        status["dependencies"]["supabase"] = "disconnected"
        status["status"] = "degraded"

    # Check Groq
    status["dependencies"]["groq"] = "configured" if groq_client else "not_configured"

    # Check Gemini
    status["dependencies"]["gemini"] = "configured" if gemini_model else "not_configured"

    return status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
