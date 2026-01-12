import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer", layout="wide")

def extract_area(text):
    if pd.isna(text): return 0
    # Robust Regex: Finds keyword, skips punctuation/spaces, then captures the number
    carpet = re.search(r'(?:क्षेत्र|carpet area)[^\d]*(\d+\.?\d*)', text, re.IGNORECASE)
    balcony = re.search(r'(?:बाल्कनी|balcony)[^\d]*(\d+\.?\d*)', text, re.IGNORECASE)
    
    try:
        c_val = float(carpet.group(1)) if carpet else 0
        b_val = float(balcony.group(1)) if balcony else 0
        return c_val + b_val
    except:
        return 0

st.title("🏙️ Real Estate Raw to Final Processor")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("⚙️ Global Settings")
    st.info("These settings will apply to ALL projects in the uploaded file.")
    
    col1, col2 = st.columns(2)
    with col1:
        global_loading = st.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        global_bhk_ranges = st.text_input(
            "BHK Ranges (Format: Low-High:Name)", 
            "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK"
        )

    if st.button("🚀 Process & Generate Report"):
        # 1. Calculation Logic
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.7639
        
        def apply_global_logic(row):
            # Apply single loading factor
            saleable = row['Carpet Area(SQ.FT)'] * global_loading
            
            # Apply single BHK range logic
            area_ft = row['Carpet Area(SQ.FT)']
            final_bhk = "Other"
            try:
                for r in global_bhk_ranges.split(','):
                    limit, name = r.split(':')
                    low, high = map(float, limit.split('-'))
                    if low <= area_ft <= high:
                        final_bhk = name.strip()
                        break
            except:
                pass
            return pd.Series([saleable, final_bhk])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_global_logic, axis=1)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # 2. Aggregation Logic (Summary)
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 
            'Property': 'count'
        }).rename(columns={'Property': 'Total Units', 'APR': 'Avg APR'}).reset_index()

        # 3. File Preparation
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Final Data')
            summary.to_excel(writer, index=False, sheet_name='Market Summary')
        
        # 4. Results UI
        st.success("Transformation Successful!")
        st.download_button("📥 Download Final Excel", output.getvalue(), "Final_Market_Analysis.xlsx")
        
        st.subheader("Preview: Market Summary")
        st.dataframe(summary, use_container_width=True)
