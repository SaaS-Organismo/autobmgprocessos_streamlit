import json
import re
import smtplib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Tuple

import boto3
import pandas as pd
import streamlit as st
from botocore.config import Config
from decouple import config

from generate_pre_signed_url import zip_s3_bucket_contents

# Page config for a cleaner look
st.set_page_config(
    page_title="AutoBMG Processos",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
    <style>
    .stButton button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
    }
    .stTextInput > div > div > input {
        border-radius: 5px;
    }
    .stProgress > div > div > div {
        background-color: #FF4B4B;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# AWS Configuration
boto_config = Config(read_timeout=900, connect_timeout=900, retries={"max_attempts": 0})
lambda_client = boto3.client(
    "lambda",
    config=boto_config,
    aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
    region_name=config("AWS_REGION"),
)
AWS_LAMBDA_NAME = config("AWS_LAMBDA_NAME")

# Email configuration
SMTP_SERVER = config("SMTP_SERVER")
SMTP_PORT = config("SMTP_PORT")
SMTP_USERNAME = config("SMTP_USERNAME")
SMTP_PASSWORD = config("SMTP_PASSWORD")
SENDER_EMAIL = config("SENDER_EMAIL")


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))


def validate_process_code(code: str) -> bool:
    """Validate process code format for CIV format."""
    if not code:  # Empty code is considered valid
        return True
    # Check for format CIV followed by digits
    pattern = r"^CIV\d+$"
    return bool(re.match(pattern, code))


def invoke_lambda(event_payload: dict) -> dict:
    """Invoke Lambda function with enhanced error handling."""
    try:
        response = lambda_client.invoke(
            FunctionName=AWS_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(event_payload),
        )

        if "FunctionError" in response:
            error_details = json.loads(response["Payload"].read())
            st.error(f"Erro Lambda: {error_details}")
            raise Exception(f"Lambda execution failed: {error_details}")

        response_body = json.loads(response["Payload"].read())
        return response_body
    except Exception as e:
        st.error(f"Erro ao invocar Lambda: {str(e)}")
        return {"statusCode": 500, "body": str(e)}


def send_download_email(
    recipient_email: str, process_code: str, download_url: str
) -> bool:
    """Send email with pre-signed URL to the user."""
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = f"Download Link para Processo {process_code}"

        # Use HTML body with hyperlink
        body = f"""
        <html>
        <body>
            <p>Olá,</p>
            <p>O seu processo <strong>{process_code}</strong> está pronto para download.<br>
            Por favor, <a href="{download_url}" target="_blank">clique aqui</a> para baixar os documentos.</p>
            <p>Este link expirará em 24 horas.</p>
            <p>Atenciosamente,<br>
            AutoBMG Processos</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        print(
            f"Erro ao enviar email: {str(e)}"
        )  # Replace with proper logging in production
        return False


def process_and_send_email(
    email: str, login: str, password: str, process_code: str
) -> Dict[str, any]:
    """Process a single code and send email immediately upon completion."""
    try:
        # Invoke Lambda
        event_payload = {
            "email": email,
            "login": login,
            "password": password,
            "process_code": process_code,
            "timestamp": datetime.now().isoformat(),
        }

        response = invoke_lambda(event_payload)

        if response["statusCode"] == 200:
            # Generate download URL
            download_url, error = zip_s3_bucket_contents(process_code)

            if download_url:
                # Send email immediately
                email_sent = send_download_email(email, process_code, download_url)

                return {
                    "code": process_code,
                    "success": True,
                    "email_sent": email_sent,
                    "error": None,
                }
            else:
                return {
                    "code": process_code,
                    "success": True,
                    "email_sent": False,
                    "error": f"Erro ao gerar URL: {error}",
                }
        else:
            return {
                "code": process_code,
                "success": False,
                "email_sent": False,
                "error": f"Erro no processamento: {response.get('body', 'Unknown error')}",
            }

    except Exception as e:
        return {
            "code": process_code,
            "success": False,
            "email_sent": False,
            "error": str(e),
        }


def initialize_session_state():
    """Initialize enhanced session state variables."""
    if "form_data" not in st.session_state:
        st.session_state.form_data = {
            "email": "",
            "login": "",
            "process_codes": [""] * 5,
            "theme": "light",
        }
    if "processing_history" not in st.session_state:
        st.session_state.processing_history = []
    if "success_count" not in st.session_state:
        st.session_state.success_count = 0
    if "total_processed" not in st.session_state:
        st.session_state.total_processed = 0
    if "processing_results" not in st.session_state:
        st.session_state.processing_results = []


def run():
    initialize_session_state()

    if not st.session_state.authenticated:
        st.warning("⚠️ Você precisa estar autenticado para acessar esta página.")
        st.stop()

    # Sidebar with enhanced credentials section
    with st.sidebar:
        st.header("🔐 Credenciais")

        # Create columns for a more compact layout
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Processos com Sucesso", st.session_state.success_count)
        with col2:
            st.metric("Total Processado", st.session_state.total_processed)

        with st.form("credentials_form"):
            email = st.text_input(
                "📧 Email",
                value=st.session_state.form_data["email"],
                placeholder="seu.email@exemplo.com",
            )

            login = st.text_input(
                "👤 Login",
                value=st.session_state.form_data["login"],
                placeholder="Seu login BMG",
            )

            password = st.text_input(
                "🔑 Senha", type="password", placeholder="Sua senha BMG"
            )

            save_credentials = st.form_submit_button("💾 Salvar Credenciais")

            if save_credentials:
                if validate_email(email) and login and password:
                    st.session_state.form_data.update({"email": email, "login": login})
                    st.success("✅ Credenciais salvas com sucesso!")
                else:
                    st.error("❌ Por favor, verifique suas credenciais")

    # Main content area
    st.title("📑 AutoBMG Processos")

    # Help section with tabs
    tab1, tab2 = st.tabs(["ℹ️ Como Usar", "📋 Requisitos"])

    with tab1:
        st.markdown(
            """
        ### Passo a passo:
        1. 📝 Preencha suas credenciais na barra lateral
        2. 📎 Digite de 1 a 5 códigos de processo
        3. 🚀 Clique em 'Processar' para iniciar
        4. 📧 Aguarde o email com o link para download
        
        **Observação:** Você pode deixar campos vazios, mas precisa fornecer pelo menos um código válido.
        """
        )

    with tab2:
        st.markdown(
            """
        ### Formato do Código de Processo:
        - Deve começar com 'CIV' (maiúsculo)
        - Seguido por números
        - Campos podem ficar vazios
        - Exemplos válidos: 
          * CIV1234567
          * CIV12345
          * CIV123456789
          * (campo vazio)
        - Exemplos inválidos:
          * civ1234567 (CIV deve ser maiúsculo)
          * CIV123ABC (apenas números após CIV)
          * 1234CIV (deve começar com CIV)
        """
        )

    # Main form for process codes
    with st.form("process_form"):
        st.subheader("🔄 Processar Documentos")

        # Process code inputs with instant validation
        process_codes = []
        cols = st.columns(5)
        for i, col in enumerate(cols):
            with col:
                code = st.text_input(
                    f"Processo {i+1}",
                    value=st.session_state.form_data["process_codes"][i],
                    placeholder="CIVXXXXXX",
                    key=f"process_code_{i}",
                ).upper()  # Automatically convert to uppercase

                if code:  # Only show validation message if field is not empty
                    if not validate_process_code(code):
                        st.caption("❌ Formato inválido - Use CIV + números")
                    else:
                        st.caption("✅ Formato válido")
                process_codes.append(code)

        submit_button = st.form_submit_button("🚀 Processar")

    # Status containers
    status_container = st.container()
    progress_container = st.container()

    if submit_button:
        # Start timing the process
        start_time = datetime.now()

        # Validate inputs
        validation_errors = []

        # Check if credentials match the saved ones
        if (
            email != st.session_state.form_data["email"]
            or login != st.session_state.form_data["login"]
        ):
            validation_errors.append(
                "❌ Por favor, salve suas credenciais antes de processar"
            )

        if not validate_email(email):
            validation_errors.append("❌ Email inválido")
        if not login:
            validation_errors.append("❌ Login é obrigatório")
        if not password:
            validation_errors.append("❌ Senha é obrigatória")

        # Filter out empty codes and validate the non-empty ones
        non_empty_codes = [code for code in process_codes if code.strip()]
        valid_codes = [code for code in non_empty_codes if validate_process_code(code)]

        if not valid_codes:
            validation_errors.append(
                "❌ Forneça pelo menos um código de processo válido"
            )
        elif len(valid_codes) > 5:
            validation_errors.append(
                "❌ Você pode processar no máximo 5 códigos por vez"
            )

        if validation_errors:
            for error in validation_errors:
                st.error(error)
        else:
            with status_container:
                st.info("🔄 Iniciando processamento dos documentos...")

            progress_placeholder = st.empty()
            progress_text = st.empty()

            # Process codes in parallel
            successful_codes = []
            failed_codes = []
            total_codes = len(valid_codes)

            with st.spinner("Processando..."):
                # Create a list to store all futures
                futures = []

                with ThreadPoolExecutor(max_workers=5) as executor:
                    # Submit all tasks
                    for code in valid_codes:
                        future = executor.submit(
                            process_and_send_email, email, login, password, code
                        )
                        futures.append(future)

                    # Process results as they complete
                    for idx, future in enumerate(as_completed(futures), 1):
                        result = future.result()
                        code = result["code"]

                        # Update progress
                        progress = idx / total_codes
                        progress_placeholder.progress(progress)
                        progress_text.markdown(
                            f"⏳ **Progresso:** {idx}/{total_codes} processos"
                        )

                        if result["success"]:
                            successful_codes.append(code)
                            if result["email_sent"]:
                                st.toast(
                                    f"✅ Processo {code} concluído e email enviado!",
                                    icon="✅",
                                )
                            else:
                                st.toast(
                                    f"⚠️ Processo {code} concluído, mas erro ao enviar email: {result['error']}",
                                    icon="⚠️",
                                )
                        else:
                            failed_codes.append(code)
                            st.toast(
                                f"❌ Erro no processo {code}: {result['error']}",
                                icon="❌",
                            )

            # Update statistics
            st.session_state.success_count += len(successful_codes)
            st.session_state.total_processed += total_codes

            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds() / 60

            # Final status update
            if successful_codes:
                status_container.success(
                    f"✅ {len(successful_codes)}/{total_codes} processo(s) concluído(s)!"
                )
                if failed_codes:
                    status_container.warning(
                        f"⚠️ {len(failed_codes)} processo(s) falharam: {', '.join(failed_codes)}"
                    )
            else:
                status_container.error("❌ Nenhum processo foi concluído")

            # Update processing history
            st.session_state.processing_history.append(
                {
                    "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "successful": len(successful_codes),
                    "failed": len(failed_codes),
                    "total_time": f"{processing_time:.1f} min",
                }
            )

    # Enhanced processing history with median calculation
    if st.session_state.processing_history:
        with st.expander("📊 Histórico de Processamento"):
            history_df = pd.DataFrame(st.session_state.processing_history)

            # Convert total_time strings to numeric values for median calculation
            history_df["processing_minutes"] = (
                history_df["total_time"].str.extract("(\d+\.?\d*)").astype(float)
            )

            # Calculate median processing time
            median_time = history_df["processing_minutes"].median()

            # Display statistics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Tempo Médio de Processamento", f"{median_time:.1f} min")
            with col2:
                st.metric("Total de Lotes Processados", len(history_df))

            # Display history table
            st.dataframe(
                history_df.drop("processing_minutes", axis=1),
                column_config={
                    "timestamp": "Data/Hora",
                    "successful": "Sucesso",
                    "failed": "Falhas",
                    "total_time": "Tempo Total",
                },
                hide_index=True,
            )


def main():
    run()


if __name__ == "__main__":
    main()
