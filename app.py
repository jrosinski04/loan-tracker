import streamlit as st
from supabase import create_client
import resend
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Loan Tracker", page_icon="seatibiza.png", layout="wide")

ICON_DATA = "seatibiza.png" 
st.markdown("""
    <link rel="apple-touch-icon" href="{ICON_DATA}">
    <link rel="icon" href="{ICON_DATA}">
    <style>
           .block-container {
                padding-top: 50px;
            }

            /* Dark Blurry Blue/Purple Gradient Background */
            .stApp {
                background: linear-gradient(135deg, #0d1128 0%, #1a1025 50%, #0d1128 100%);
            }

            /* Hide the Streamlit footer and hamburger menu */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            
            /* Make the top header transparent */
            [data-testid="stHeader"] {
                background: rgba(0,0,0,0);
            }

            /* =========================================
               1. FORMS & BUTTONS
               ========================================= */
            [data-testid="stForm"] {
                background-color: rgba(255, 255, 255, 0.03) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                border-radius: 15px !important;
                padding: 20px !important;
                backdrop-filter: blur(10px); 
            }

            button[kind="secondary"], button[kind="primary"],
            button[kind="secondaryFormSubmit"], button[kind="primaryFormSubmit"] {
                background-color: rgba(255, 255, 255, 0.08) !important;
                border: 1px solid rgba(255, 255, 255, 0.2) !important;
                color: white !important;
                border-radius: 8px !important;
                backdrop-filter: blur(5px);
                transition: all 0.3s ease !important;
            }

            button[kind="secondary"]:hover, button[kind="primary"]:hover,
            button[kind="secondaryFormSubmit"]:hover, button[kind="primaryFormSubmit"]:hover {
                background-color: rgba(255, 255, 255, 0.15) !important;
                border: 1px solid rgba(255, 255, 255, 0.4) !important;
            }

            /* =========================================
               2. THE PAYMENT HISTORY TABLE
               ========================================= */
            [data-testid="stTable"] {
                background-color: rgba(255, 255, 255, 0.03) !important;
                backdrop-filter: blur(10px) !important;
                border-radius: 10px !important;
                overflow: hidden !important;
            }
            
            /* Table Headers */
            [data-testid="stTable"] th {
                background-color: rgba(255, 255, 255, 0.1) !important;
                color: white !important;
                border-bottom: 1px solid rgba(255, 255, 255, 0.2) !important;
                font-weight: bold !important;
            }
            
            /* Table Rows */
            [data-testid="stTable"] td {
                background-color: transparent !important;
                color: rgba(255, 255, 255, 0.9) !important;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
            }
            
            /* Hover effect for table rows */
            [data-testid="stTable"] tr:hover td {
                background-color: rgba(255, 255, 255, 0.05) !important;
            }

            [data-testid="stTable"] th:first-child {
                display: none !important;
            }
            
    </style>
    """, unsafe_allow_html=True)

# Initalization of clients using secrets
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
resend.api_key = st.secrets["RESEND_API_KEY"]

# Restore the Supabase session
if "session" in st.session_state:
    supabase.auth.set_session(
        st.session_state.session.access_token, 
        st.session_state.session.refresh_token
    )

# Authentication
if "user" not in st.session_state:
    st.title("Car Finance Tracker")
    st.write("Please log in to view your dashboard.")

    with st.form("login_form"):
        email = st.text_input("Email address")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log In"):
            try:
                # Authenticate user with Supabase
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.session_state.session = res.session
                st.rerun()
            except Exception as e:
                st.error("Login failed: " + str(e))

else:
    email = st.session_state.user.email

    # Main dashboard
    col1, image, col2 = st.columns([7,2,1])
    with col1:
        st.title("Car Finance Dashboard")
        st.write(f"Logged in as: **{email}**")

    with image:
        st.image("seatibiza.png", width=200)
    with col2:
        # --- ADD THIS: Account Settings UI ---
        with st.popover("⚙️ Settings"):
            st.write("Update Password")
            new_password = st.text_input("New Password", type="password", key="new_pw")
            if st.button("Save New Password"):
                try:
                    # This securely updates the password in the Supabase vault
                    supabase.auth.update_user({"password": new_password})
                    st.success("Password updated! Log out and log back in to use the new password.")
                except Exception as e:
                    st.error("Failed to update password.")
            
            st.divider()
            
            # Move your existing logout button inside this settings menu to keep it clean!
            if st.button("Logout", use_container_width=True):
                supabase.auth.sign_out()
                if "user" in st.session_state:
                    del st.session_state.user
                if "session" in st.session_state:
                    del st.session_state.session
                st.rerun()

    st.divider()

    # Fetching loan data
    loan_response = supabase.table("loans").select("*").execute()

    if not loan_response.data:
        st.write("No loans found.")
    else:
        loan = loan_response.data[0]
        is_borrower = (email == loan["borrower_email"])

        # Fetching payment details
        pay_response = supabase.table("payments").select("*").eq("loan_id", loan["id"]).order("created_at", desc=True).execute()
        payments = pay_response.data

        # Calculate totals
        total_paid = sum(p["amount"] for p in payments)
        balance = float(loan["total_amount"]) - total_paid

        # Graphical Visual Summary (The Dials)
        dial_col1, dial_col2 = st.columns(2)

        # Dial 1: Total Paid (Green)
        fig1 = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = total_paid,
            title = {'text': "Total Paid (£)", 'font': {'size': 24}},
            number = {'prefix': "£", 'valueformat': ",.2f"},
            gauge = {
                'axis': {'range': [0, float(loan['total_amount'])], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "rgba(76, 175, 80, 0.6)"}, # A nice dark green
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 1,
                'bordercolor': "rgba(255, 255, 255, 0.2)",
                'steps': [
                    {'range': [0, float(loan['total_amount'])], 'color': "rgba(255,255,255,0.05)"} # Light green background
                ]
            }
        ))
        
        # Dial 2: Remaining Balance (Red/Orange)
        fig2 = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = balance,
            title = {'text': "Remaining Balance (£)", 'font': {'size': 24}},
            number = {'prefix': "£", 'valueformat': ",.2f"},
            gauge = {
                'axis': {'range': [0, float(loan['total_amount'])]},
                'bar': {'color': "rgba(244, 67, 54, 0.6)"}, # A nice dark red
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 1,
                'bordercolor': "rgba(255, 255, 255, 0.2)",
                'steps': [
                    {'range': [0, float(loan['total_amount'])], 'color': "rgba(255,255,255,0.05)"} # Light red background
                ]
            }
        ))

        # Render the charts in Streamlit
        fig1.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, margin=dict(l=10, r=10, t=50, b=10))
        fig2.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, margin=dict(l=10, r=10, t=50, b=10))
        
        dial_col1.plotly_chart(fig1, use_container_width=True)
        dial_col2.plotly_chart(fig2, use_container_width=True)
        
        remaining = st.columns([1,1,1])
        with remaining[1]:
            st.info(f"**Total Amount**: £{loan['total_amount']:.2f}")

        st.divider()

        # Record payment
        if is_borrower:
            st.subheader("Record a Payment")
            with st.form("payment_form", clear_on_submit=True):
                amount = st.number_input("Payment Amount", min_value=100.00, max_value=float(balance), step=1.0)
                note = st.text_input("Note (optional)")

                if st.form_submit_button("Submit Payment"):
                    # Insert the payment into Supabase
                    supabase.table("payments").insert({
                        "loan_id": loan['id'],
                        "amount": amount,
                        "note": note,
                        "paid_by": email
                    }).execute()

                    try:
                        resend.Emails.send({
                            "from": "info@zbuk.org",
                            "to": loan["lender_email"],
                            "subject": f"💸 New Loan Payment Received!",
                            "html": f"""
                                <h1>Payment Received</h1>
                                <p><strong>{email}</strong> has made a payment of <strong>£{amount:.2f}</strong> towards the loan.</p>
                                <p><em>Note:</em> {note if note else 'No additional notes provided.'}</p>
                            """
                        })

                    except Exception as e:
                        st.warning("Payment recorded, but failed to send email notification: " + str(e))

                    st.success("Payment recorded successfully!")
                    st.rerun()
        
        # Payment history
        st.subheader("Payment History")
        if payments:
            display_data = [{
                "Date": p['created_at'][:10],
                "Amount": f"£{p['amount']:.2f}",
                "Note": p['note'] or "N/A"
            } for p in payments]

            df = pd.DataFrame(display_data)
            st.table(df.style.hide(axis="index"))
        else:
            st.write("No payments recorded yet.")