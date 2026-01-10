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

# --- CUSTOM CSS (Cyberpunk Theme - No Layout Hacks) ---
st.markdown("""
<style>
    /* 1. APP THEME */
    .stApp { background-color: #0f1715; color: #e2e8f0; }
    h1, h2, h3 { color: #10b981 !important; font-family: 'Courier New', monospace; }
    
    /* 2. BUTTON STYLING */
    .stButton>button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: bold;
        height: 50px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.5);
        transform: scale(1.02);
    }
    
    /* 3. SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #0f1715;
        border-right: 1px solid #1a2624;
    }
    
    /* 4. DASHBOARD ELEMENTS */
    div[data-testid="stMetricValue"] { font-family: 'Courier New', monospace; color: #10b981; }
    .streamlit-expanderHeader { background-color: #1a2624; color: #e2e8f0; }
    
    /* Custom Badges */
    .badge-red { background-color: #ef4444; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-yellow { background-color: #f59e0b; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-green { background-color: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    
    /* Legend Box */
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

# --- 2. SIDEBAR (Standard Layout) ---
with st.sidebar:
    st.header("Input Feed")
    uploaded_file = st.file_uploader("Upload Product Label", type=["jpg", "png", "jpeg"])
    st.info("Supported: Food, Cosmetics, Cleaning Supplies")

# --- 3. MAIN APP LOGIC ---
st.title("EcoScan 🌐")
st.caption("Universal Multi-Category Product Auditor")

if uploaded_file is not None:
    if st.button("🚀 INITIATE AUDIT", use_container_width=True):
        
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
    st.markdown("### ⬅️ Waiting for Input...")
    st.write("Upload a product label to generate the Sustainability Dashboard.")