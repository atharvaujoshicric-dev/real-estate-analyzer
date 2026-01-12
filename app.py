import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Pro RE Analyzer", layout="wide")

def extract_area_perfect(text):
    if pd.isna(text): return 0
    # Normalize text to handle spaces and Marathi variations
    text = text.replace('ओेपन', 'ओपन').replace('कार्पेट', 'कारपेट').replace('ौ.मी', 'चौ.मी').replace(',', '')
    
    # 1. We ONLY care about the part of the text AFTER the unit/flat is mentioned.
    # This skips all the Land/Survey/Hissa numbers at the start.
    unit_marker = re.search(r'(?:फ्लॅट|युनिट|विंग|flat|unit|floor|मजल्यावरील)', text, re.IGNORECASE)
    if unit_marker:
        text = text[unit_marker.start():]

    total_sqmt = 0.0
    total_sqft = 0.0

    # 2. Logic: Find numbers followed by SQMT or SQFT keywords
    # We use a very flexible regex to handle "चौ. मी.", "चौ.मी", "चौरस मीटर"
    sqmt_pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*मी|चौरस\s*मीटर|sq[\.\s]*mt)'
    sqft_pattern = r'(\d+\.?\d*)\s*(?:चौ[\.\s]*फ[ुू][टट]|sq[\.\s]*ft|square\s*feet)'

    # Find all SQMT matches
    for m in re.finditer(sqmt_pattern, text, re.IGNORECASE):
        val = float(m.group(1))
        prefix = text[max(0, m.start()-30):m.start()].lower()
        # Exclude if it's parking or survey info that leaked into this section
        if not any(k in prefix for k in ['पार्किंग', 'पार्कींग', 'parking', 'सर्व्हे', 'survey']):
            total_sqmt += val

    # 3. Fallback: If no SQMT found, look for SQFT
    if total_sqmt == 0:
        for m in re.finditer(sqft_pattern, text, re.IGNORECASE):
            val = float(m.group(1))
            prefix = text[max(0, m.start()-30):m.start()].lower()
            if not any(k in prefix for k in ['पार्किंग', 'पार्कींग', 'parking']):
                total_sqft += val
        if total_sqft > 0:
            total_sqmt = total_sqft / 10.764

    return total_sqmt

st.title("🏙️ Professional Real Estate Analyzer")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.header("Settings")
    col1, col2 = st.columns(2)
    loading = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("Generate Final Excel"):
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_perfect)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        def get_bhk(area):
            try:
                for r in bhk_input.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            
            summary = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summary.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index()
            s2.columns = ['Property', 'Count of Consideration Value']
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("Analysis Finished. The logic now strictly ignores Land/Survey numbers.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
