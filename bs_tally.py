
import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from xml.dom import minidom
from io import BytesIO

#========================
#LOGIN CODE
#========================

import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

name, auth_status, username = authenticator.login("Login", "main")

if auth_status is False:
    st.error("Invalid username or password")
    st.stop()

if auth_status is None:
    st.warning("Please enter your credentials")
    st.stop()

authenticator.logout("Logout", "sidebar")
st.sidebar.success(f"Logged in as {name}")

# =========================
# CONFIGURATION (Backend)
# =========================
COMPANY_NAME = "ABC Pvt Ltd"

def format_date_for_tally(date_val):
    """
    Tally expects date in YYYYMMDD format
    Excel / string / datetime all handled here
    """
    return pd.to_datetime(date_val).strftime("%Y%m%d")


# =========================
# XML HELPERS
# =========================
def prettify_xml(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


# =========================
# VOUCHER TYPE LOGIC
# =========================
def determine_voucher_type(row):
    if row["Withdrawal"] > 0:
        return "Payment"
    if row["Deposit"] > 0:
        return "Receipt"
    return None


# =========================
# TALLY XML BUILDER
# =========================
def build_tally_xml(df, bank_ledger):
    envelope = ET.Element("ENVELOPE")

    header = ET.SubElement(envelope, "HEADER")
    ET.SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = ET.SubElement(envelope, "BODY")
    import_data = ET.SubElement(body, "IMPORTDATA")

    request_desc = ET.SubElement(import_data, "REQUESTDESC")
    ET.SubElement(request_desc, "REPORTNAME").text = "Vouchers"

    static_vars = ET.SubElement(request_desc, "STATICVARIABLES")
    ET.SubElement(static_vars, "SVCURRENTCOMPANY").text = COMPANY_NAME

    request_data = ET.SubElement(import_data, "REQUESTDATA")

    for _, row in df.iterrows():
        voucher_type = determine_voucher_type(row)
        if voucher_type is None:
            continue

        amount = row["Withdrawal"] if row["Withdrawal"] > 0 else row["Deposit"]

        tally_message = ET.SubElement(request_data, "TALLYMESSAGE")
        voucher = ET.SubElement(
            tally_message,
            "VOUCHER",
            VCHTYPE=voucher_type,
            ACTION="Create"
        )

        ET.SubElement(voucher, "DATE").text = format_date_for_tally(row["Date"])
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = voucher_type
        ET.SubElement(voucher, "NARRATION").text = row["Narration"]

        # -------------------------
        # Counter Ledger Entry
        # -------------------------
        counter_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(counter_entry, "LEDGERNAME").text = row["Ledger"]

        if voucher_type == "Payment":
            ET.SubElement(counter_entry, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(counter_entry, "AMOUNT").text = f"-{amount}"
        else:
            ET.SubElement(counter_entry, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(counter_entry, "AMOUNT").text = f"{amount}"

        # -------------------------
        # Bank Ledger Entry
        # -------------------------
        bank_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(bank_entry, "LEDGERNAME").text = bank_ledger

        if voucher_type == "Payment":
            ET.SubElement(bank_entry, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(bank_entry, "AMOUNT").text = f"{amount}"
        else:
            ET.SubElement(bank_entry, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(bank_entry, "AMOUNT").text = f"-{amount}"

    return prettify_xml(envelope)


# =========================
# TEMPLATE GENERATOR
# =========================
def generate_template():
    template_df = pd.DataFrame(
        columns=["Date", "Narration", "Withdrawal", "Deposit", "Ledger"]
    )
    buffer = BytesIO()
    template_df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Bank to Tally XML", layout="centered")
st.title("Bank Statement → Tally Voucher XML Converter")

# --- Template Download ---
st.subheader("1. Download Excel Template")
st.download_button(
    label="Download Bank Statement Template",
    data=generate_template(),
    file_name="bank_statement_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --- Bank Ledger Input ---
st.subheader("2. Bank Ledger Configuration")
bank_ledger_name = st.text_input(
    "Enter Bank Ledger Name (Must match Tally exactly)",
    value="HDFC Bank"
)

# --- File Upload ---
st.subheader("3. Upload Bank Statement Excel")
uploaded_file = st.file_uploader(
    "Upload Excel File",
    type=["xlsx"]
)

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    required_cols = {"Date", "Narration", "Withdrawal", "Deposit", "Ledger"}
    if not required_cols.issubset(df.columns):
        st.error("Excel file does not match required template structure.")
        st.stop()

    st.success("File validated successfully")
    st.dataframe(df.head())

    # --- XML Generation ---
    st.subheader("4. Generate Tally XML")
    if st.button("Generate Tally XML"):
        xml_data = build_tally_xml(df, bank_ledger_name)

        st.download_button(
            label="Download Tally XML",
            data=xml_data,
            file_name="bank_vouchers.xml",
            mime="application/xml"
        )
