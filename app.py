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

def get_config(area, t1, t2, t3, t4):
    if area <= 0: return "N/A"
    if area < t1: return "1 BHK"
    if area < t2: return "2 BHK"
    if area < t3: return "3 BHK"
    if area < t4: return "4 BHK"
    return "4+ BHK"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Real Estate Data Specialist", layout="wide")

st.title("🏠 Property Master Data Processor")
st.markdown("""
Extracts data from Marathi descriptions and calculates SQ.MT, SQ.FT, Saleable, APR, and Configuration.
""")

# Sidebar settings
st.sidebar.header("1. Loading Calculation")
loading_factor = st.sidebar.number_input("Loading Factor", value=1.350, format="%.3f")

st.sidebar.header("2. Configuration Thresholds (SQ.FT)")
bhk1_max = st.sidebar.number_input("1 BHK: Anything less than (<)", value=550.0)
bhk2_max = st.sidebar.number_input(f"2 BHK: From {bhk1_max} up to", value=850.0)
bhk3_max = st.sidebar.number_input(f"3 BHK: From {bhk2_max} up to", value=1300.0)
bhk4_max = st.sidebar.number_input(f"4 BHK: From {bhk3_max} up to", value=1800.0)

uploaded_file = st.file_uploader("Upload Raw Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # Check for required columns
    required_cols = ["Property Description", "Consideration value"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    
    if not missing_cols:
        with st.spinner('Calculating Master Data...'):
            # 1. Calculate SQ.MT (Metric)
            df['Carpet Area (SQ.MT)'] = df['Property Description'].apply(extract_area_logic)
            
            # 2. Calculate SQ.FT (3 decimal places)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            
            # 3. Calculate Saleable Area (3 decimal places)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading_factor).round(3)
            
            # 4. Calculate APR (3 decimal places)
            df['APR'] = df.apply(
                lambda row: round(row['Consideration value'] / row['Saleable Area'], 3) 
                if row['Saleable Area'] > 0 else 0, 
                axis=1
            )
            
            # 5. Calculate Configuration
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(
                lambda x: get_config(x, bhk1_max, bhk2_max, bhk3_max, bhk4_max)
            )
            
            # Rearrange columns to put results at the end
            cols = list(df.columns)
            result_cols = ['Carpet Area (SQ.MT)', 'Carpet Area (SQ.FT)', 'Saleable Area', 'APR', 'Configuration']
            for col in result_cols:
                if col in cols:
                    cols.append(cols.pop(cols.index(col)))
            df = df[cols]
            
            st.success("All calculations updated!")
            
            # Results Preview
            st.subheader("Data Preview")
            preview_cols = ['Property Description', 'Consideration value', 'Carpet Area (SQ.FT)', 'Saleable Area', 'APR', 'Configuration']
            st.dataframe(df[preview_cols].head(15))
            
            # Excel download buffer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Final Report",
                data=output.getvalue(),
                file_name="Property_Master_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error(f"Missing required columns: {', '.join(missing_cols)}")
