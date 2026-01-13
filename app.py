import streamlit as st
import pandas as pd
import re
import io
from decimal import Decimal

st.set_page_config(page_title="Professional RE Analyzer", layout="wide")

def extract_area_final_verified(text):
    """
    Surgical extraction: Sums Carpet + Balcony + Terrace.
    Strictly ignores Parking and Land Survey numbers.
    """
    if pd.isna(text) or not text.strip(): return None
    
    # Standardize Marathi text
    text = text.replace(',', '').replace('कार्पेट', 'कारपेट').replace('ओेपन', 'ओपन').replace('ौ.मी', 'चौ.मी')
    
    sqmt_total = Decimal('0')
    sqft_total = Decimal('0')
    found_any = False
    
    # Patterns for Metric and Imperial units
    patterns = [
        (r'(\d+\.?\d*)\s*(?:चौ[\.\s]*मी|चौरस\s*मीटर|sq[\.\s]*mt)', 'sqmt'),
        (r'(\d+\.?\d*)\s*(?:चौ[\.\s]*फ[ुू][टट]|sq[\.\s]*ft|square\s*feet|फ[ुू][टट])', 'sqft')
    ]
    
    for pattern, unit_type in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            val = Decimal(m.group(1))
            
            # Context Check (40 chars before number)
            prefix = text[max(0, m.start()-40):m.start()].lower()
            # Professional Exclusion Keywords
            exclude_logic = ['पार्किंग', 'पार्कींग', 'parking', 'park', 'सर्व्हे', 'survey', 'स.नं', 'गट नं', 'hissa', 'एकूण क्षेत्र']
            
            if any(k in prefix for k in exclude_logic) or val > Decimal('500'):
                continue 
            
            if unit_type == 'sqmt':
                sqmt_total += val
            else:
                sqft_total += val
            found_any = True

    if sqmt_total > 0:
        return float(sqmt_total)
    elif sqft_total > 0:
        # Fallback formula: sqmt = sqft / 10.764
        return float(sqft_total / Decimal('10.764'))
    
    return None

st.title("🏙️ Professional Real Estate Data Processor")
st.markdown("---")

uploaded_file = st.file_uploader("Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("Settings")
    col1, col2 = st.columns(2)
    load_val = col1.number_input("Loading Factor", 1.0, 2.0, 1.4, step=0.0001, format="%.4f")
    bhk_input = col2.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Generate Final Verified File"):
        # The line that caused your error is now fixed (name matches function above)
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_final_verified)
        
        # High precision math using Decimal
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
        
        # Excel Generation with exact Sheet offsets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            
            summ = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summ.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            df['Property'].value_counts().reset_index().to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index().rename(columns={'Consideration Value': 'Count of Consideration Value'})
            s2_final = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2_final.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({'APR': 'mean', 'Property': 'count'}).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Generated Successfully.")
        st.download_button("Download Final.xlsx", output.getvalue(), "Final.xlsx")
