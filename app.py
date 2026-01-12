import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Universal RE Analyzer", layout="wide")

def extract_total_area(text):
    if pd.isna(text): return 0
    
    # Standardize Marathi text to handle variations
    text = text.replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी')
    
    # Regex designed to capture numbers even if there is punctuation in between
    # Looks for digits/decimals after keywords
    carpet_match = re.search(r'(?:कारपेट क्षेत्र|carpet area)[^\d]*([\d\.]+)', text, re.IGNORECASE)
    balcony_match = re.search(r'(?:ओपन बाल्कनी|बाल्कनी|सीटआऊट|dry balcony)[^\d]*([\d\.]+)', text, re.IGNORECASE)
    fallback = re.search(r'(?:फ्लॅट|unit|युनिट)[^\d]*क्षेत्र[^\d]*([\d\.]+)', text, re.IGNORECASE)

    def safe_float(match):
        if not match: return 0
        val = match.group(1).strip('.') # Remove stray dots
        try:
            return float(val) if val else 0
        except ValueError:
            return 0

    c_val = safe_float(carpet_match)
    b_val = safe_float(balcony_match)
    
    # Logic: Sum Carpet + Balcony. If both missing, try fallback.
    total = c_val + b_val
    if total == 0:
        total = safe_float(fallback)
        
    return total

st.title("🏙️ Universal Real Estate Processor")
st.markdown("---")

uploaded_file = st.file_uploader("1. Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # MOVED BACK TO MAIN PAGE:
    st.header("2. Global Configuration")
    col1, col2 = st.columns(2)
    with col1:
        global_loading = st.number_input("Loading Factor (Applied to all)", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        global_bhk = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Process & Generate Final Excel"):
        # Process Areas
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_total_area)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.7639
        
        def apply_logic(row):
            saleable = row['Carpet Area(SQ.FT)'] * global_loading
            area_ft = row['Carpet Area(SQ.FT)']
            label = "Other"
            try:
                for r in global_bhk.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area_ft <= high:
                        label = name.strip()
                        break
            except: pass
            return pd.Series([saleable, label])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_logic, axis=1)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # Create Summary (Matching your manual file structure)
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 'Property': 'count'
        }).rename(columns={'Property': 'Count of Property', 'APR': 'Average of APR'}).reset_index()

        # Output to Excel with multiple sheets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            summary.to_excel(writer, index=False, sheet_name='summary')
            # Property Counts sheet (Sheet1/Sheet2 style)
            counts = df['Property'].value_counts().reset_index()
            counts.columns = ['Property', 'Count']
            counts.to_excel(writer, index=False, sheet_name='Property Counts')

        st.success("Transformation complete!")
        st.download_button("📥 Download Final_Corrected.xlsx", output.getvalue(), "Final_Corrected.xlsx")
        
        st.subheader("Data Preview")
        st.dataframe(summary.head(10))
