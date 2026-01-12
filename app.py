import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer Pro", layout="wide")

def extract_area_logic(text):
    """
    Intelligently extracts and sums Carpet + Balcony areas while ignoring Parking.
    """
    if pd.isna(text): return 0
    
    # Normalize Marathi variations to ensure regex matches
    text = text.replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी').replace(',', '')
    
    # Extract all numbers associated with SQMT (चौ.मी / चौरस मीटर)
    pattern = r'([\d\.]+)\s*(?:चौ\.मी|चौरस मीटर|sq\.?mt|sq\.?mtr)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    areas = [float(m) for m in matches]
    
    if len(areas) >= 2:
        # If 'Parking' is mentioned, we assume the last area is parking and exclude it
        if "पार्कींग" in text or "parking" in text.lower():
            # Sum only the first two (Carpet + Balcony)
            return sum(areas[:2])
        # If no parking mentioned, sum everything found
        return sum(areas)
    elif len(areas) == 1:
        return areas[0]
    
    return 0

st.title("🏙️ Real Estate Raw to Final Processor")
st.markdown("---")

uploaded_file = st.file_uploader("1. Upload Raw Excel File", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("2. Analysis Parameters")
    col1, col2 = st.columns(2)
    
    with col1:
        user_loading = st.number_input("Enter Loading Factor (e.g. 1.4 for 40%)", 1.0, 2.0, 1.4, step=0.01)
    
    with col2:
        user_bhk = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Process Data"):
        # 1. Extraction
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_logic)
        
        # 2. Formula: sqft = sqmt * 10.764
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        
        # 3. Formula: saleable area = sqft * loading
        def apply_bhk_and_saleable(row):
            # Calculate Saleable
            saleable = row['Carpet Area(SQ.FT)'] * user_loading
            
            # Categorize BHK
            area = row['Carpet Area(SQ.FT)']
            bhk_label = "Other"
            try:
                for r in user_bhk.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high:
                        bhk_label = name.strip()
                        break
            except: pass
            return pd.Series([saleable, bhk_label])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_bhk_and_saleable, axis=1)
        
        # 4. Formula: apr = consideration value / saleable area
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # --- GENERATE SUMMARY SHEETS ---
        
        # Summary (Grouped by Property, Configuration, and Area)
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 
            'Property': 'count'
        }).rename(columns={'Property': 'Count of Property', 'APR': 'Average of APR'}).reset_index()

        # Property Counts (Sheet1/Sheet2 style)
        counts = df['Property'].value_counts().reset_index()
        counts.columns = ['Property', 'Count']

        # --- EXCEL GENERATION ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            summary.to_excel(writer, index=False, sheet_name='summary')
            counts.to_excel(writer, index=False, sheet_name='Sheet1')

        st.success("Analysis Complete! All formulas applied correctly.")
        st.download_button(
            label="📥 Download Final.xlsx",
            data=output.getvalue(),
            file_name="Final_Processed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.subheader("Results Preview")
        st.dataframe(summary)
