import streamlit as st
import pandas as pd
import re
import io
from decimal import Decimal

st.set_page_config(page_title="Professional RE Analyzer", layout="wide")

def extract_area_surgical(text):
    if pd.isna(text) or not text.strip(): return None
    
    # Standardize Marathi specific characters to ensure matches
    t = text.replace(',', '').replace('कार्पेट', 'कारपेट').replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी')
    
    total_sqmt = Decimal('0')
    found = False
    
    # 1. Regex to find any number followed by Square Meter keywords
    # Flexible on dots and spaces
    pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*मी|चौरस\s*मीटर|sq[\.\s]*mt)'
    
    for m in re.finditer(pattern, t, re.IGNORECASE):
        val = Decimal(m.group(1))
        
        # Check prefix context (40 chars) to exclude junk
        prefix = t[max(0, m.start()-40):m.start()].lower()
        exclude_logic = ['पार्किंग', 'पार्कींग', 'parking', 'park', 'सर्व्हे', 'survey', 'स.नं', 'गट नं', 'फ्लॅट नं', 'unit no']
        
        if any(k in prefix for k in exclude_logic) or val > Decimal('500'):
            continue
            
        total_sqmt += val
        found = True

    # 2. Fallback: If no SQMT labels found, check for SQFT
    if not found:
        ft_pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*फ[ुू][टट]|sq[\.\s]*ft|square\s*feet|फ[ुू][टट])'
        sqft_sum = Decimal('0')
        for fm in re.finditer(ft_pattern, t, re.IGNORECASE):
            f_val = Decimal(fm.group(1))
            f_prefix = t[max(0, fm.start()-40):fm.start()].lower()
            if not any(k in f_prefix for k in ['पार्किंग', 'पार्कींग', 'parking']) and f_val < Decimal('5000'):
                sqft_sum += f_val
                found = True
        if sqft_sum > 0:
            total_sqmt = sqft_sum / Decimal('10.764')

    return float(total_sqmt) if found else None

st.title("🏙️ Real Estate Raw to Final Processor")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.header("Settings")
    col1, col2 = st.columns(2)
    load_val = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.0001, format="%.4f")
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Process Final Excel"):
        # Apply Surgical Extraction
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_surgical)
        
        # Exact Formula with High Precision
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

        # Excel Export with Exact Sheets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            
            # summary (Row 3 Offset)
            summ = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summ.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # Sheet2 (With Grand Total)
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index().rename(columns={'Consideration Value': 'Count of Consideration Value'})
            pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)]).to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # Sheet3
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("Transformation Complete.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
