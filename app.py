import streamlit as st
import asyncio
from dotenv import load_dotenv

# Import the Consolidated Logic
import backend

# Load environment variables
load_dotenv()

# --- 1. UI CONFIGURATION (Cyberpunk Theme) ---
st.set_page_config(
    page_title="EcoScan | Multi-Category Auditor",
    page_icon="🌿",
    layout="wide"
)

# Custom CSS for that "Hacker" vibe
st.markdown("""
<style>
    .stApp { background-color: #0f1715; color: #e2e8f0; }
    h1, h2, h3 { color: #10b981 !important; font-family: 'Courier New', monospace; }
    .stButton>button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white; border: none; border-radius: 12px; font-weight: bold; height: 50px;
    }
    .stButton>button:hover { box-shadow: 0 0 15px rgba(16, 185, 129, 0.5); }
    div[data-testid="stMetricValue"] { font-family: 'Courier New', monospace; color: #10b981; }
    .streamlit-expanderHeader { background-color: #1a2624; color: #e2e8f0; }
    .badge-red { background-color: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    .badge-yellow { background-color: #f59e0b; color: black; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    .badge-green { background-color: #10b981; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. MAIN APP LOGIC ---
st.title("EcoScan v2.1 🌐")
st.caption("Universal Multi-Category Product Auditor")

with st.sidebar:
    st.header("Input Feed")
    uploaded_file = st.file_uploader("Upload Label", type=["jpg", "png", "jpeg"])
    st.info("Supported: Food, Cosmetics, Cleaning Supplies")

if uploaded_file is not None:
    if st.button("🚀 INITIATE AUDIT", use_container_width=True):
        
        # --- PHASE 1: VISION & CATEGORY ---
        with st.status("Analyzing Visual Data...", expanded=True) as status:
            st.write("📸 Extracting features...")
            data = asyncio.run(backend.extract_data_from_image(uploaded_file))
            
            # Check for Vision Error
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
                
                if status == "RED": icon, color_class = "🔴", "badge-red"
                elif status == "GREEN": icon, color_class = "🟢", "badge-green"
                else: icon, color_class = "🟡", "badge-yellow"
                
                with st.expander(f"{icon} {name}"):
                    st.markdown(f"**Impact:** {explanation}")
                    if alternative and alternative != "None":
                        st.success(f"**Better Choice:** {alternative}")

else:
    st.markdown("### ⬅️ Waiting for Input...")
    st.write("Upload a product label to generate the Sustainability Dashboard.")