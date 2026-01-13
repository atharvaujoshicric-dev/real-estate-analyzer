import streamlit as st
import pandas as pd
import re
import io
from decimal import Decimal

st.set_page_config(page_title="Professional RE Data Tool", layout="wide")

def extract_exact_area(text):
    if pd.isna(text) or not text.strip(): return None
    
    # Standardize Marathi for consistent detection
    text_norm = text.replace(',', '').replace('कार्पेट', 'कारपेट').replace('कॅरपेट', 'कारपेट').replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी')
    
    sqmt_list = []
    sqft_list = []
    
    # Find all numbers in the text
    matches = list(re.finditer(r'(\d+\.?\d*)', text_norm))
    
    for m in matches:
        val_str = m.group(1)
        val = Decimal(val_str)
        
        # Context windows
        prefix = text_norm[max(0, m.start()-50):m.start()].lower()
        suffix = text_norm[m.end():m.end()+40].lower()
        
        # 1. CATEGORY CLASSIFICATION
        is_survey = any(x in prefix for x in ['सर्व्हे', 'survey', 'स.नं', 'स नं', 'गट नं', 'हिस्सा', 'hissa'])
        is_total_land = any(x in prefix for x in ['एकूण', 'total'])
        is_parking = any(x in prefix for x in ['पार्किंग', 'पार्कींग', 'parking', 'park'])
        
        # Rule: Ignore Survey, Land Survey totals, and Parking
        if is_survey or is_total_land or is_parking:
            continue
            
        # 2. UNIT IDENTIFICATION
        is_sqmt = any(x in suffix for x in ['चौ.मी', 'चौरस मीटर', 'sqmt', 'sq.mt', 'sq. mt'])
        is_sqft = any(x in suffix for x in ['चौ.फूट', 'चौ.फुट', 'चौ फूट', 'sqft', 'sq.ft', 'sq. ft', 'फूट', 'फुट'])
        
        # Rule: Add component if it belongs to Carpet/Balcony
        if is_sqmt and val < Decimal('500'): # Sanity check for unit components
            sqmt_list.append(val)
        elif is_sqft and val < Decimal('5000'):
            sqft_list.append(val)

    # 3. FINAL CALCULATION
    if sqmt_list:
        return float(sum(sqmt_list))
    elif sqft_list:
        # Fallback: sqmt = sqft / 10.764
        return float(sum(sqft_list) / Decimal('10.764'))
    
    return None

st.title("🏙️ Professional Real Estate Analyzer")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.header("Settings")
    col1, col2 = st.columns(2)
    load_val = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.0001, format="%.4f")
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Process Final Excel"):
        # Apply strict extraction
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_exact_area)
        
        # Exact formulas (No Rounding)
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

        # Excel Generation (5 Sheets)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 1. in
            df.to_excel(writer, index=False, sheet_name='in')
            
            # 2. summary (Row 3 start, no Possession)
            summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summary.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # 3. Sheet1 (No header, Count only)
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # 4. Sheet2 (Row 3 start + Total)
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index().rename(columns={'Consideration Value': 'Count of Consideration Value'})
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # 5. Sheet3 (Row 3 start)
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Generated Successfully.")
        st.download_button("📥 Download Final.xlsx", output.getvalue(), "Final.xlsx")
