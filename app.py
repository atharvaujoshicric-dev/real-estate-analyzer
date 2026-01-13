import streamlit as st
import pandas as pd
import re

def extract_total_area(text):
    if pd.isna(text) or text == "":
        return 0.0
    
    # 1. Regex to find numbers followed by metric units (sq.m. variants)
    # This specifically looks for area components like 58.70 चौ.मी.
    metric_pattern = r'(\d+\.?\d*)\s*(?:चौ\.मी\.|चौरस मीटर|sq\.m\.)'
    
    # Find all metric values in the string
    areas = re.findall(metric_pattern, str(text))
    
    # Convert strings to floats
    float_areas = [float(a) for a in areas]
    
    # 2. Safety Logic: Exclude potential "Plot Areas" 
    # Usually, plot areas or land areas are significantly larger than flat areas.
    # We filter for components that look like flat parts (e.g., < 500 sq.m.)
    # and sum them up as per your Carpet + Balcony + Terrace logic.
    flat_components = [a for a in float_areas if a < 500] 
    
    return round(sum(flat_components), 2)

# --- Streamlit UI ---
st.set_page_config(page_title="Marathi Property Data Extractor", layout="wide")

st.title("🏠 Real Estate Marathi Text Extractor")
st.markdown("""
Upload your raw Excel file. This tool will extract **Carpet + Balcony + Terrace** areas 
from the 'Property Description' column and calculate the total in **SQ.MT**.
""")

uploaded_file = st.file_uploader("Upload Raw Excel File", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    if "Property Description" in df.columns:
        with st.spinner('Processing Marathi text...'):
            # Apply the extraction logic
            df['Carpet Area SQ.MT'] = df['Property Description'].apply(extract_total_area)
            
            st.success("Extraction Complete!")
            st.dataframe(df[['Property Description', 'Carpet Area SQ.MT']].head(10))
            
            # Download Button
            output_file = "Processed_Property_Data.xlsx"
            df.to_excel(output_file, index=False)
            
            with open(output_file, "rb") as file:
                st.download_button(
                    label="Download Ready File",
                    data=file,
                    file_name=output_file,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.error("Error: Could not find a column named 'Property Description' in the uploaded file.")
