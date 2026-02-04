"""
Field Service Scheduling System - Streamlit App
100% Free Appointment System using Google Sheets, Gemini API, and Gmail
"""

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

# Configure page
st.set_page_config(
    page_title="Service Appointment Manager",
    page_icon="📅",
    layout="wide"
)

# Load environment variables (these should be set in Streamlit Cloud secrets)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
GMAIL_ADDRESS = st.secrets.get("GMAIL_ADDRESS", os.getenv("GMAIL_ADDRESS", ""))
GMAIL_APP_PASSWORD = st.secrets.get("GMAIL_APP_PASSWORD", os.getenv("GMAIL_APP_PASSWORD", ""))

# Configure Gemini with a specific stable version
if GEMINI_API_KEY:
    import google.generativeai.types as types
    genai.configure(api_key=GEMINI_API_KEY)
    
    # This explicit model naming usually bypasses the v1beta 404 error
    model = genai.GenerativeModel(model_name="gemini-3-flash-preview")
    )
else:
    st.error("⚠️ Gemini API Key not found. Please set it in Streamlit secrets.")

# Column mapping based on your sheet structure
COLUMNS = {
    'WORK_ORDER': 'Work_Order',
    'CUSTOMER_NAME': 'Customer_Name',
    'CUSTOMER_EMAIL': 'Customer_Email',
    'ADDRESS': 'Address',
    'POSTAL_CODE': 'Postal_Code',
    'APPOINTMENT_DATE': 'Appointment_Date',
    'APPOINTMENT_TIME': 'Appointment_Time',
    'STATUS': 'Status',
    'TECH_ID': 'Tech_ID'
}

# ============================================================================
# GOOGLE SHEETS CONNECTION
# ============================================================================

@st.cache_resource(ttl=60)
def get_sheet_connection():
    """Create and cache Google Sheets connection"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

def load_appointments():
    """Load all appointments from Google Sheet"""
    try:
        conn = get_sheet_connection()
        if conn:
            df = conn.read(ttl=0)  # ttl=0 means always fetch fresh data
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading appointments: {e}")
        return pd.DataFrame()

def update_appointment(work_order, new_date, new_time, new_status="Rescheduled"):
    """Update an appointment in Google Sheet"""
    try:
        conn = get_sheet_connection()
        if not conn:
            return False
        
        # Load current data
        df = load_appointments()
        
        # Find the row with matching work order
        mask = df[COLUMNS['WORK_ORDER']] == work_order
        
        if not mask.any():
            st.error(f"Work Order {work_order} not found")
            return False
        
        # Update the fields
        df.loc[mask, COLUMNS['APPOINTMENT_DATE']] = new_date
        df.loc[mask, COLUMNS['APPOINTMENT_TIME']] = new_time
        df.loc[mask, COLUMNS['STATUS']] = new_status
        
        # Write back to sheet
        conn.update(data=df)
        
        return True
        
    except Exception as e:
        st.error(f"Error updating appointment: {e}")
        return False

# ============================================================================
# GEMINI AI CHATBOT
# ============================================================================

def initialize_chat_session(appointment_info):
    """Initialize Gemini chat session with appointment context"""
    
    system_prompt = f"""You are a helpful appointment scheduling assistant for a field service company.

Current appointment details:
- Work Order: {appointment_info['Work_Order']}
- Customer Name: {appointment_info['Customer_Name']}
- Current Date: {appointment_info.get('Appointment_Date', 'Not set')}
- Current Time: {appointment_info.get('Appointment_Time', 'Not set')}
- Address: {appointment_info['Address']}
- Status: {appointment_info['Status']}

Your job is to:
1. Help the customer reschedule their appointment if needed
2. Ask for their preferred date and time
3. Confirm the new appointment details
4. Be friendly and professional

When the customer provides a new date and time, respond with EXACTLY this format:
RESCHEDULE_REQUEST: [date] | [time]

Example: RESCHEDULE_REQUEST: 2026-02-20 | 3:00 PM

Important:
- Always ask for BOTH date AND time
- Confirm details before finalizing
- Use format YYYY-MM-DD for dates
- Use 12-hour format for times (e.g., 2:00 PM)
"""
    
    return system_prompt

def chat_with_gemini(message, chat_history, system_prompt):
    """Send message to Gemini using the stable chat session method"""
    try:
        # Create a new chat session with the system prompt instructions
        chat = model.start_chat(history=[])
        # Send the system prompt first (invisible to user) to set the rules
        chat.send_message(system_prompt)
        # Send the actual user message
        response = chat.send_message(message)
        return response.text
    except Exception as e:
        return f"Model Error: {e}. Try checking your API key permissions in Google AI Studio."
        
def parse_reschedule_request(response_text):
    """Parse reschedule request from Gemini response"""
    if "RESCHEDULE_REQUEST:" in response_text:
        try:
            # Extract the line with reschedule request
            request_line = [line for line in response_text.split('\n') if 'RESCHEDULE_REQUEST:' in line][0]
            
            # Parse date and time
            parts = request_line.split('RESCHEDULE_REQUEST:')[1].strip().split('|')
            
            if len(parts) == 2:
                new_date = parts[0].strip()
                new_time = parts[1].strip()
                return new_date, new_time
        except:
            pass
    
    return None, None

# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_late_alert_email(appointment):
    """Send late arrival alert email to customer"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Update: Your Service Appointment - Work Order {appointment['Work_Order']}"
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = appointment['Customer_Email']
        
        # Email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b6b;">Service Update - Running Late</h2>
                
                <p>Dear {appointment['Customer_Name']},</p>
                
                <p>We wanted to inform you that our technician is running slightly behind schedule and may arrive later than your scheduled appointment time.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #ff6b6b; margin: 20px 0;">
                    <strong>Your Appointment Details:</strong><br>
                    Work Order: {appointment['Work_Order']}<br>
                    Scheduled: {appointment.get('Appointment_Date', 'N/A')} at {appointment.get('Appointment_Time', 'N/A')}<br>
                    Address: {appointment['Address']}<br>
                    Technician: {appointment['Tech_ID']}
                </div>
                
                <p>We apologize for any inconvenience this may cause. If you need to reschedule, please use the link provided in your original confirmation email.</p>
                
                <p>Thank you for your patience and understanding.</p>
                
                <p style="margin-top: 30px;">
                    Best regards,<br>
                    <strong>Field Service Team</strong>
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# ============================================================================
# CUSTOMER VIEW
# ============================================================================

def customer_view():
    """Customer interface for rescheduling appointments"""
    
    st.title("📅 Manage Your Appointment")
    
    # Get Work Order ID from URL parameter or input
    query_params = st.query_params
    work_order_from_url = query_params.get("id", [""])[0] if isinstance(query_params.get("id"), list) else query_params.get("id", "")
    
    work_order = st.text_input(
        "Enter your Work Order ID",
        value=work_order_from_url,
        placeholder="e.g., WO-001"
    )
    
    if not work_order:
        st.info("👆 Please enter your Work Order ID to view your appointment")
        return
    
    # Load appointment data
    df = load_appointments()
    
    if df.empty:
        st.error("Unable to load appointment data")
        return
    
    # Find appointment
    appointment = df[df[COLUMNS['WORK_ORDER']] == work_order]
    
    if appointment.empty:
        st.error(f"❌ Work Order '{work_order}' not found")
        return
    
    # Get appointment details
    appt = appointment.iloc[0].to_dict()
    
    # Display appointment details
    st.success(f"✅ Found your appointment")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"""
        **Customer:** {appt['Customer_Name']}
        
        **Address:** {appt['Address']}, {appt['Postal_Code']}
        
        **Scheduled:** {appt.get('Appointment_Date', 'Not set')} at {appt.get('Appointment_Time', 'Not set')}
        """)
    
    with col2:
        st.info(f"""
        **Work Order:** {appt['Work_Order']}
        
        **Status:** {appt['Status']}
        
        **Technician:** {appt['Tech_ID']}
        """)
    
    st.divider()
    
    # Chat interface
    st.subheader("💬 Chat with AI Assistant")
    
    # Initialize chat history in session state
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
        st.session_state.system_prompt = initialize_chat_session(appt)
    
    # Display chat messages
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.chat_history:
            with st.chat_message(message['role']):
                st.write(message['content'])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        
        # Add user message to history
        st.session_state.chat_history.append({
            'role': 'user',
            'content': prompt
        })
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = chat_with_gemini(
                    prompt,
                    st.session_state.chat_history,
                    st.session_state.system_prompt
                )
                
                st.write(response)
        
        # Add assistant response to history
        st.session_state.chat_history.append({
            'role': 'assistant',
            'content': response
        })
        
        # Check if response contains reschedule request
        new_date, new_time = parse_reschedule_request(response)
        
        if new_date and new_time:
            st.success("🎯 Reschedule request detected!")
            
            if st.button("✅ Confirm Reschedule", type="primary"):
                with st.spinner("Updating your appointment..."):
                    success = update_appointment(work_order, new_date, new_time)
                    
                    if success:
                        st.success(f"✅ Appointment rescheduled to {new_date} at {new_time}!")
                        st.balloons()
                        
                        # Clear chat history
                        st.session_state.chat_history = []
                        
                        # Refresh to show updated data
                        st.rerun()
                    else:
                        st.error("Failed to update appointment. Please try again.")
    
    # Quick action buttons
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Start New Chat"):
            st.session_state.chat_history = []
            st.rerun()
    
    with col2:
        if appt['Status'] == 'Pending' or appt['Status'] == 'Email Sent':
            if st.button("✅ Confirm Appointment"):
                update_appointment(work_order, 
                                 appt.get('Appointment_Date', ''), 
                                 appt.get('Appointment_Time', ''), 
                                 'Confirmed')
                st.success("Appointment confirmed!")
                st.rerun()

# ============================================================================
# TECHNICIAN VIEW
# ============================================================================

def technician_view():
    """Technician dashboard for viewing and managing appointments"""
    
    st.title("🔧 Technician Dashboard")
    
    # Password protection for technician view
    if 'tech_authenticated' not in st.session_state:
        st.session_state.tech_authenticated = False
    
    if not st.session_state.tech_authenticated:
        password = st.text_input("Enter technician password", type="password")
        
        # Simple password (in production, use proper authentication)
        TECH_PASSWORD = st.secrets.get("TECH_PASSWORD", os.getenv("TECH_PASSWORD", "admin123"))
        
        if st.button("Login"):
            if password == TECH_PASSWORD:
                st.session_state.tech_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        
        st.info("💡 Demo password: admin123 (set TECH_PASSWORD in secrets for production)")
        return
    
    # Load appointments
    df = load_appointments()
    
    if df.empty:
        st.warning("No appointments found")
        return
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Jobs", len(df))
    
    with col2:
        pending = len(df[df[COLUMNS['STATUS']].isin(['Pending', 'Email Sent'])])
        st.metric("Pending", pending)
    
    with col3:
        confirmed = len(df[df[COLUMNS['STATUS']] == 'Confirmed'])
        st.metric("Confirmed", confirmed)
    
    with col4:
        completed = len(df[df[COLUMNS['STATUS']] == 'Completed'])
        st.metric("Completed", completed)
    
    st.divider()
    
    # Filter options
    st.subheader("📋 Job List")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=df[COLUMNS['STATUS']].unique(),
            default=df[COLUMNS['STATUS']].unique()
        )
    
    with col2:
        tech_filter = st.multiselect(
            "Filter by Technician",
            options=df[COLUMNS['TECH_ID']].unique(),
            default=df[COLUMNS['TECH_ID']].unique()
        )
    
    with col3:
        search = st.text_input("Search (Work Order or Name)")
    
    # Apply filters
    filtered_df = df[
        (df[COLUMNS['STATUS']].isin(status_filter)) &
        (df[COLUMNS['TECH_ID']].isin(tech_filter))
    ]
    
    if search:
        filtered_df = filtered_df[
            filtered_df[COLUMNS['WORK_ORDER']].str.contains(search, case=False, na=False) |
            filtered_df[COLUMNS['CUSTOMER_NAME']].str.contains(search, case=False, na=False)
        ]
    
    # Display jobs
    for idx, row in filtered_df.iterrows():
        with st.expander(f"🔹 {row['Work_Order']} - {row['Customer_Name']} - {row['Status']}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Customer:** {row['Customer_Name']}")
                st.write(f"**Email:** {row['Customer_Email']}")
                st.write(f"**Address:** {row['Address']}, {row['Postal_Code']}")
                st.write(f"**Appointment:** {row.get('Appointment_Date', 'Not set')} at {row.get('Appointment_Time', 'Not set')}")
                st.write(f"**Technician:** {row['Tech_ID']}")
            
            with col2:
                st.write(f"**Status:** {row['Status']}")
                
                # Action buttons
                if st.button(f"📧 Send Late Alert", key=f"late_{row['Work_Order']}"):
                    if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
                        with st.spinner("Sending email..."):
                            success = send_late_alert_email(row.to_dict())
                            if success:
                                st.success("✅ Late alert sent!")
                            else:
                                st.error("❌ Failed to send email")
                    else:
                        st.error("Email credentials not configured")
                
                if st.button(f"✅ Mark Complete", key=f"complete_{row['Work_Order']}"):
                    update_appointment(
                        row['Work_Order'],
                        row.get('Appointment_Date', ''),
                        row.get('Appointment_Time', ''),
                        'Completed'
                    )
                    st.success("Marked as complete!")
                    st.rerun()
    
    st.divider()
    
    # Bulk actions
    st.subheader("⚡ Bulk Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Data"):
            st.cache_resource.clear()
            st.rerun()
    
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.tech_authenticated = False
            st.rerun()

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point"""
    
    # Sidebar navigation
    st.sidebar.title("🗓️ Appointment System")
    
    view = st.sidebar.radio(
        "Select View",
        ["Customer View", "Technician Dashboard"],
        index=0
    )
    
    st.sidebar.divider()
    
    # Configuration status
    st.sidebar.subheader("⚙️ Configuration Status")
    
    if GEMINI_API_KEY:
        st.sidebar.success("✅ Gemini API configured")
    else:
        st.sidebar.error("❌ Gemini API key missing")
    
    if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
        st.sidebar.success("✅ Email configured")
    else:
        st.sidebar.warning("⚠️ Email not configured")
    
    st.sidebar.divider()
    
    st.sidebar.info("""
    **100% Free Stack:**
    - Streamlit (Free hosting)
    - Google Sheets (Free)
    - Gemini API (Free tier)
    - Gmail (Free)
    """)
    
    # Route to appropriate view
    if view == "Customer View":
        customer_view()
    else:
        technician_view()

# ============================================================================
# RUN APP
# ============================================================================

if __name__ == "__main__":
    main()
