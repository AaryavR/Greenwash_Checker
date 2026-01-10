import streamlit as st
import asyncio
from dotenv import load_dotenv
import backend

# Load environment variables
load_dotenv()

# --- 1. UI CONFIGURATION ---
st.set_page_config(
    page_title="EcoScan | Multi-Category Auditor",
    page_icon="🌿",
    layout="wide"
)

# --- CUSTOM CSS (The UI Magic) ---
st.markdown("""
<style>
    /* 1. APP THEME */
    .stApp { background-color: #0f1715; color: #e2e8f0; }
    h1, h2, h3 { color: #10b981 !important; font-family: 'Courier New', monospace; }
    
    /* 2. SIDEBAR STYLING (Bottom Dock) */
    [data-testid="stSidebar"] {
        background-color: #0f1715;
        border-right: 1px solid #1a2624;
    }
    
    /* This flex trick pushes the uploader to the bottom of the sidebar */
    [data-testid="stSidebarUserContent"] {
        display: flex;
        flex-direction: column;
        justify-content: flex-end; 
        height: 85vh; /* Force height to push items down */
    }

    /* 3. FILE UPLOADER STYLING (Minimalist Icon Look) */
    [data-testid="stFileUploader"] {
        width: 100%;
        margin-bottom: 20px;
    }
    
    /* Style the internal button of the uploader */
    [data-testid="stFileUploader"] button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border: none;
        border-radius: 50px; /* Rounded pill shape */
        padding: 15px 20px;
        font-weight: bold;
        width: 100%;
        transition: transform 0.2s;
    }
    [data-testid="stFileUploader"] button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);
    }
    
    /* Hide the "Drag and drop file here" text to make it clean */
    [data-testid="stFileUploader"] .uploadedFile {
        display: none;
    }
    [data-testid="stFileUploader"] small {
        display: none;
    }

    /* 4. DASHBOARD ELEMENTS */
    div[data-testid="stMetricValue"] { font-family: 'Courier New', monospace; color: #10b981; }
    .streamlit-expanderHeader { background-color: #1a2624; color: #e2e8f0; }
    
    /* Custom Badges */
    .badge-red { background-color: #ef4444; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-yellow { background-color: #f59e0b; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-green { background-color: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    
    .legend-box {
        background-color: #1a2624;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #334155;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR (The "Icon on Bottom") ---
with st.sidebar:
    # We add a title at the top, but the uploader will be pushed to bottom by CSS
    st.markdown("### ⚙️ EcoScan Controls")
    st.info("Supported: Food, Cosmetics, Cleaning Supplies")
    
    # The Uploader (Pushed to bottom by CSS flex-end)
    st.markdown("---") # Divider line
    uploaded_file = st.file_uploader("📷 Scan Product Label", type=["jpg", "png", "jpeg"], label_visibility="collapsed")


# --- 3. MAIN APP LOGIC ---
st.title("EcoScan v2.1 🌐")
st.caption("Universal Multi-Category Product Auditor")

# Trigger Logic only if file is uploaded
if uploaded_file is not None:
    # Automatically show a spinner and run logic once file is there
    # (No need for extra "Initiate" button anymore, makes it smoother like an app)
    
    # --- PHASE 1: VISION & CATEGORY ---
    with st.status("Analyzing Visual Data...", expanded=True) as status:
        st.write("📸 Extracting features...")
        data = asyncio.run(backend.extract_data_from_image(uploaded_file))
        
        claims_list = data.get("claims", [])
        if claims_list and isinstance(claims_list[0], str) and claims_list[0].startswith("Error"):
            status.update(label="Scanning Failed", state="error")
            st.error(claims_list[0])
            st.stop()

        raw_category = data.get("product_category", "Unknown")
        category = backend.identify_category(raw_category)
        st.write(f"🏷️ Identified Category: **{category}**")
        
        ingredients = data.get("ingredients", [])
        claims = data.get("claims", [])
        origin = data.get("origin_info", "Unknown")
        
        status.update(label="Visual Analysis Complete", state="complete")

    # --- PHASE 2: SCORING & LOGISTICS ---
    with st.spinner("Running Deep Audit..."):
        async def run_calculations():
            task_score = backend.calculate_scores(category, ingredients, claims, origin)
            task_logistics = backend.analyze_logistics(origin)
            return await asyncio.gather(task_score, task_logistics)

        scores, logistics = asyncio.run(run_calculations())
        verdict = asyncio.run(backend.get_verdict(scores.get('final_total_score', 50), category, scores.get('breakdown_notes', [])))

    # --- PHASE 3: DASHBOARD DISPLAY ---
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1: st.subheader(f"VERDICT: {verdict}")
    with col2: st.metric("Total Score", f"{scores.get('final_total_score', 0)}/100")
    
    # RATING LEGEND
    st.markdown("""
    <div class="legend-box">
        <strong>🚦 RATING GUIDE:</strong><br>
        <span style="color:#ef4444">🔴 <strong>RED (Hazard/False):</strong></span> Toxic ingredients or outright lies.<br>
        <span style="color:#f59e0b">🟡 <strong>YELLOW (Caution/Vague):</strong></span> Unregulated terms (e.g. "Natural") or moderate impact.<br>
        <span style="color:#10b981">🟢 <strong>GREEN (Safe/Verified):</strong></span> Certified sustainable or beneficial.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📊 Sustainability Dashboard")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("🌍 Environment", scores.get('environment_score', 0))
        st.progress(scores.get('environment_score', 0) / 100)
    with m2:
        st.metric("🤝 Social", scores.get('social_score', 0))
        st.progress(scores.get('social_score', 0) / 100)
    with m3:
        st.metric("⚖️ Governance", scores.get('governance_score', 0))
        st.progress(scores.get('governance_score', 0) / 100)
        
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📍 Logistics Intel")
        st.write(f"**Origin:** {logistics.get('origin_identified', 'Unknown')}")
        st.write(f"*{logistics.get('roast_line')}*")
        st.metric("Food Miles Penalty", f"{logistics.get('distance_score_adj', 0)} pts")
        
    with c2:
        st.subheader("📝 Audit Notes")
        for note in scores.get("breakdown_notes", []):
            st.write(f"- {note}")

    # --- CLAIMS SECTION ---
    st.divider()
    st.subheader("📢 Claims Intel")
    claims_data = scores.get("claims_breakdown", [])
    
    if not claims_data:
        st.info("No marketing claims detected to analyze.")
    else:
        for item in claims_data:
            status = item.get("status", "YELLOW").upper()
            claim_text = item.get("claim", "Unknown Claim")
            verdict = item.get("verdict", "UNVERIFIED")
            explanation = item.get("explanation", "No details.")

            if status == "RED": icon = "🔴"
            elif status == "GREEN": icon = "🟢"
            else: icon = "🟡"

            with st.expander(f"{icon} Claim: \"{claim_text}\""):
                st.markdown(f"**Verdict:** {verdict}")
                st.write(f"**Analysis:** {explanation}")

    # --- INGREDIENTS SECTION ---
    st.divider()
    st.subheader("🧪 Ingredient Intel")
    
    ingredient_list = scores.get("ingredient_breakdown", [])
    if not ingredient_list:
        st.info("No detailed ingredient analysis returned.")
    else:
        for item in ingredient_list:
            status = item.get("status", "YELLOW").upper()
            name = item.get("name", "Unknown")
            explanation = item.get("explanation", "No details.")
            alternative = item.get("alternative", "None suggestion.")
            
            if status == "RED": icon = "🔴"
            elif status == "GREEN": icon = "🟢"
            else: icon = "🟡"
            
            with st.expander(f"{icon} {name}"):
                st.markdown(f"**Impact:** {explanation}")
                if alternative and alternative != "None":
                    st.success(f"**Better Choice:** {alternative}")

else:
    # Landing Page State
    st.markdown("### ⬅️ Ready to Scan")
    st.write("Use the camera button in the sidebar to begin.")