import streamlit as st
import boto3
from cryptography.fernet import Fernet
import pandas as pd

# Initialize the S3 client
s3_client = boto3.client('s3')

# Constants
S3_BUCKET_NAME = 'your-s3-bucket-name'  # Change this to your S3 bucket name
ENCRYPTION_KEY = b'SkQwPSjFjaivV+9rF3HqPur6OqN4hlUsp50m7Gb9NTk='   # Change this to your generated encryption key
fernet = Fernet(ENCRYPTION_KEY)

def encrypt_login(login):
    return fernet.encrypt(login.encode()).decode()

def list_files(login):
    encrypted_email = encrypt_login(login)
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=encrypted_email)
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        else:
            return []
    except Exception as e:
        st.error(f"Error retrieving files: {e}")
        return []

def run():
    st.title("List Files in S3")
    login = st.text_input("Email to List Files", placeholder="Enter your login")

    if st.button("List Files"):
        if login:
            files = [{"name": "test", "link": "test"} for i in range(10)] #list_files(login)
            if files:
                st.success("Files retrieved successfully!")
                # Pagination settings
                page_size = 5  # Number of files per page
                total_files = len(files)
                total_pages = (total_files // page_size) + (1 if total_files % page_size > 0 else 0)

                # Current page logic
                if 'current_page' not in st.session_state:
                    st.session_state.current_page = 1

                

                # Calculate file indices for the current page
                start_idx = (st.session_state.current_page - 1) * page_size
                end_idx = start_idx + page_size
                files_to_display = files[start_idx:end_idx]
                print(files_to_display)

                # Create a DataFrame to display the files with clickable links
                files_to_display = [
                    {**file,
                     "link": f"<a href=\"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{file.get('link')}\" target=\"_blank\">Link</a>"}
                    for file in files_to_display
                ]
                df = pd.DataFrame(files_to_display, columns=["name", "link"])

                # Use st.markdown to render HTML with links
                st.markdown(df.to_html(index=False, escape=False), unsafe_allow_html=True)  # Render the DataFrame as an HTML table

                # Page navigation
                col1, col2, col3 = st.columns([1, 1, 1])  # Three columns for pagination controls
                with col1:
                    if st.button("Previous", disabled=st.session_state.current_page == 1):
                        st.session_state.current_page -= 1
                with col2:
                    st.write(f"Page {st.session_state.current_page} of {total_pages}")
                with col3:
                    if st.button("Next", disabled=st.session_state.current_page == total_pages):
                        st.session_state.current_page += 1
            else:
                st.warning("No files found for this email.")
        else:
            st.warning("Please enter a valid email.")
