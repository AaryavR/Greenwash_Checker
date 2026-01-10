import streamlit as st
import asyncio
from dotenv import load_dotenv
import backend

# Load environment variables
load_dotenv()

# --- 1. UI CONFIGURATION ---
st.set_page_config(
    page_title="EcoScan",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed" # Hide default sidebar
)

# --- CUSTOM CSS (Mobile App Layout) ---
st.markdown("""
<style>
    /* 1. APP THEME */
    .stApp { background-color: #0f1715; color: #e2e8f0; padding-bottom: 120px; } /* Padding for bottom bar */
    h1, h2, h3 { color: #10b981 !important; font-family: 'Courier New', monospace; }
    
    /* 2. HIDE DEFAULT ELEMENTS */
    [data-testid="stSidebar"] { display: none; } /* Hide the actual sidebar */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* 3. FLOATING BOTTOM DOCK */
    .bottom-dock {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background: #1a2624; /* Dark Bar Background */
        border-top: 1px solid #10b981;
        padding: 10px 20px;
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
        box-shadow: 0 -5px 20px rgba(0,0,0,0.5);
    }

    /* 4. TRANSFORM FILE UPLOADER INTO A BUTTON */
    /* This targets the specific widget container we will place at the bottom */
    div.stFileUploader {
        position: fixed;
        bottom: 15px;
        left: 50%;
        transform: translateX(-50%);
        width: 80px; /* Small width for icon */
        height: 80px;
        z-index: 10000;
        opacity: 0.9;
    }

    /* Style the inner button to look like a Shutter/Scan Icon */
    div.stFileUploader > label { display: none; } /* Hide label text */
    div.stFileUploader button {
        background: #10b981 !important; /* Green Circle */
        color: white !important;
        border: 4px solid #0f1715 !important;
        border-radius: 50% !important;
        width: 70px !important;
        height: 70px !important;
        font-size: 30px !important;
        line-height: 70px !important;
        padding: 0 !important;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.6);
        transition: transform 0.1s;
    }
    div.stFileUploader button:active {
        transform: scale(0.9);
    }
    
    /* Hide the 'Drag and Drop' text mess */
    div.stFileUploader section {
        background: transparent !important;
        border: none !important;
    }
    div.stFileUploader .uploadedFile { display: none; } /* Hide file name after upload */

    /* 5. DASHBOARD STYLING */
    .legend-box {
        background-color: #1a2624;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #334155;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
    .badge-red { background-color: #ef4444; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-yellow { background-color: #f59e0b; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-green { background-color: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. MAIN HEADER ---
st.title("EcoScan v2.1 🌐")
st.caption("Universal Multi-Category Product Auditor")

# --- 3. THE FLOATING UPLOADER (THE "ICON") ---
# We place this here, but CSS moves it to the bottom center
uploaded_file = st.file_uploader("Scan", type=["jpg", "png", "jpeg"], label_visibility="collapsed")

# Inject a fake "Dock" background for visuals
st.markdown('<div class="bottom-dock"></div>', unsafe_allow_html=True)


# --- 4. APP LOGIC ---

# LANDING STATE (When no file)
if uploaded_file is None:
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; opacity: 0.7;">
        <h3>Ready to Audit</h3>
        <p>Tap the Green Button below to scan a label.</p>
        <br>
    </div>
    """, unsafe_allow_html=True)

# ANALYSIS STATE (When file exists)
else:
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
        <span style="color:#f59e0b">🟡 <strong>YELLOW (Caution/Vague):</strong></span> Unregulated terms or moderate impact.<br>
        <span style="color:#10b981">🟢 <strong>GREEN (Safe/Verified):</strong></span> Certified sustainable.
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
        st.info("No marketing claims detected.")
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
            alternative = item.get("alternative", "None.")
            if status == "RED": icon = "🔴"
            elif status == "GREEN": icon = "🟢"
            else: icon = "🟡"
            with st.expander(f"{icon} {name}"):
                st.markdown(f"**Impact:** {explanation}")
                if alternative and alternative != "None":
                    st.success(f"**Better Choice:** {alternative}")
    
    # Extra spacing for bottom bar
    st.write("<br><br><br>", unsafe_allow_html=True)