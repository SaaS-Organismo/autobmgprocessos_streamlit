import json
import re
import smtplib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Tuple

import boto3
import pandas as pd
import streamlit as st
from botocore.config import Config
from decouple import config

from generate_pre_signed_url import zip_s3_bucket_contents

SMTP_SERVER = config("SMTP_SERVER")
SMTP_PORT = config("SMTP_PORT")
SMTP_USERNAME = config("SMTP_USERNAME")
SMTP_PASSWORD = config("SMTP_PASSWORD")
SENDER_EMAIL = config("SENDER_EMAIL")

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


def send_download_email(
    recipient_email: str, process_code: str, download_url: str
) -> bool:
    """Send email with pre-signed URL to the user."""
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = f"Download Link para Processo {process_code}"

        body = f"""
        Olá,

        O seu processo {process_code} está pronto para download.
        Por favor, utilize o link abaixo para baixar os documentos:

        {download_url}

        Este link expirará em 24 horas.

        Atenciosamente,
        AutoBMG Processos
        """

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {str(e)}")
        return False


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


def create_download_button(url: str, code: str):
    """Create a download button that opens in a new tab without page reload."""
    button_id = f"download_button_{code}"
    st.markdown(
        f"""
        <a href="{url}" target="_blank">
            <button id="{button_id}" style="
                width: 100%;
                border-radius: 5px;
                height: 3em;
                background-color: #FF4B4B;
                color: white;
                font-weight: bold;
                border: none;
                cursor: pointer;">
                📥 Download
            </button>
        </a>
        """,
        unsafe_allow_html=True,
    )


def process_single_code(
    email: str, login: str, password: str, process_code: str
) -> Tuple[str, dict]:
    """Process a single code with progress tracking."""
    event_payload = {
        "email": email,
        "login": login,
        "password": password,
        "process_code": process_code,
        "timestamp": datetime.now().isoformat(),
    }
    return process_code, invoke_lambda(event_payload)


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
        4. 📥 Baixe os arquivos processados
        
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
    download_container = st.container()

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

            progress_bar = progress_container.progress(0)
            progress_text = progress_container.empty()

            # Process codes in parallel with enhanced progress tracking
            successful_codes = []
            total_codes = len(valid_codes)

            with st.spinner("Processando..."):
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        executor.submit(
                            process_single_code, email, login, password, code
                        ): code
                        for code in valid_codes
                    }

                    for idx, future in enumerate(as_completed(futures)):
                        code = futures[future]
                        try:
                            _, response = future.result()
                            if response["statusCode"] == 200:
                                successful_codes.append(code)
                                st.toast(f"✅ Processo {code} concluído!", icon="✅")
                            else:
                                st.toast(f"❌ Erro: Processo {code}", icon="❌")
                        except Exception as e:
                            st.toast(f"❌ Erro: {code} - {str(e)}", icon="❌")

                        progress = (idx + 1) / total_codes
                        progress_bar.progress(
                            progress, f"Processando {idx + 1}/{total_codes}"
                        )
                        progress_text.markdown(
                            f"⏳ **Progresso:** {idx + 1}/{total_codes} processos"
                        )

            # Update statistics
            st.session_state.success_count += len(successful_codes)
            st.session_state.total_processed += total_codes

            if successful_codes:
                status_container.success(
                    f"✅ {len(successful_codes)}/{total_codes} processo(s) concluído(s)!"
                )

                # Send download links via email
                with st.spinner("📧 Enviando links por email..."):
                    for code in successful_codes:
                        download_url, error = zip_s3_bucket_contents(code)

                        if download_url:
                            if send_download_email(email, code, download_url):
                                st.toast(
                                    f"✅ Link de download enviado por email para {code}!",
                                    icon="✅",
                                )
                            else:
                                st.error(f"❌ Erro ao enviar email para {code}")
                        else:
                            st.error(f"❌ Erro ao gerar link para {code}")
                            if error:
                                st.caption(f"Erro: {error}")

                st.success(f"📧 Links de download foram enviados para {email}")

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
