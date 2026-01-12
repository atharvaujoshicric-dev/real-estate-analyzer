import streamlit as st
import pandas as pd
import re
import io
from decimal import Decimal

st.set_page_config(page_title="Professional RE Analyzer", layout="wide")

def extract_area_final_fixed(text):
    if pd.isna(text) or not text.strip(): return None
    
    # Standardize all Marathi variations of Carpet and Balcony spelling
    text = text.replace('कार्पेट', 'कारपेट').replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी').replace(',', '')
    
    total_sqmt = Decimal('0')
    
    # This pattern finds ANY number followed by area keywords, 
    # capturing the preceding context to filter out parking/survey numbers
    pattern = r'(.{0,40})(\d+\.?\d*)\s*(?:चौ[\.\s]*मी|चौरस\s*मीटर|sq[\.\s]*mt)'
    matches = re.finditer(pattern, text, re.IGNORECASE)
    
    found_any = False
    for m in matches:
        prefix = m.group(1).lower()
        val = Decimal(m.group(2))
        
        # Professional Exclusion: Reject if attached to parking or land survey jargon
        exclude_terms = ['पार्किंग', 'पार्कींग', 'parking', 'सर्व्हे', 'survey', 'गट नं', 'स.नं', 'hissa']
        if any(term in prefix for term in exclude_terms):
            continue
            
        # Reject if the number is too large (likely a land survey number > 500 sqm)
        if val >= Decimal('500'):
            continue
            
        total_sqmt += val
        found_any = True

    return float(total_sqmt) if found_any else None

st.title("🏙️ Professional Real Estate Analyzer")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.header("Settings")
    col1, col2 = st.columns(2)
    load_val = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.0001, format="%.4f")
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Run Final Verified Process"):
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_final_fixed)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'].apply(lambda x: float(Decimal(str(x)) * Decimal('10.764')) if x else None)
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'].apply(lambda x: float(Decimal(str(x)) * Decimal(str(load_val))) if x else None)
        df['APR'] = df.apply(lambda r: float(Decimal(str(r['Consideration Value'])) / Decimal(str(r['Saleable Area']))) if r['Saleable Area'] else None, axis=1)
        
        def get_bhk(area):
            if not area: return ""
            for r in bhk_input.split(','):
                limits, name = r.split(':')
                low, high = map(float, limits.split('-'))
                if low <= area <= high: return name.strip()
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            # summary (Starts Row 3)
            summ = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summ.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            # Sheet1 (No header)
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            # Sheet2 (Row 3 + Total)
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index().rename(columns={'Consideration Value': 'Count of Consideration Value'})
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            # Sheet3 (Row 3)
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Verified and Ready.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
