

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

def save_feedback_to_gsheet(email, suggestions):
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(creds)
    sheet = client.open("Bank2Tally_Feedback").sheet1

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        email,
        suggestions
    ])
