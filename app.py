import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Universal RE Analyzer", layout="wide")

def extract_area_final(text):
    if pd.isna(text): return 0
    # Normalize Marathi characters and remove commas
    text = text.replace(',', '').replace('ओेपन', 'ओपन').replace('कार्पेट', 'कारपेट').replace('ौ.मी', 'चौ.मी')
    
    # Identify the unit-specific segment to skip land/survey areas
    unit_keywords = ['फ्लॅट', 'युनिट', 'विंग', 'flat', 'unit', 'मजल्यावरील', 'floor']
    unit_start_idx = 0
    for kw in unit_keywords:
        match = re.search(kw, text, re.IGNORECASE)
        if match:
            unit_start_idx = match.start()
            break
    
    search_text = text[unit_start_idx:]
    
    # Precise Regex for SQMT and SQFT
    sqmt_pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*मी[\.\s]*|चौरस\s*मीटर|sq[\.\s]*mt[r]*)'
    sqft_pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*फ[ुू][टट][\.\s]*|फ[ुू][टट][\.\s]*|sq[\.\s]*ft|square\s*feet)'
    
    sqmt_matches = list(re.finditer(sqmt_pattern, search_text, re.IGNORECASE))
    sqft_matches = list(re.finditer(sqft_pattern, search_text, re.IGNORECASE))
    
    def get_valid_sum(matches, full_text):
        total = 0.0
        for m in matches:
            val = float(m.group(1))
            # Check prefix for "parking" to exclude those numbers
            prefix = full_text[max(0, m.start()-40):m.start()].lower()
            if not any(k in prefix for k in ['पार्किंग', 'पार्कींग', 'parking', 'park']):
                total += val
        return total

    # Calculation logic: Priority to SQMT, Fallback to SQFT
    total_sqmt = get_valid_sum(sqmt_matches, search_text)
    if total_sqmt > 0:
        return total_sqmt
    else:
        total_sqft = get_valid_sum(sqft_matches, search_text)
        # Apply the exact formula provided: sqmt = sqft / 10.764
        return total_sqft / 10.764 if total_sqft > 0 else 0

st.title("🏙️ Professional Real Estate Analyzer")
st.markdown("---")

uploaded_file = st.file_uploader("1. Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("2. Analysis Parameters")
    col1, col2 = st.columns(2)
    with col1:
        loading = st.number_input("Enter Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        bhk_ranges = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Generate Final.xlsx"):
        # Processing - No Rounding
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_final)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        def get_bhk(area):
            try:
                for r in bhk_ranges.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)

        # Excel Export with Sheet Replication - No Possession Date
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Sheet: in
            df.to_excel(writer, index=False, sheet_name='in')
            
            # Sheet: summary
            summ = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            # Reorder to match your manual structure
            summ = summ[['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Average of APR', 'Count of Property']]
            summ.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1 (No Headers)
            s1 = df['Property'].value_counts().reset_index()
            s1.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # Sheet2
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index()
            s2.columns = ['Property', 'Count of Consideration Value']
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # Sheet3
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Generated Successfully!")
        st.download_button("📥 Download Final.xlsx", output.getvalue(), "Final.xlsx")
