import streamlit as st
import boto3
from cryptography.fernet import Fernet

# Initialize the S3 client
s3_client = boto3.client('s3')

# Constants
S3_BUCKET_NAME = 'your-s3-bucket-name'  # Change this to your S3 bucket name
ENCRYPTION_KEY = b'SkQwPSjFjaivV+9rF3HqPur6OqN4hlUsp50m7Gb9NTk='   # Change this to your generated encryption key
fernet = Fernet(ENCRYPTION_KEY)

def encrypt_login(login):
    return fernet.encrypt(login.encode()).decode()

def upload_to_s3(file, object_key):
    try:
        s3_client.upload_fileobj(file, S3_BUCKET_NAME, object_key)
        return True
    except Exception as e:
        st.error(f"Error uploading file: {e}")
        return False

def run():
    st.title("User Registration Form")
    with st.form(key='registration_form'):
        login = st.text_input("Login", placeholder="Enter your login")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        excel_file = st.file_uploader("Upload Excel File", type=["xls", "xlsx"])

        submit_button = st.form_submit_button(label='Submit')

        if submit_button:
            if login and excel_file:
                object_key = f"uploads/{encrypt_login(login)}.xlsx"
                if upload_to_s3(excel_file, object_key):
                    st.success("File uploaded successfully!")
                else:
                    st.error("File upload failed.")
            else:
                st.warning("Please fill in all fields and upload an Excel file.")

