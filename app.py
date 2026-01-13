import streamlit as st
import pandas as pd
import re
import io

def extract_area_refined(text):
    if pd.isna(text) or text == "":
        return 0.0
    
    # 1. Cleanup: Standardize spaces and remove tabs/newlines
    text = " ".join(str(text).split())
    text = text.replace(' ,', ',').replace(', ', ',')

    # 2. METRIC EXTRACTION (SQ.MT / चौ.मी.)
    # This regex handles: चौ.मी., चौ. मी., चौरस मीटर, sq.m., sq mtr
    metric_regex = r'(\d+\.?\d*)\s*(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    
    # Split text by metric units to check context for each number found
    segments = re.split(metric_regex, text, flags=re.IGNORECASE)
    
    total_metric = 0.0
    found_any_metric = False
    
    # segments format: [text_before, num1, text_between, num2, text_after]
    for i in range(1, len(segments), 2):
        val = float(segments[i])
        context_before = segments[i-1].lower()
        
        # LOGIC: 
        # - Exclude large project/plot areas (>500 sq.m)
        # - Exclude areas associated with "Parking"
        if 0 < val < 500:
            if "पार्किंग" in context_before or "parking" in context_before:
                continue
            total_metric += val
            found_any_metric = True
            
    if found_any_metric and total_metric > 0:
        return round(total_metric, 2)
    
    # 3. FALLBACK: SQ.FT TO SQ.MT CONVERSION
    # If no Metric values found, look for Sq.Ft and divide by 10.764
    ft_regex = r'(\d+\.?\d*)\s*(?:चौ\.?\s*फू\.?|चौरस\s*फूट|sq\.?\s*f(?:t)?\.?)'
    ft_segments = re.split(ft_regex, text, flags=re.IGNORECASE)
    
    total_ft = 0.0
    found_any_ft = False
    for i in range(1, len(ft_segments), 2):
        val = float(ft_segments[i])
        context_before = ft_segments[i-1].lower()
        
        if 0 < val < 5000: # Typical upper limit for flat sq.ft
            if "पार्किंग" in context_before or "parking" in context_before:
                continue
            total_ft += val
            found_any_ft = True
            
    if found_any_ft and total_ft > 0:
        return round(total_ft / 10.764, 2)
    
    return 0.0

# --- Streamlit Web Interface ---
st.set_page_config(page_title="Marathi Property Extractor", page_icon="🏢")

st.title("🏠 Marathi Property Area Extractor")
st.write("Upload your Excel file to extract Carpet + Balcony + Terrace areas automatically.")

uploaded_file = st.file_uploader("Choose an Excel file", type="xlsx")

if uploaded_file:
    # Read the file
    df = pd.read_excel(uploaded_file)
    
    if "Property Description" in df.columns:
        with st.spinner('Extracting data...'):
            # Apply the logic
            df['Carpet Area SQ.MT'] = df['Property Description'].apply(extract_area_refined)
            
            st.success("Processing Complete!")
            
            # Show preview
            st.subheader("Data Preview (First 10 rows)")
            st.write(df[['Property Description', 'Carpet Area SQ.MT']].head(10))
            
            # Export to Excel in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            processed_data = output.getvalue()
            
            # Download button
            st.download_button(
                label="📥 Download Processed Excel File",
                data=processed_data,
                file_name="Processed_Property_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("Error: The file must have a column named 'Property Description'.")
