import streamlit as st
import pandas as pd
import re
import io

def extract_area_logic(text):
    """
    Advanced logic to extract property area from Marathi text.
    Handles vowel variations, Metric/Imperial units, and parking exclusion.
    """
    if pd.isna(text) or text == "":
        return 0.0
    
    # 1. Cleanup: Standardize spaces
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')
    
    # Define flexible regex patterns
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    total_keywords = r'(?:ए[ककु]ण\s*क्षेत्र|क्षेत्रफळ|total\s*area)'
    
    # --- STEP 1: METRIC EXTRACTION (SQ.MT) ---
    m_segments = re.split(f'(\d+\.?\d*)\s*{m_unit}', text, flags=re.IGNORECASE)
    m_vals = []
    
    for i in range(1, len(m_segments), 2):
        val = float(m_segments[i])
        context_before = m_segments[i-1].lower()
        if 0 < val < 500:
            if "पार्किंग" not in context_before and "parking" not in context_before:
                m_vals.append(val)
    
    if m_vals:
        t_m_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{m_unit}', text, re.IGNORECASE)
        if t_m_match:
            return round(float(t_m_match.group(1)), 3)
        if len(m_vals) > 1 and abs(m_vals[-1] - sum(m_vals[:-1])) < 1:
            return round(m_vals[-1], 3)
        return round(sum(m_vals), 3)
        
    # --- STEP 2: FALLBACK TO IMPERIAL (SQ.FT) ---
    f_segments = re.split(f'(\d+\.?\d*)\s*{f_unit}', text, flags=re.IGNORECASE)
    f_vals = []
    
    for i in range(1, len(f_segments), 2):
        val = float(f_segments[i])
        context_before = f_segments[i-1].lower()
        if 0 < val < 5000:
            if "पार्किंग" not in context_before and "parking" not in context_before:
                f_vals.append(val)
                
    if f_vals:
        t_f_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{f_unit}', text, re.IGNORECASE)
        if t_f_match:
            return round(float(t_f_match.group(1)) / 10.764, 3)
        if len(f_vals) > 1 and abs(f_vals[-1] - sum(f_vals[:-1])) < 1:
            return round(f_vals[-1] / 10.764, 3)
        return round(sum(f_vals) / 10.764, 3)

    return 0.0

def determine_config(area, t1, t2, t3):
    if area == 0: return "N/A"
    if area < t1: return "1 BHK"
    elif area < t2: return "2 BHK"
    elif area < t3: return "3 BHK"
    else: return "4 BHK"  # Covers anything equal to or above t3

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Data Specialist", layout="wide")

st.title("🏠 Property Analysis Dashboard")
st.markdown("Extract Marathi property data and calculate SQ.MT, SQ.FT, Saleable, APR, and Configuration.")

# Sidebar for all adjustable parameters
st.sidebar.header("Calculation Settings")
loading_factor = st.sidebar.number_input("Loading Factor", min_value=1.0, value=1.35, step=0.001, format="%.3f")

st.sidebar.markdown("---")
st.sidebar.subheader("Configuration Thresholds (SQ.FT)")
t1 = st.sidebar.number_input("1 BHK Threshold (<)", value=600)
t2 = st.sidebar.number_input("2 BHK Threshold (<)", value=850)
t3 = st.sidebar.number_input("3 BHK Threshold (<)", value=1100)
st.sidebar.info(f"Anything ≥ {t3} will be 4 BHK")

uploaded_file = st.file_uploader("Upload Raw Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    required_cols = ["Property Description", "Consideration Value"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    
    if not missing_cols:
        with st.spinner('Processing...'):
            # 1. Extract SQ.MT
            df['Carpet Area (SQ.MT)'] = df['Property Description'].apply(extract_area_logic)
            
            # 2. Calculate SQ.FT (3 decimal places)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            
            # 3. Calculate Saleable Area (3 decimal places)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(3)
            
            # 4. Calculate APR (3 decimal places)
            df['APR'] = df.apply(
                lambda row: round(row['Consideration Value'] / row['Saleable Area'], 3) 
                if row['Saleable Area'] > 0 else 0, axis=1
            )
            
            # 5. Configuration
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
            
            # Explicitly Order Columns: Original Columns + New Columns at the end
            # We filter out the result_cols from original list to avoid duplicates
            result_cols = ['Carpet Area (SQ.MT)', 'Carpet Area (SQ.FT)', 'Saleable Area', 'APR', 'Configuration']
            base_cols = [c for c in df.columns if c not in result_cols]
            df = df[base_cols + result_cols]
            
            st.success("Calculations Complete!")
            
            # Preview
            st.subheader("Results Preview")
            st.dataframe(df[result_cols].head(15))
            
            # Export
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Ready File",
                data=output.getvalue(),
                file_name="Property_Analysis_Final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error(f"Missing required columns: {', '.join(missing_cols)}")
