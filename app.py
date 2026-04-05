import time
import streamlit as st
from supabase import create_client
from streamlit_cookies_controller import CookieController
import resend
import plotly.graph_objects as go
import pandas as pd

cookies = CookieController()

TITLE = "Loan Tracker"
st.set_page_config(page_title=TITLE, page_icon="💸", layout="wide")

ICON_DATA = "💸" 
st.markdown("""
    <link rel="apple-touch-icon" href="{ICON_DATA}">
    <link rel="icon" href="{ICON_DATA}">
    <style>
           .block-container {
                padding-top: 10px;
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

def load_session():
    # Checking if user is already logged in (session exists)
    if "user" in st.session_state:
        return st.session_state.user
    
    # If not, checking browser cookies
    all_cookies = cookies.getAll()

    access_token = all_cookies.get("sb-access-token")
    refresh_token = all_cookies.get("sb-refresh-token")

    if not access_token or not refresh_token:
        time.sleep(0.2)
        return None

    if access_token and refresh_token:
        try:
            # Re-authenticate using saved tokens
            res = supabase.auth.set_session(access_token, refresh_token)
            st.session_state.user = res.user
            st.session_state.session = res.session
            return res.user
        except Exception as e:
            cookies.remove("sb-access-token")
            cookies.remove("sb-refresh-token")
    return None

user = load_session()
# Authentication

if user is None:
    all_cookies = cookies.getAll()
    if cookies.get("sb-access-token") or cookies.get("sb-refresh-token"):
        st.rerun()

if user is None or not user:
    st.title(TITLE)
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

                from datetime import datetime, timedelta
                expires = datetime.now() + timedelta(days=7)

                cookies.set("sb-access-token", res.session.access_token, expires=expires, secure=True, same_site="Lax")
                cookies.set("sb-refresh-token", res.session.refresh_token, expires=expires, secure=True, same_site="Lax")

                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error("Login failed: " + str(e))

else:
    email = st.session_state.user.email
    username = st.session_state.user.user_metadata.get("display_name") or email.split("@")[0]

    # Fetching loan data
    loan_response = supabase.table("loans").select("*").execute()

    if not loan_response.data:
        st.write("No loans found.")
    else:
        loan = loan_response.data[0]

    # Main dashboard
    col1, image, col2 = st.columns([7,2,1])

    IMAGE = None
    if loan_response.data:
        if loan.get('note') == "SEAT IBIZA":
            TITLE = "Car Finance Dashboard"
            ICON_DATA = "seatibiza.png"
            IMAGE = "seatibiza.png"

    with col1:
        st.title(TITLE)
        st.write(f"Logged in as: **{username}**")

    with image:
        if IMAGE:
            st.image(IMAGE, width=200)

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
                cookies.remove("sb-access-token")
                cookies.remove("sb-refresh-token")
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    st.divider()

    if loan_response.data:
        
        # Identifying th euser's role for the loan (borrower or lender)
        is_borrower = (email == loan["borrower_email"])
        is_lender = (email == loan["lender_email"])

        # Checking if user has permission to record payments
        can_record = False
        if is_borrower and loan.get('borrower_can_record_payment'):
            can_record = True
        elif is_lender and loan.get('lender_can_record_payment'):
            can_record = True

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
        if can_record:
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
            # Calculate remaining balance after each payment
            payments_asc = sorted(payments, key=lambda x: x['created_at'])
            cumulative_paid = 0
            remaining_dict = {}
            for p in payments_asc:
                cumulative_paid += p['amount']
                remaining_dict[p['id']] = float(loan['total_amount']) - cumulative_paid

            display_data = [{
                "Date": p['created_at'][:10],
                "Amount": f"£{p['amount']:.2f}",
                "Remaining": f"£{remaining_dict[p['id']]:.2f}",
                "Note": p['note'] or "N/A",
            } for p in payments]

            df = pd.DataFrame(display_data)
            st.table(df.style.hide(axis="index"))
        else:
            st.write("No payments recorded yet.")

st.markdown("---")
with st.expander("📄 Privacy Policy"):
    st.markdown("""
    <div style="font-size: 0.85rem; color: rgba(255,255,255,0.6);">
    <strong>Data Privacy at a Glance</strong><br>
    Last Updated: April 2026<br><br>

    <strong>1. Data We Collect</strong><br>
    We only store your Name, Email Address, and a securely hashed version of your password. We do not store, access, or see any of your personal banking details, credit scores, or external financial accounts.

    <strong>2. How We Use It</strong><br>
    Your information is used strictly to:<br>
        - Identify you within the Loan Tracker.<br>
        - Link your account to your specific loan agreements.<br>
        - Send automated payment confirmations and loan updates via our email partner (Resend).

    <strong>3. Security & Storage</strong><br>
    Your data is hosted on Supabase servers, utilizing industry-standard encryption and security protocols. We will never sell, share, or trade your personal information with third parties for marketing or any other purpose.

    <strong>4. Data Retention</strong><br>
    To ensure a clean record for your records, all personal information and associated loan data will be permanently deleted from our database 6 months after the loan is marked as "Completed."

    <strong>5. Your Rights</strong><br>
    You have the right to access your data or request immediate deletion at any time. For any privacy-related inquiries or to request manual data removal, please contact us at info@zbuk.org.

    <strong>6. Cookies</strong><br>
    We use essential session cookies to maintain your login status. By using the app, you agree to these functional cookies.
    </div>
    """, unsafe_allow_html=True)