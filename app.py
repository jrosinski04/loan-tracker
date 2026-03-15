import streamlit as st
from supabase import create_client
import resend
import plotly.graph_objects as go

# Configuraton

st.set_page_config(page_title="Loan Tracker", page_icon=":money_with_wings:", layout="wide")

# Reduce Top Padding
st.markdown("""
    <style>
           .block-container {
                padding-top: 50px;
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
    col1, image, col2 = st.columns([4,2,1])
    col1.title("Car Finance Dashboard")
    with image:
        st.image("seatibiza.png", width=200)
    if col2.button("Log Out"):
        supabase.auth.sign_out()
        del st.session_state.user
        del st.session_state.session
        st.rerun()
    st.write(f"Logged in as: **{email}**")
    st.divider()

    # Fetching loan data
    loan_response = supabase.table("loans").select("*").execute()

    if not loan_response.data:
        st.write("No loans found.")
    else:
        loan = loan_response.data[0]
        is_borrower = (email == loan["borrower_email"])

        # Fetching payment details
        pay_response = supabase.table("payments").select("*").eq("loan_id", loan["id"]).execute()
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
                'bar': {'color': "#2e7d32"}, # A nice dark green
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, float(loan['total_amount'])], 'color': "#e8f5e9"} # Light green background
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
                'bar': {'color': "#c62828"}, # A nice dark red
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, float(loan['total_amount'])], 'color': "#ffebee"} # Light red background
                ]
            }
        ))

        # Render the charts in Streamlit
        fig1.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
        fig2.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
        
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
                            "from": "onboarding@resend.dev",
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
            st.dataframe(display_data, use_container_width=True, hide_index=True)
        else:
            st.write("No payments recorded yet.")