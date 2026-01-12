import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Universal RE Analyzer", layout="wide")

def extract_total_area(text):
    if pd.isna(text): return 0
    
    # Standardize Marathi text to handle spelling variations (ओेपन vs ओपन)
    text = text.replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी')
    
    # 1. Search for Carpet (Looks for numbers after 'कारपेट क्षेत्र' or 'क्षेत्र')
    # We use a non-greedy search to find the number closest to the unit keywords
    carpet_match = re.search(r'(?:कारपेट क्षेत्र|carpet area)\s*([\d\.]+)', text, re.IGNORECASE)
    
    # 2. Search for Balcony (Looks for 'बाल्कनी', 'ओपन बाल्कनी', 'सीटआऊट')
    balcony_match = re.search(r'(?:ओपन बाल्कनी|बाल्कनी|सीटआऊट|dry balcony)\s*(?:क्षेत्र)?\s*([\d\.]+)', text, re.IGNORECASE)
    
    # 3. Fallback for "Total Area" if the above fails
    # Finds the area mentioned after floor/unit details
    fallback = re.search(r'(?:फ्लॅट|unit|युनिट).*?क्षेत्र\s*([\d\.]+)', text, re.IGNORECASE)

    c_val = float(carpet_match.group(1)) if carpet_match else 0
    b_val = float(balcony_match.group(1)) if balcony_match else 0
    
    # If we found nothing with specific labels, use the fallback
    if c_val == 0 and fallback:
        c_val = float(fallback.group(1))
        
    return c_val + b_val

st.title("🏙️ Universal Real Estate Processor")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.sidebar.header("Global Configuration")
    global_loading = st.sidebar.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    global_bhk = st.sidebar.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("Generate Corrected Final Excel"):
        # Process Areas
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_total_area)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.7639
        
        # Calculate Saleable & BHK
        def apply_logic(row):
            saleable = row['Carpet Area(SQ.FT)'] * global_loading
            area_ft = row['Carpet Area(SQ.FT)']
            label = "Other"
            try:
                for r in global_bhk.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area_ft <= high:
                        label = name.strip()
                        break
            except: pass
            return pd.Series([saleable, label])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_logic, axis=1)
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # Summaries
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 'Property': 'count'
        }).rename(columns={'Property': 'Count of Property', 'APR': 'Average of APR'}).reset_index()

        # Output
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            summary.to_excel(writer, index=False, sheet_name='summary')
            # Extra counts sheet
            df['Property'].value_counts().to_excel(writer, sheet_name='Property Counts')

        st.success("Transformation complete. Logic now sums Carpet + Balcony correctly.")
        st.download_button("📥 Download Corrected Excel", output.getvalue(), "Final_Corrected.xlsx")
