import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer", layout="wide")

def extract_area_simple(text):
    if pd.isna(text): return 0
    text = text.replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी').replace(',', '')
    # Find all numbers followed by metric units (चौ.मी / sqm)
    pattern = r'([\d\.]+)\s*(?:चौ[\.\s]*मी|चौरस मीटर|sq[\.\s]*mt)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    areas = [float(m) for m in matches]
    
    # Filter: Residential flats/balconies are between 5 and 450 sqm.
    # Anything else (like 17,600 sqm land) is ignored.
    unit_parts = [a for a in areas if 5 < a < 450]
    
    if len(unit_parts) >= 2:
        return unit_parts[0] + unit_parts[1] # Carpet + Balcony
    elif len(unit_parts) == 1:
        return unit_parts[0]
    return 0

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
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_simple)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        
        def get_bhk(area):
            try:
                for r in bhk_input.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""

        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']

        # --- SHEET GENERATION ---
        
        # summary sheet: Group by Property, Configuration, Area
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 
            'Property': 'count'
        }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()

        # Sheet1: Matches your Sheet1.csv (Property and Count)
        sheet1 = df['Property'].value_counts().reset_index()
        sheet1.columns = ['Property', 'Count']

        # Sheet2: Matches your Sheet2.csv (Property and Count of Consideration Value)
        sheet2 = df.groupby('Property')['Consideration Value'].count().reset_index()
        sheet2.columns = ['Property', 'Count of Consideration Value']

        # Sheet3: Matches your Sheet3.csv (Property, Rera, Configuration, Area, APR, Count)
        sheet3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 
            'Property': 'count'
        }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()

        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            summary.to_excel(writer, index=False, sheet_name='summary')
            sheet1.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            sheet2.to_excel(writer, index=False, sheet_name='Sheet2')
            sheet3.to_excel(writer, index=False, sheet_name='Sheet3')

        st.success("Files Generated.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
