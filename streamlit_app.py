import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# 1. Setup Page and Title
st.set_page_config(page_title="Appointment System", page_icon="📅")
st.title("📅 Manage Your Appointment")

# 2. Configuration & API Setup
try:
    # This MUST match your Secrets box exactly
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("⚠️ Gemini API Key not found. Please set 'GOOGLE_API_KEY' in Secrets.")
    st.stop()

# 3. Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read()

# 4. Sidebar View Selection
view = st.sidebar.radio("Select View", ["Customer View", "Technician Dashboard"])

if view == "Customer View":
    job_id = st.text_input("Enter your Work Order ID", placeholder="e.g., WO-001")
    
    if job_id:
        # Search for the job in the dataframe (Assuming column 1 is 'ID')
        job_data = df[df.iloc[:, 0].astype(str) == job_id]
        
        if not job_data.empty:
            st.success(f"Found appointment for {job_data.iloc[0, 1]}")
            st.write(f"**Current Slot:** {job_data.iloc[0, 5]}")
            
            # Simple Chat logic for rescheduling
            user_msg = st.chat_input("Ask to reschedule...")
            if user_msg:
                response = model.generate_content(f"The customer for Job {job_id} says: {user_msg}. Help them reschedule.")
                st.chat_message("assistant").write(response.text)
        else:
            st.error("Work Order ID not found.")

else:
    st.header("👷 Technician Dashboard")
    st.dataframe(df)
