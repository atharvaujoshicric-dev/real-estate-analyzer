import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer", layout="wide")

def extract_area(text):
    if pd.isna(text): return 0
    # Logic to find Carpet and Balcony while ignoring Parking
    carpet = re.search(r'(?:क्षेत्र|carpet area)\s*([\d\.]+)', text, re.IGNORECASE)
    balcony = re.search(r'(?:बाल्कनी|balcony)\s*([\d\.]+)', text, re.IGNORECASE)
    total = (float(carpet.group(1)) if carpet else 0) + (float(balcony.group(1)) if balcony else 0)
    return total

st.title("🏙️ Real Estate Raw to Final Processor")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    projects = df['Property'].unique()
    
    st.header("Step 2: Set Loading & BHK Ranges")
    st.info("The app will categorize BHK based on the Carpet Area (SQ.FT) ranges you enter.")
    
    configs = {}
    for proj in projects:
        with st.expander(f"Settings for: {proj}"):
            col1, col2 = st.columns(2)
            load = col1.number_input(f"Loading Factor", 1.0, 2.0, 1.4, key=f"l_{proj}")
            ranges = col2.text_input("BHK Ranges (Low-High:Name)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK", key=f"r_{proj}")
            configs[proj] = {"load": load, "ranges": ranges}

    if st.button("Generate Final Report"):
        # Process Data
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.7639
        
        def apply_proj_logic(row):
            conf = configs[row['Property']]
            saleable = row['Carpet Area(SQ.FT)'] * conf['load']
            
            # BHK Logic
            bhk = "Other"
            try:
                for r in conf['ranges'].split(','):
                    limit, name = r.split(':')
                    low, high = map(float, limit.split('-'))
                    if low <= row['Carpet Area(SQ.FT)'] <= high:
                        bhk = name.strip()
                        break
            except: pass
            return pd.Series([saleable, bhk])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_proj_logic, axis=1)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # Summary Sheet
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'Property': 'Units'}).reset_index()

        # Excel Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Final Data')
            summary.to_excel(writer, index=False, sheet_name='Summary')
        
        st.download_button("📥 Download Final Excel", output.getvalue(), "Final_Analysis.xlsx")
        st.success("Done! Preview below:")
        st.dataframe(summary)
