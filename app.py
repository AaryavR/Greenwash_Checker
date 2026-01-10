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
    layout="wide"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* 1. APP THEME */
    .stApp { background-color: #0f1715; color: #e2e8f0; }
    h1, h2, h3 { color: #10b981 !important; font-family: 'Courier New', monospace; }
    
    /* 2. CLEANER SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #0f1715;
        border-right: 1px solid #1a2624;
    }

    /* 3. PUSH UPLOADER TO BOTTOM OF SIDEBAR */
    /* We make the sidebar a flex container so we can push the button down */
    [data-testid="stSidebarUserContent"] {
        display: flex;
        flex-direction: column;
        height: 90vh; /* Use viewport height to space things out */
    }
    
    /* This class will be applied to a spacer div to push content down */
    .sidebar-spacer {
        flex-grow: 1;
    }

    /* 4. STYLE THE FILE UPLOADER AS A BUTTON */
    [data-testid="stFileUploader"] {
        width: 100%;
        padding-bottom: 20px;
    }
    
    /* Hide the annoying "Drag and drop file here" text and limit text */
    [data-testid="stFileUploader"] section {
        padding: 0;
    }
    [data-testid="stFileUploader"] div[role="button"] {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        width: 100%;
        margin: 0 auto;
        display: block;
    }
    /* Hide the small "Limit 200MB" text */
    [data-testid="stFileUploader"] small { display: none; }
    /* Hide the file list after upload to keep it clean */
    [data-testid="stFileUploader"] .uploadedFile { display: none; }

    /* 5. DASHBOARD STYLING */
    div[data-testid="stMetricValue"] { font-family: 'Courier New', monospace; color: #10b981; }
    .streamlit-expanderHeader { background-color: #1a2624; color: #e2e8f0; }
    
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

# --- 2. SIDEBAR LAYOUT ---
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    st.info("Supported: Food, Cosmetics, Cleaning Supplies")
    
    # SPACER: This invisible block pushes everything below it to the bottom
    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
    
    # THE UPLOADER (Now at the bottom)
    uploaded_file = st.file_uploader("📷 Scan Product", type=["jpg", "png", "jpeg"], label_visibility="collapsed")


# --- 3. MAIN APP LOGIC ---
st.title("EcoScan 🌐") # Removed "v2.1" as requested
st.caption("Universal Multi-Category Product Auditor")

# LANDING STATE
if uploaded_file is None:
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; opacity: 0.7;">
        <h3>Ready to Audit</h3>
        <p>Use the <b>Scan Product</b> button in the sidebar to begin.</p>
    </div>
    """, unsafe_allow_html=True)

# ANALYSIS STATE
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
            alternative = item.get("alternative", "None suggestion.")
            
            if status == "RED": icon = "🔴"
            elif status == "GREEN": icon = "🟢"
            else: icon = "🟡"
            
            with st.expander(f"{icon} {name}"):
                st.markdown(f"**Impact:** {explanation}")
                if alternative and alternative != "None":
                    st.success(f"**Better Choice:** {alternative}")