import time
import streamlit as st
from supabase import create_client
from streamlit_cookies_controller import CookieController
import resend
import plotly.graph_objects as go
import pandas as pd

cookies = CookieController()

TITLE = "Loan Tracker"
IMAGE = None
st.set_page_config(page_title=TITLE, page_icon="💸", layout="wide")

ICON_DATA = "💸" 
st.markdown("""
    <link rel="apple-touch-icon" href="{ICON_DATA}">
    <link rel="icon" href="{ICON_DATA}">
    <style>
           .block-container {
                padding-top: 10px;
            }

            /* Dark Blurry Blue/Purple Gradient Background (0d1128 & 1a1025) */
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

# Store cookies securely in production, but allow a local override for HTTP development.
USE_SECURE_COOKIES = st.secrets.get("USE_SECURE_COOKIES", True)

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

def calculate_payment_totals(payments, total_amount):
    actual_paid_raw = 0.0
    virtual_balance = 0.0

    for payment in payments or []:
        amount = float(payment.get("amount", 0) or 0)

        if bool(payment.get("is_virtual")):
            virtual_balance += max(amount, 0)
        actual_paid_raw += amount

    balance = max(float(total_amount) - actual_paid_raw, 0.0)
    return {"actual_paid_raw": actual_paid_raw, "virtual_balance": virtual_balance, "balance": balance}

def calculate_virtual_balance(payments, withdrawals):
    virtual_payments = sum(
        max(float(payment.get("amount", 0) or 0), 0)
        for payment in payments or []
        if bool(payment.get("is_virtual"))
    )
    confirmed_withdrawals = sum(
        max(float(withdrawal.get("amount", 0) or 0), 0)
        for withdrawal in withdrawals or []
        if withdrawal.get("status") == "confirmed"
    )
    return max(virtual_payments - confirmed_withdrawals, 0.0)

user = load_session()
loan = None
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

                cookies.set("sb-access-token", res.session.access_token, expires=expires, secure=USE_SECURE_COOKIES, same_site="Lax")
                cookies.set("sb-refresh-token", res.session.refresh_token, expires=expires, secure=USE_SECURE_COOKIES, same_site="Lax")

                st.rerun()
            except Exception as e:
                st.error("Login failed: " + str(e))

else:
    email = st.session_state.user.email
    username = st.session_state.user.user_metadata.get("display_name") or email.split("@")[0]

    # Fetching loans AND the lender's display name from view
    # Joining the lender_names view using the lender_id
    loan_query = supabase.table("loans").select("""
        *,
        lender:profiles!lender_id(display_name),
        borrower:profiles!borrower_id(display_name)
    """).execute() 

    loans = loan_query.data

    if not loans:
        st.write("No loans found for your account.")
        st.stop()

    loan_options = []

    for l in loans:
        lender_name = l.get('lender', {}).get('display_name')
        lender_display = lender_name if lender_name else l['lender_email']
        label = f"{l['note']} - £{l['total_amount']} (Lender: {lender_display})"
        loan_options.append({"label": label, "data": l})

    if len(loans) > 1:
        selected_label = st.selectbox("Choose a loan to view", options=[o["label"] for o in loan_options])
        loan = next(o["data"] for o in loan_options if o["label"] == selected_label)
    else:
        loan = loans[0]

    # Main dashboard
    col1, image, virtual_account_header, settings = st.columns([6,2,2,1])

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

    virtual_account_header_slot = virtual_account_header.empty()

    with settings:
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
            
            if st.button("Logout", use_container_width=True):
                supabase.auth.sign_out()
                cookies.remove("sb-access-token")
                cookies.remove("sb-refresh-token")
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    st.divider()

    if loan:
        
        # Identifying the user's role for the loan (borrower or lender)
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
        withdrawal_response = supabase.table("withdrawals").select("*").eq("loan_id", loan["id"]).order("created_at", desc=True).execute()
        withdrawals = withdrawal_response.data

        # Calculating totals
        totals = calculate_payment_totals(payments, loan["total_amount"])
        total_paid_raw = totals["actual_paid_raw"]
        total_paid = max(total_paid_raw, 0)
        balance = totals["balance"]
        virtual_balance = calculate_virtual_balance(payments, withdrawals)

        if loan.get("virtual_account"):
            with virtual_account_header_slot.container():
                with st.popover(f"💷 £{virtual_balance:.2f}", use_container_width=True):
                    st.subheader("Virtual Account")
                    st.metric("Available balance", f"£{virtual_balance:.2f}")
                    st.caption("Withdrawal history can be seen at the bottom of the page.")

                    if is_lender:
                        if virtual_balance > 0:
                            with st.form("withdrawal_request_form", clear_on_submit=True):
                                withdrawal_amount = st.number_input(
                                    "Amount to request",
                                    min_value=0.01,
                                    max_value=float(virtual_balance),
                                    step=0.01,
                                )
                                withdrawal_note = st.text_input("Note (optional)")
                                request_withdrawal = st.form_submit_button("Request withdrawal", use_container_width=True)

                            if request_withdrawal:
                                supabase.table("withdrawals").insert({
                                    "loan_id": loan["id"],
                                    "amount": withdrawal_amount,
                                    "status": "pending",
                                    "requested_by": email,
                                    "note": withdrawal_note,
                                }).execute()
                                try:
                                    resend.Emails.send({
                                        "from": "info@zbuk.org",
                                        "to": loan["borrower_email"],
                                        "subject": "⚠️ Withdrawal requested from virtual account 💷",
                                        "html": f"<p>{username} requested a virtual-account withdrawal of <strong>£{withdrawal_amount:.2f}</strong>. You have 14 days to issue the withdrawal.</p>",
                                    })
                                except Exception as e:
                                    st.warning("Withdrawal requested, but failed to send email notification: " + str(e))
                                st.success("Withdrawal requested successfully!")
                                st.rerun()
                        else:
                            st.caption("No virtual balance available for withdrawal.")

                    if is_borrower:
                        pending_withdrawals = [w for w in withdrawals if w.get("status") == "pending"]
                        if pending_withdrawals:
                            with st.form("record_withdrawal_form", clear_on_submit=True):
                                selected_withdrawal = st.selectbox(
                                    "Pending withdrawal",
                                    pending_withdrawals,
                                    format_func=lambda withdrawal: f"£{float(withdrawal['amount']):.2f} requested by {withdrawal['requested_by']}",
                                )
                                confirm_withdrawal = st.form_submit_button("Record withdrawal", use_container_width=True)

                            if confirm_withdrawal:
                                selected_amount = float(selected_withdrawal["amount"])
                                if selected_amount > virtual_balance:
                                    st.error("This withdrawal is greater than the available virtual balance.")
                                else:
                                    update_response = supabase.table("withdrawals").update({
                                        "status": "confirmed",
                                        "confirmed_by": email,
                                    }).eq("id", selected_withdrawal["id"]).eq("status", "pending").execute()
                                    if not update_response.data:
                                        st.error("This withdrawal has already been recorded.")
                                    else:
                                        try:
                                            resend.Emails.send({
                                                "from": "info@zbuk.org",
                                                "to": loan["lender_email"],
                                                "subject": "💷 Virtual-account withdrawal recorded ✅",
                                                "html": f"<p>{username} recorded a virtual-account withdrawal of <strong>£{selected_amount:.2f}</strong>.</p>",
                                            })
                                        except Exception as e:
                                            st.warning("Withdrawal recorded, but failed to send email notification: " + str(e))
                                        st.success("Withdrawal recorded successfully!")
                                        st.rerun()

        # Graphical Visual Summary (Dials)
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
        remaining_max = max(float(loan['total_amount']), balance, 0)
        fig2 = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = balance,
            title = {'text': "Remaining Balance (£)", 'font': {'size': 24}},
            number = {'prefix': "£", 'valueformat': ",.2f"},
            gauge = {
                'axis': {'range': [0, remaining_max]},
                'bar': {'color': "rgba(244, 67, 54, 0.6)"}, # A nice dark red
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 1,
                'bordercolor': "rgba(255, 255, 255, 0.2)",
                'steps': [
                    {'range': [0, remaining_max], 'color': "rgba(255,255,255,0.05)"} # Light red background
                ]
            }
        ))

        # Rendering the charts in Streamlit
        fig1.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, margin=dict(l=10, r=10, t=50, b=10))
        fig2.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, margin=dict(l=10, r=10, t=50, b=10))
        
        dial_col1.plotly_chart(fig1, use_container_width=True)
        dial_col2.plotly_chart(fig2, use_container_width=True)
        
        remaining = st.columns([1,1,1])
        with remaining[1]:
            st.info(f"**Total Amount**: £{loan['total_amount']:.2f}")

        st.divider()

        # Recording payment
        if can_record:
            st.subheader("Record a Payment")

            with st.form("payment_form", clear_on_submit=True):
                if is_lender:
                    payment_type = st.selectbox("Payment Type", ["Record payment from borrower", "Lend additional amount"])
                    amount_label = "Amount"
                    min_val = 20.00
                    max_val = None
                else:
                    amount_label = "Payment Amount"
                    min_val = 20.00
                    max_val = float(balance)
                
                amount = st.number_input(amount_label, min_value=min_val, max_value=max_val, step=1.0)
                note = st.text_input("Note (optional)")

                should_offer_virtual_destination = loan.get("virtual_account") and (is_borrower or (is_lender and payment_type == "Record payment from borrower"))
                if should_offer_virtual_destination:
                    payment_destination = st.selectbox(
                        "Payment Destination",
                        ["Bank account", "Virtual Account"]
                    )
                    is_virtual_payment = payment_destination == "Virtual Account"
                else:
                    is_virtual_payment = False

                if st.form_submit_button("Submit Payment"):
                    if is_lender:
                        if payment_type == "Record payment from borrower":
                            amt = amount  # positive
                            email_to = loan["borrower_email"]
                            subject = f"💸 Payment Recorded by Lender"
                            html = f"""
                                <h1>Payment Recorded</h1>
                                <p>A payment of <strong>£{amount:.2f}</strong> has been recorded towards the loan.</p>
                                <p><em>Note:</em> {note if note else 'No additional notes provided.'}</p>
                            """
                        else:
                            amt = -amount  # negative
                            email_to = loan["borrower_email"]
                            subject = f"💸 New Loan Payment Recorded by Lender"
                            html = f"""
                                <h1>Payment Recorded</h1>
                                <p><strong>{username}</strong> has lent an additional <strong>£{amount:.2f}</strong>.</p>
                                <p><em>Note:</em> {note if note else 'No additional notes provided.'}</p>
                            """
                    else:
                        amt = amount  # positive
                        email_to = loan["lender_email"]
                        subject = f"💸 New Loan Payment Received!"
                        html = f"""
                            <h1>Payment Received</h1>
                            <p><strong>{username}</strong> has made a payment of <strong>£{amount:.2f}</strong> towards the loan.</p>
                            <p>The payment has been sent to your {'virtual account' if is_virtual_payment else 'bank account'}.</p>
                            <p><em>Note:</em> {note if note else 'No additional notes provided.'}</p>
                        """

                    # Insert the payment into Supabase
                    supabase.table("payments").insert({
                        "loan_id": loan['id'],
                        "amount": amt,
                        "note": note,
                        "paid_by": email,
                        "is_virtual": is_virtual_payment
                    }).execute()

                    # Send email notification
                    try:
                        resend.Emails.send({
                            "from": "info@zbuk.org",
                            "to": email_to,
                            "subject": subject,
                            "html": html
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
                "Destination": "Virtual Account" if p['is_virtual'] else "Bank Account",
                "Remaining": f"£{remaining_dict[p['id']]:.2f}",
                "Note": p['note'] or "N/A",
            } for p in payments]

            df = pd.DataFrame(display_data)
            st.table(df.style.hide(axis="index"))
        else:
            st.write("No payments recorded yet.")

        if loan.get("virtual_account") and withdrawals:
            st.subheader("Virtual Account Withdrawal History")
            withdrawal_data = [{
                "Date": withdrawal["created_at"][:10],
                "Amount": f"£{float(withdrawal['amount']):.2f}",
                "Status": withdrawal["status"].capitalize(),
                "Requested By": withdrawal["requested_by"],
                "Confirmed By": withdrawal.get("confirmed_by") or "Pending",
                "Note": withdrawal.get("note") or "N/A",
            } for withdrawal in withdrawals]
            st.table(pd.DataFrame(withdrawal_data).style.hide(axis="index"))

st.markdown("---")
if loan and loan.get("virtual_account"):
    with st.expander("💷 Virtual account explained"):
        st.markdown("""
        ### What is the virtual account?

        The virtual account lets a borrower set money aside for the lender without transferring it to the lender's bank account immediately. A borrower can choose **Virtual Account** as the payment destination when recording a payment.

        Virtual-account payments still count towards the loan's total paid and reduce the remaining loan balance. The money is recorded as belonging to the lender, but remains in the virtual account until it is withdrawn.

        ### How withdrawals work

        The lender can see the current virtual-account balance and request a withdrawal at any time, up to the available balance. When a withdrawal is requested, the borrower is notified and is obligated to pay the requested amount to the lender within **14 days**.

        Once the borrower records the withdrawal, it is marked as confirmed and removed from the available virtual-account balance. The withdrawal does not change the loan's total paid or remaining loan balance because the original virtual payment has already been counted towards the loan.

        When requesting a withdrawal, the lender should use the notes field to state how they would like to be paid. Please write **CASH** or **TRANSFER** in the notes so the borrower knows the preferred payout method.

        The virtual account is a record of money set aside for the lender. It does not hold or transfer funds itself, and this app does not access either party's bank account.
        """)

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

st.markdown("""
            <div style="text-align: right; font-size: 10px;">App version 1.1.0</div>
            """, unsafe_allow_html=True)
