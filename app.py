import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="RE Analyzer Pro", layout="wide")

def extract_correct_unit_area(text):
    """
    Extracts only the flat/unit carpet and balcony area.
    Ignores Land/Survey areas by looking for keywords specific to the unit.
    """
    if pd.isna(text): return 0
    
    # Clean text to remove extra spaces
    text = " ".join(text.split())

    # 1. Look for Carpet Area specifically. 
    # This regex looks for 'कारपेट क्षेत्र' or 'carpet area' and captures the number following it.
    carpet_match = re.search(r'(?:कारपेट क्षेत्र|carpet area)\s*(\d+\.?\d*)', text, re.IGNORECASE)
    
    # 2. Look for Balcony Area specifically.
    balcony_match = re.search(r'(?:बाल्कनी|balcony|सीटआऊट)\s*क्षेत्र\s*(\d+\.?\d*)', text, re.IGNORECASE)
    
    # 3. Fallback for older formats: Look for area mentioned after the Flat Number
    if not carpet_match:
        # Finds a number after "फ्लॅट नं." or "Unit No."
        fallback_match = re.search(r'(?:फ्लॅट नं|फ्लॅट नंबर|unit no).*?क्षेत्र\s*(\d+\.?\d*)', text, re.IGNORECASE)
        carpet_val = float(fallback_match.group(1)) if fallback_match else 0
    else:
        carpet_val = float(carpet_match.group(1))

    balcony_val = float(balcony_match.group(1)) if balcony_match else 0
    
    return carpet_val + balcony_val

st.title("🏙️ Real Estate Raw to Final Processor (Corrected)")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("⚙️ Global Configuration")
    st.info("Set the parameters once to apply them across the entire file.")
    
    col1, col2 = st.columns(2)
    with col1:
        global_loading = st.number_input("Loading Factor (e.g., 1.4 for 40%)", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        global_bhk_ranges = st.text_input(
            "Global BHK Area Ranges (SQ.FT)", 
            "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK"
        )

    if st.button("🚀 Run Analysis"):
        # --- DATA PROCESSING ---
        
        # Calculate SQMT from Description
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_correct_unit_area)
        
        # Convert to SQFT
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.7639
        
        def apply_final_logic(row):
            # Apply loading
            saleable = row['Carpet Area(SQ.FT)'] * global_loading
            
            # Apply BHK Range Logic
            area_ft = row['Carpet Area(SQ.FT)']
            config = "Other"
            try:
                for r in global_bhk_ranges.split(','):
                    bounds, label = r.split(':')
                    low, high = map(float, bounds.split('-'))
                    if low <= area_ft <= high:
                        config = label.strip()
                        break
            except:
                pass
            return pd.Series([saleable, config])

        df[['Saleable Area', 'Configuration']] = df.apply(apply_final_logic, axis=1)
        
        # Final Rate Calculation (APR)
        # Using Consideration Value as per your Correct Excel
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        # --- SUMMARY GENERATION ---
        
        summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
            'APR': 'mean', 
            'Property': 'count'
        }).rename(columns={'Property': 'Count of Property', 'APR': 'Average of APR'}).reset_index()

        # --- EXCEL EXPORT ---
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            summary.to_excel(writer, index=False, sheet_name='summary')
            
            # Additional Sheets for counting properties (matches your Sheet1/Sheet2)
            prop_counts = df['Property'].value_counts().reset_index()
            prop_counts.to_excel(writer, index=False, sheet_name='Property Counts')

        st.success("Analysis Complete! The logic now prioritizes 'Carpet Area' over 'Land Area'.")
        
        st.download_button(
            label="📥 Download Final.xlsx",
            data=output.getvalue(),
            file_name="Final_Processed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.subheader("Market Summary Snapshot")
        st.dataframe(summary)
