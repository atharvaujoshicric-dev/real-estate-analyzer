import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Universal RE Analyzer", layout="wide")

def extract_area_final(text):
    if pd.isna(text): return 0
    # Normalize Marathi text to handle all variations
    text = text.replace(',', '').replace('ओेपन', 'ओपन').replace('कार्पेट', 'कारपेट').replace('ौ.मी', 'चौ.मी')
    
    sqmt_total = 0.0
    sqft_total = 0.0
    
    # regex for number: ([\d\.]+)
    # We find every number and look at the words immediately following it
    matches = list(re.finditer(r'(\d+\.?\d*)', text))
    
    for m in matches:
        val = float(m.group(1))
        
        # 1. Get Context (40 chars before, 40 chars after)
        suffix = text[m.end():m.end()+40].lower()
        prefix = text[max(0, m.start()-40):m.start()].lower()
        
        # 2. Exclude Land/Survey numbers (If 'survey', 'स.नं', or 'Hissa' is nearby)
        if any(k in prefix for k in ['सर्व्हे', 'स.नं', 'गट नं', 'survey', 'hissa']):
            continue
            
        # 3. Exclude Parking (If 'parking' or 'पार्किंग' is nearby)
        if any(k in prefix for k in ['पार्किंग', 'पार्कींग', 'parking', 'park']):
            continue

        # 4. Identify SQMT values
        if any(k in suffix for k in ['चौ.मी', 'चौरस मीटर', 'sq.mt', 'sqmt', 'sq.mtr']):
            sqmt_total += val
        
        # 5. Identify SQFT values (only if we need fallback later)
        elif any(k in suffix for k in ['चौ.फुट', 'चौ.फूट', 'चौ. फूट', 'sq.ft', 'sqft', 'square feet', 'फूट', 'फुट']):
            sqft_total += val

    # Logic: Use SQMT sum if found. If 0, use SQFT sum and divide by 10.764
    if sqmt_total > 0:
        return sqmt_total
    elif sqft_total > 0:
        return sqft_total / 10.764
    
    return 0

st.title("🏙️ Professional Real Estate Analyzer")
st.markdown("---")

uploaded_file = st.file_uploader("1. Upload Raw Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.header("2. Analysis Parameters")
    col1, col2 = st.columns(2)
    with col1:
        loading = st.number_input("Enter Loading Factor", 1.0, 2.0, 1.4, step=0.01)
    with col2:
        bhk_ranges = st.text_input("BHK Ranges (SQFT)", "0-700:1 BHK, 701-1000:2 BHK, 1001-2000:3 BHK")

    if st.button("🚀 Generate Final.xlsx"):
        # Processing - Strict Precision, No Rounding
        df['Carpet Area(SQ.MT)'] = df['Property Description'].apply(extract_area_final)
        df['Carpet Area(SQ.FT)'] = df['Carpet Area(SQ.MT)'] * 10.764
        df['Saleable Area'] = df['Carpet Area(SQ.FT)'] * loading
        df['APR'] = df['Consideration Value'] / df['Saleable Area']
        
        def get_bhk(area):
            try:
                for r in bhk_ranges.split(','):
                    limits, name = r.split(':')
                    low, high = map(float, limits.split('-'))
                    if low <= area <= high: return name.strip()
            except: pass
            return ""
        df['Configuration'] = df['Carpet Area(SQ.FT)'].apply(get_bhk)

        # Excel Export with exact sheet structure
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='in')
            
            # summary
            summ = df.groupby(['Property', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            summ.to_excel(writer, startrow=2, index=False, sheet_name='summary')
            
            # Sheet1 (No Headers)
            s1 = df['Property'].value_counts().reset_index()
            s1.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
            # Sheet2 (With Grand Total)
            s2 = df.groupby('Property')['Consideration Value'].count().reset_index()
            s2.columns = ['Property', 'Count of Consideration Value']
            s2 = pd.concat([s2, pd.DataFrame([['Grand Total', s2.iloc[:,1].sum()]], columns=s2.columns)])
            s2.to_excel(writer, startrow=2, index=False, sheet_name='Sheet2')
            
            # Sheet3
            s3 = df.groupby(['Property', 'Rera Code', 'Configuration', 'Carpet Area(SQ.FT)']).agg({
                'APR': 'mean', 'Property': 'count'
            }).rename(columns={'APR': 'Average of APR', 'Property': 'Count of Property'}).reset_index()
            s3.to_excel(writer, startrow=2, index=False, sheet_name='Sheet3')

        st.success("File Generated Successfully!")
        st.download_button("📥 Download Final.xlsx", output.getvalue(), "Final.xlsx")
