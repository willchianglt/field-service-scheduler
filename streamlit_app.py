import streamlit as st
import google.generativeai as genai

st.title("🛠️ System Debugger")

# 1. Check Streamlit Secrets connection
st.header("Step 1: Secrets Check")
if not st.secrets:
    st.error("Empty Secrets: The app cannot see any secrets at all.")
else:
    st.success("Secrets object detected.")
    # Check for the specific key name
    found_key = "GOOGLE_API_KEY" in st.secrets
    st.write(f"Is 'GOOGLE_API_KEY' found? **{found_key}**")

# 2. Check Gemini Configuration
st.header("Step 2: Gemini Check")
if found_key:
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        st.success("Gemini configured successfully!")
    except Exception as e:
        st.error(f"Error configuring Gemini: {e}")
else:
    st.warning("Skipping Gemini check because key is missing.")

# 3. Check Google Sheets
st.header("Step 3: Google Sheets Check")
try:
    if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        st.success("Google Sheets configuration found in Secrets.")
    else:
        st.error("Google Sheets configuration MISSING in Secrets.")
except Exception as e:
    st.error(f"Error reading Sheets secrets: {e}")

st.divider()
st.info("After you see the results above, tell me what 'Step 1' says!")
