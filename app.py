import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer Final", layout="wide")

def extract_correct_areas(text):
    if pd.isna(text): return 0
    text = text.replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी').replace(',', '')
    
    # 1. Extract numbers associated with Area (Metric)
    # This captures variations like चौ.मी, चौ मी, चौ.मी.
    pattern = r'([\d\.]+)\s*(?:चौ[\.\s]*मी|चौरस मीटर|sq[\.\s]*mt)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    areas = [float(m) for m in matches]
    
    # 2. Filter logic: Ignore large land survey numbers (usually > 500)
    # Also ignore parking (usually the 3rd number if listed)
    unit_areas = [a for a in areas if 5 < a < 500] 
    
    if len(unit_areas) >= 2:
        # If it's a typical residential entry: Carpet + Balcony
        return unit_areas[0] + unit_areas[1]
    elif len(unit_areas) == 1:
        return unit_areas[0]
    return 0

st.title("🏙️ Professional Real Estate Analyzer")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("Analysis Parameters")
    col1, col2 = st.columns(2)
    with col1:
        loading = st.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        bhk_ranges = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Generate Final Excel"):
        # Core Calculations
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_correct_areas)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        
        def process_row(row):
            saleable = row['Carpet Area(SQ.FT)'] * loading
            area = row['Carpet Area(SQ.FT)']
            conf = "Other"
            try:
                for r in bhk_ranges.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high:
                        conf = name.strip()
                        break
            except: pass
            return pd.Series([saleable, conf])

        df[['Saleable Area', 'Configuration']] = df.apply(process_row, axis=1)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # Format Possession (Month, Year)
        df['Possession'] = pd.to_datetime(df['Completion Date']).dt.strftime('%B, %Y')

        # --- SHEETS ---
        # 1. In Sheet
        in_sheet = df.copy()

        # 2. Summary Sheet (Aggregated)
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Possession']).agg({
            'APR': 'mean', 'Property': 'count'
        }).rename(columns={'Property': 'Count of Property', 'APR': 'Average of APR'}).reset_index()
        summary = summary[['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Average of APR', 'Count of Property', 'Possession']]

        # 3. Sheet1 (Simple Counts)
        sheet1 = df['Property'].value_counts().reset_index()
        sheet1.columns = ['Property', 'Count']

        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            in_sheet.to_excel(writer, index=False, sheet_name='in')
            summary.to_excel(writer, index=False, sheet_name='summary')
            sheet1.to_excel(writer, index=False, header=False, sheet_name='Sheet1')

        st.success("File Processed! Land survey areas excluded and formats corrected.")
        st.download_button("📥 Download Final.xlsx", output.getvalue(), "Final.xlsx")
