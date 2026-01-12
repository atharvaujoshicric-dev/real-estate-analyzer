import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer", layout="wide")

def extract_area(text):
    if pd.isna(text): return 0
    # Improved regex to ensure it only captures valid numbers
    # It looks for digits followed by optional decimals
    carpet = re.search(r'(?:क्षेत्र|carpet area)\s*(\d+\.?\d*)', text, re.IGNORECASE)
    balcony = re.search(r'(?:बाल्कनी|balcony)\s*(\d+\.?\d*)', text, re.IGNORECASE)
    
    try:
        c_val = float(carpet.group(1)) if carpet and carpet.group(1) != '.' else 0
        b_val = float(balcony.group(1)) if balcony and balcony.group(1) != '.' else 0
        return c_val + b_val
    except ValueError:
        return 0

st.title("🏙️ Real Estate Raw to Final Processor")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    projects = df['Property'].unique()
    
    st.header("Step 2: Global Settings")
    
    # Single Loading Factor for the whole app
    global_loading = st.number_input("Enter Loading Factor (applied to all projects)", 1.0, 2.0, 1.4, step=0.01)
    
    st.subheader("BHK Area Ranges (Per Project)")
    st.info("Define the SQ.FT ranges to categorize BHK (e.g., 0-700:1 BHK)")
    
    bhk_configs = {}
    for proj in projects:
        # We still need ranges per project as area sizes vary by builder/location
        bhk_ranges = st.text_input(f"BHK Ranges for {proj}", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK", key=f"r_{proj}")
        bhk_configs[proj] = bhk_ranges

    if st.button("Generate Final Report"):
        # 1. Extract and Calculate Area
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.7639
        
        # 2. Apply Logic
        def apply_logic(row):
            # Use the global loading factor
            saleable = row['Carpet Area(SQ.FT)'] * global_loading
            
            # Use project-specific BHK ranges
            bhk_range_str = bhk_configs.get(row['Property'], "")
            final_bhk = "Other"
            try:
                for r in bhk_range_str.split(','):
                    limit, name = r.split(':')
                    low, high = map(float, limit.split('-'))
                    if low <= row['Carpet Area(SQ.FT)'] <= high:
                        final_bhk = name.strip()
                        break
            except:
                pass
            return pd.Series([saleable, final_bhk])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_logic, axis=1)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # 3. Create Summary
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 
            'Property': 'count'
        }).rename(columns={'Property': 'Units', 'APR': 'Avg APR'}).reset_index()

        # 4. Excel Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Final Data')
            summary.to_excel(writer, index=False, sheet_name='Summary')
        
        st.download_button("📥 Download Final Excel", output.getvalue(), "Final_Analysis.xlsx")
        st.success("Analysis Complete!")
        st.dataframe(summary)
