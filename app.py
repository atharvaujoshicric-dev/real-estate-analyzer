import streamlit as st
import pandas as pd
import re
import io
from decimal import Decimal

st.set_page_config(page_title="Professional RE Analyzer", layout="wide")

def extract_area_final_verified(text):
    if pd.isna(text) or not text.strip(): return None
    
    # Standardize Marathi text
    text = text.replace(',', '').replace('ओेपन', 'ओपन').replace('कार्पेट', 'कारपेट').replace('ौ.मी', 'चौ.मी')
    
    # 1. Search specifically for Carpet and Balcony labels
    # We look for the keyword, then optional words like 'क्षेत्र', then the number
    carpet_pattern = r'(?:कारपेट|कार्पेट|carpet)\s*(?:क्षेत्र|area)?\s*(\d+\.?\d*)'
    balcony_pattern = r'(?:बाल्कनी|balcony|टेरेस|terrace|ओपन|सीटआऊट)\s*(?:क्षेत्र|area)?\s*(\d+\.?\d*)'
    
    c_match = re.search(carpet_pattern, text, re.IGNORECASE)
    b_matches = re.finditer(balcony_pattern, text, re.IGNORECASE)
    
    total_sqmt = Decimal('0')
    found_any = False

    # Extract Carpet
    if c_match:
        val = Decimal(c_match.group(1))
        if val < Decimal('500'): # Ignore survey numbers if accidentally caught
            total_sqmt += val
            found_any = True
            
    # Extract Balcony/Terrace (Sum all if multiple found)
    for m in b_matches:
        val = Decimal(m.group(1))
        # Context check: ignore if 'parking' or 'survey' is in the preceding 30 chars
        prefix = text[max(0, m.start()-30):m.start()].lower()
        if not any(k in prefix for k in ['पार्किंग', 'parking', 'सर्व्हे', 'survey']):
            if val < Decimal('200'): # Balconies are small
                total_sqmt += val
                found_any = True

    # 2. Fallback: If labels failed but SQFT exists, convert it
    if not found_any:
        sqft_pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*फ[ुू][टट]|sq[\.\s]*ft|square\s*feet)'
        sqft_match = re.search(sqft_pattern, text, re.IGNORECASE)
        if sqft_match:
            val_sqft = Decimal(sqft_match.group(1))
            total_sqmt = val_sqft / Decimal('10.764')
            found_any = True

    return float(total_sqmt) if found_any else None

st.title("🏙️ Professional Real Estate Analyzer")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.header("Settings")
    col1, col2 = st.columns(2)
    load_val = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.0001, format="%.4f")
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Run Final Verified Process"):
        # apply verified extraction
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_final_verified)
        
        # Formulas with high precision
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'].apply(lambda x: float(Decimal(str(x)) * Decimal('10.764')) if x else None)
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'].apply(lambda x: float(Decimal(str(x)) * Decimal(str(load_val))) if x else None)
        df['APR'] = df.apply(lambda r: float(Decimal(str(r['Consideration Value'])) / Decimal(str(r['Saleable Area']))) if r['Saleable Area'] else None, axis=1)
        
        def get_bhk(area):
            if not area: return ""
            for r in bhk_input.split(','):
                limits, name = r.split(':')
                low, high = map(float, limits.split('-'))
                if low <= area <= high: return name.strip()
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)
        df['Possession'] = pd.to_datetime(df['Completion Date']).dt.strftime('%B, %Y')

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            
            # summary sheet (Exact layout: Row 3 start + Possession column)
            summ = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Possession']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summ.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # Sheet2 (Row 3 start)
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index().rename(columns={'Consideration Value': 'Count of Consideration Value'})
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # Sheet3 (Row 3 start)
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("Professional Processing Complete.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
