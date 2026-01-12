import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Real Estate Analyzer Pro", layout="wide")

def extract_area_refined(text):
    if pd.isna(text): return 0
    # Standardize Marathi text
    text = text.replace('कार्पेट', 'कारपेट').replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी').replace(',', '')
    
    # Locate where the unit details start (skip land/survey info)
    unit_start = re.search(r'(?:फ्लॅट|युनिट|विंग|flat|unit|building)', text, re.IGNORECASE)
    search_text = text[unit_start.start():] if unit_start else text
    
    # Regex to find numbers followed by SQMT keywords
    pattern = r'([\d\.]+)\s*(?:चौ[\.\s]*मी|चौरस मीटर|sq[\.\s]*mt)'
    matches = re.findall(pattern, search_text, re.IGNORECASE)
    
    # Capture context for each number to check for "parking"
    total_area = 0
    # Find all matches with 30 characters of preceding context
    context_matches = re.finditer(r'(.{0,30})([\d\.]+)\s*(?:चौ[\.\s]*मी|चौरस मीटर|sq[\.\s]*mt)', search_text, re.IGNORECASE)
    
    for m in context_matches:
        prefix = m.group(1).lower()
        val = float(m.group(2))
        # Exclude if parking is mentioned or if value is too large (likely land)
        if not any(k in prefix for k in ['पार्किंग', 'पार्कींग', 'parking']) and val < 400:
            total_area += val
            
    return total_area

st.title("🏙️ Real Estate Raw to Final Processor")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("Settings")
    col1, col2 = st.columns(2)
    with col1:
        loading = st.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        bhk_input = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("Generate Final Excel"):
        # 1. Calculations
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_refined)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        def get_bhk(area):
            try:
                for r in bhk_input.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)
        
        # Format Possession for summary
        df['Possession_Str'] = pd.to_datetime(df['Completion Date']).dt.strftime('%B, %Y')

        # --- DATA SHEETS ---
        # 1. Summary
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Possession_Str']).agg({
            'APR': 'mean', 'Property': 'count'
        }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
        summary = summary.rename(columns={'Possession_Str': 'Possession'})

        # 2. Sheet1 (No Header)
        sheet1 = df['Property'].value_counts().reset_index()

        # 3. Sheet2
        sheet2 = df.groupby('Property')['Consideration Value'].count().reset_index()
        sheet2.columns = ['Property', 'Count of Consideration Value']

        # 4. Sheet3
        sheet3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 'Property': 'count'
        }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()

        # --- EXCEL EXPORT ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # In Sheet
            df.drop(columns=['Possession_Str']).to_excel(writer, index=False, sheet_name='in')
            
            # Summary Sheet (Starting Row 3)
            summary.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1 (No headers)
            sheet1.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # Sheet2 (Starting Row 3)
            sheet2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # Sheet3 (Starting Row 3)
            sheet3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Generated Successfully!")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
