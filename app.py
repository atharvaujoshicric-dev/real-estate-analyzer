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

def assign_configuration(area, b1, b2, b3, b4):
    """Categorizes flat based on closest matching sqft input."""
    if area <= 0:
        return "N/A"
    configs = {
        "1 BHK": b1,
        "2 BHK": b2,
        "3 BHK": b3,
        "4 BHK": b4
    }
    # Determine which config area is closest to the actual carpet area
    best_match = min(configs, key=lambda x: abs(configs[x] - area))
    return best_match

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Data Specialist", layout="wide")

st.title("🏠 Property Data Extractor & Configurator")
st.markdown("""
Extracts Marathi property data and calculates Metric, Imperial, Saleable, APR, and Configuration columns.
""")

# Sidebar for Calculation Settings
st.sidebar.header("1. Calculation Settings")
loading_factor = st.sidebar.number_input("Loading Factor", min_value=1.0, max_value=3.0, value=1.350, step=0.001, format="%.3f")

st.sidebar.header("2. Configuration Thresholds (SQ.FT)")
b1_area = st.sidebar.number_input("1 BHK Avg Area", value=450.0)
b2_area = st.sidebar.number_input("2 BHK Avg Area", value=750.0)
b3_area = st.sidebar.number_input("3 BHK Avg Area", value=1100.0)
b4_area = st.sidebar.number_input("4 BHK Avg Area", value=1600.0)

uploaded_file = st.file_uploader("Upload Raw Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    required_cols = ["Property Description", "Consideration value"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    
    if not missing_cols:
        with st.spinner('Processing...'):
            # 1. Metric Area
            df['Carpet Area (SQ.MT)'] = df['Property Description'].apply(extract_area_logic)
            
            # 2. Imperial Area (3 decimal places)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            
            # 3. Saleable Area (3 decimal places)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(3)
            
            # 4. APR (3 decimal places)
            df['APR'] = df.apply(
                lambda row: round(row['Consideration value'] / row['Saleable Area'], 3) 
                if row['Saleable Area'] > 0 else 0, axis=1
            )
            
            # 5. Configuration (Closest match logic)
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(
                lambda x: assign_configuration(x, b1_area, b2_area, b3_area, b4_area)
            )
            
            # Reorder columns to place new data at the end
            cols = list(df.columns)
            result_cols = ['Carpet Area (SQ.MT)', 'Carpet Area (SQ.FT)', 'Saleable Area', 'APR', 'Configuration']
            for col in result_cols:
                if col in cols:
                    cols.append(cols.pop(cols.index(col)))
            df = df[cols]
            
            st.success("Calculations complete!")
            
            # Preview
            st.subheader("Data Preview")
            preview_cols = ['Property Description', 'Carpet Area (SQ.FT)', 'Saleable Area', 'APR', 'Configuration']
            st.dataframe(df[preview_cols].head(15))
            
            # Excel download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Processed Report",
                data=output.getvalue(),
                file_name="Property_Report_Full.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error(f"Missing columns: {', '.join(missing_cols)}")
