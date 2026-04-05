import datetime
from supabase import create_client
import resend
import os

# Setting up clients
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)
resend.api_key = os.environ.get("RESEND_API_KEY")

def send_monthly_reminders():

    today = datetime.date.today()

    # Reminder for payments due tomorrow
    reminder_target_day = (today + datetime.timedelta(days=1)).day

    loans = supabase.table("loans").select("*").eq("payment_day", reminder_target_day).execute().data

    for loan in loans:
        try:
            # Getting borrower's name
            borrower_id = loan.get("borrower_id")
            user_data = supabase.auth.admin.get_user_by_id(borrower_id).data
            metadata = user_data.user.user_metadata if user_data.user else {}
            display_name = metadata.get("display_name") or loan['borrower_email'].split("@")[0]

            resend.Emails.send({
                "from":"info@zbuk.org",
                "to":[loan["'borrower_email'"]],
                "subject":"📅 Upcoming Loan Payment Reminder",
                "html":f"""
                <h2>Hi {display_name},</h2>
                <p>This is a friendly reminder that your next loan payment is due on <strong>tomorrow</strong>.</p>
                <p>You can view your remaining balance and log your payment at <a href="https://loan-tracker.streamlit.app">https://loan-tracker.streamlit.app</a>.</p>
                """
            })
            print(f"Reminder sent to {loan['borrower_email']}")
        except Exception as e:
            print(f"Failed to send reminder to {loan['borrower_email']}: {str(e)}")

    # Reminder for payments due today
    reminder_target_day = today.day
    loans = supabase.table("loans").select("*").eq("payment_day", reminder_target_day).execute().data

    for loan in loans:
        try:
            # Getting borrower's name
            borrower_id = loan.get("borrower_id")
            user_data = supabase.auth.admin.get_user_by_id(borrower_id).data
            metadata = user_data.user.user_metadata if user_data.user else {}
            display_name = metadata.get("display_name") or loan['borrower_email'].split("@")[0]

            resend.Emails.send({
                "from":"info@zbuk.org",
                "to":[loan["'borrower_email'"]],
                "subject":"📅 Upcoming Loan Payment Reminder",
                "html":f"""
                <h2>Hi {display_name},</h2>
                <p>This is a friendly reminder that your next loan payment </strong> is due today.</p>
                <p>You can view your remaining balance and log your payment at <a href="https://loan-tracker.streamlit.app">https://loan-tracker.streamlit.app</a>.</p>
                <br>
                <p>If you have already made this payment, please disregard this message.</p>
                <br>
                """
            })
            print(f"Reminder sent to {loan['borrower_email']}")
        except Exception as e:
            print(f"Failed to send reminder to {loan['borrower_email']}: {str(e)}")

if __name__ == "__main__":
    send_monthly_reminders()