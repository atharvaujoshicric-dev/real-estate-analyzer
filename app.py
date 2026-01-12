import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Universal RE Analyzer", layout="wide")

def extract_area_perfect(text):
    if pd.isna(text) or text.strip() == "": return None
    
    # Normalize Marathi text variations
    text_norm = text.replace(',', '').replace('ओेपन', 'ओपन').replace('कार्पेट', 'कारपेट').replace('ौ.मी', 'चौ.मी')
    
    sqmt_parts = []
    sqft_parts = []
    
    # Find all numbers and check their context
    matches = list(re.finditer(r'(\d+\.?\d*)', text_norm))
    
    for m in matches:
        val = float(m.group(1))
        suffix = text_norm[m.end():m.end()+40].lower()
        prefix = text_norm[max(0, m.start()-40):m.start()].lower()
        
        # EXCLUDE: Land/Survey/Parking logic
        exclude_keywords = ['सर्व्हे', 'स.नं', 'गट नं', 'survey', 'hissa', 'पार्किंग', 'पार्कींग', 'parking', 'park']
        if any(k in prefix for k in exclude_keywords):
            continue
            
        # INCLUDE: Metric check
        if any(k in suffix for k in ['चौ.मी', 'चौरस मीटर', 'sq.mt', 'sqmt', 'sq.mtr']):
            sqmt_parts.append(val)
        elif any(k in suffix for k in ['चौ.फुट', 'चौ.फूट', 'sq.ft', 'sqft', 'square feet', 'फूट', 'फुट']):
            sqft_parts.append(val)

    if sqmt_parts:
        return sum(sqmt_parts)
    elif sqft_parts:
        # Fallback formula: sqmt = sqft / 10.764
        return sum(sqft_parts) / 10.764
    
    return None # Returns None to keep cell blank in Excel

st.title("🏙️ Professional Real Estate Analyzer")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("Settings")
    col1, col2 = st.columns(2)
    loading = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("Generate Final Excel"):
        # 1. Core Calculations with Full Precision
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_perfect)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        def get_bhk(area):
            if pd.isna(area) or area == 0: return ""
            try:
                for r in bhk_input.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)

        # 2. Build Excel with Specific Empty Rows and Structure
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Sheet: in
            df.to_excel(writer, index=False, sheet_name='in')
            
            # Sheet: summary (Starts row 3)
            summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summary.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1 (No headers)
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # Sheet2 (Starts row 3)
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index()
            s2.columns = ['Property', 'Count of Consideration Value']
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # Sheet3 (Starts row 3)
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Generated.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
