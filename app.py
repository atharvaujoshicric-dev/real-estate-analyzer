import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Professional RE Analyzer", layout="wide")

def extract_unit_sqmt(text):
    if pd.isna(text): return 0
    # Basic cleaning
    text = text.replace(',', '')
    
    # regex for numbers
    pattern = r'(\d+\.?\d*)'
    matches = list(re.finditer(pattern, text))
    
    total_area = 0.0
    for m in matches:
        val = float(m.group(1))
        # Component check: single unit parts (carpet/balcony) are rarely > 500 sqm
        if val > 500: continue
        
        # Check context window (40 chars before and after)
        suffix = text[m.end():m.end()+40].lower()
        prefix = text[max(0, m.start()-40):m.start()].lower()
        
        # 1. PROFESSIONAL EXCLUSIONS
        # Ignore parking, survey numbers, and common numeric labels
        exclude_logic = ['पार्किंग', 'पार्कींग', 'parking', 'park', 'सर्व्हे', 'survey', 'स.नं', 'गट नं', 'hissa', 'नं.']
        if any(k in prefix for k in exclude_logic):
            continue
        
        # 2. UNIT VALIDATION
        # Look for metric keywords ('मी', 'मीटर', 'sqmt', 'sq.mt')
        if any(k in suffix for k in ['मी', 'मीटर', 'meter', 'sq.mt', 'sqmt', 'mtr']):
            # Ensure it's not a secondary SQFT mention for the same area
            if not any(k in suffix[:15] for k in ['फूट', 'फुट', 'ft', 'sq.ft', 'sqft']):
                total_area += val
                
    return total_area

st.title("🏙️ Real Estate Final Report Generator")

uploaded_file = st.file_uploader("1. Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("2. Configuration")
    col1, col2 = st.columns(2)
    with col1:
        loading = st.number_input("Loading Factor (e.g. 1.4)", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        bhk_ranges = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Process & Generate Excel"):
        # Core Formulas
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_unit_sqmt)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # BHK Logic
        def get_bhk(area):
            try:
                for r in bhk_ranges.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)

        # Excel Generation (5 Sheets)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            
            # Summary Sheet (Grouped)
            summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summary.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1, Sheet2, Sheet3 (Formatting matches manual file)
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index()
            s2.columns = ['Property', 'Count of Consideration Value']
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("Analysis Complete!")
        st.download_button("📥 Download Final.xlsx", output.getvalue(), "Final.xlsx")
