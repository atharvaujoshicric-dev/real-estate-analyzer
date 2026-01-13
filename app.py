import streamlit as st
import pandas as pd
import re
import io
from decimal import Decimal

st.set_page_config(page_title="RE Analyzer Step 1", layout="wide")

def translate_and_extract(text):
    if pd.isna(text) or not text.strip(): return None
    
    # 1. CONVERT MARATHI TO ENGLISH REFERENCE
    # Standardizing keywords for the computer to understand
    eng_ref = text.lower()
    mapping = {
        'कारपेट': 'carpet', 'कार्पेट': 'carpet', 'कॅरपेट': 'carpet',
        'बाल्कनी': 'balcony', 'ओपन': 'open', 'टेरेस': 'terrace',
        'क्षेत्र': 'area', 'चौ.मी': 'sqmt', 'चौरस मीटर': 'sqmt',
        'चौ.फूट': 'sqft', 'चौ.फुट': 'sqft', 'फूट': 'ft'
    }
    for mr, en in mapping.items():
        eng_ref = eng_ref.replace(mr, en)

    # 2. EXTRACTION FROM ENGLISH REFERENCE
    total_sqmt = Decimal('0')
    found = False

    # Look for: "carpet area [number] sqmt" or "balcony area [number] sqmt"
    # We find all numbers that are followed by 'sqmt'
    matches = re.finditer(r'(\d+\.?\d*)\s*sqmt', eng_ref)
    
    for m in matches:
        val = Decimal(m.group(1))
        # Logic: If the word 'carpet', 'balcony', or 'terrace' is within 50 chars BEFORE the number
        context = eng_ref[max(0, m.start()-50):m.start()]
        
        # Professional Exclusion: skip if 'parking', 'survey', or 'land' is mentioned in context
        if any(x in context for x in ['parking', 'survey', 'hissa', 'total area']):
            continue
            
        if any(x in context for x in ['carpet', 'balcony', 'terrace', 'area']):
            total_sqmt += val
            found = True

    return float(total_sqmt) if found else None

st.title("🏙️ Professional RE Analyzer - Step 1 (Translation Logic)")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    load_val = st.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.0001, format="%.4f")
    
    if st.button("🚀 Run Step 1 Test"):
        # Apply the new translation extraction
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(translate_and_extract)
        
        # Apply your exact formulas
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'].apply(lambda x: float(Decimal(str(x)) * Decimal('10.764')) if x else None)
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'].apply(lambda x: float(Decimal(str(x)) * Decimal(str(load_val))) if x else None)
        df['APR'] = df.apply(lambda r: float(Decimal(str(r['Consideration Value'])) / Decimal(str(r['Saleable Area']))) if r['Saleable Area'] else None, axis=1)

        st.write("### Step 1 Results Preview (Check if SQ.MT is still 0)")
        st.dataframe(df[['Property', 'Property Description', 'Carpet Area(SQ.MT)', 'APR']].head(15))
        
        # Download button for Step 1
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
        st.download_button("Download Step 1 Test file", output.getvalue(), "Step1_Test.xlsx")
