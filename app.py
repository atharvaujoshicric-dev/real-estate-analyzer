import streamlit as st
import pandas as pd
import re
import io

def extract_area_logic(text):
    """
    Advanced logic to extract property area from Marathi text.
    Handles vowels variations, Metric/Imperial units, and parking exclusion.
    """
    if pd.isna(text) or text == "":
        return 0.0
    
    # 1. Standardize text
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')
    
    # Define flexible regex patterns
    # Units
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    f_unit = r'(?:चौ\.?\s*फू\.?|चौरस\s*फु[टत]|sq\.?\s*f(?:t)?\.?)'
    # Keywords for "Total Area" (handling spelling variations)
    total_keywords = r'(?:ए[ककु]ण\s*क्षेत्र|क्षेत्रफळ|total\s*area)'
    
    # --- STEP 1: METRIC EXTRACTION (SQ.MT) ---
    # Split by metric units to check context (like parking)
    m_segments = re.split(f'(\d+\.?\d*)\s*{m_unit}', text, flags=re.IGNORECASE)
    m_vals = []
    
    for i in range(1, len(m_segments), 2):
        val = float(m_segments[i])
        context_before = m_segments[i-1].lower()
        # Filter: only small areas (<500) and ignore parking
        if 0 < val < 500:
            if "पार्किंग" not in context_before and "parking" not in context_before:
                m_vals.append(val)
    
    if m_vals:
        # Check if an explicit "Total" is mentioned in the text
        t_m_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{m_unit}', text, re.IGNORECASE)
        if t_m_match:
            return round(float(t_m_match.group(1)), 2)
        
        # If no explicit total, check if last value is sum of previous (prevents double counting)
        if len(m_vals) > 1 and abs(m_vals[-1] - sum(m_vals[:-1])) < 1:
            return round(m_vals[-1], 2)
        
        return round(sum(m_vals), 2)
        
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
        # Check for explicit Total in Sq.Ft
        t_f_match = re.search(rf'{total_keywords}\s*:?\s*(\d+\.?\d*)\s*{f_unit}', text, re.IGNORECASE)
        if t_f_match:
            return round(float(t_f_match.group(1)) / 10.764, 2)
        
        # Avoid double counting components + total
        if len(f_vals) > 1 and abs(f_vals[-1] - sum(f_vals[:-1])) < 1:
            return round(f_vals[-1] / 10.764, 2)
            
        return round(sum(f_vals) / 10.764, 2)

    return 0.0

# --- STREAMLIT UI ---
st.set_page_config(page_title="Marathi Data Extractor", layout="wide")

st.title("🏠 Property Data Extraction Tool")
st.markdown("""
Extracts **Carpet + Balcony + Terrace** areas from Marathi property descriptions.
- **Auto-Conversion:** Square Feet is converted to Square Meters ($1 \text{ sq.m.} = 10.764 \text{ sq.ft.}$).
- **Smart Filter:** Automatically excludes Parking areas and large Project Plot areas.
""")

uploaded_file = st.file_uploader("Upload your raw Excel file (.xlsx)", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    if "Property Description" in df.columns:
        with st.spinner('Processing Marathi text logic...'):
            # Run the extraction
            df['Carpet Area (SQ.MT)'] = df['Property Description'].apply(extract_area_logic)
            
            st.success("Success! Area extracted for all rows.")
            
            # Show top results
            st.subheader("Preview of Results")
            st.dataframe(df[['Property Description', 'Carpet Area (SQ.MT)']].head(20))
            
            # Prepare file for download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Ready File",
                data=output.getvalue(),
                file_name="Extracted_Property_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("Error: Could not find column 'Property Description'. Please check your file.")
