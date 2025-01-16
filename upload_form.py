import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import boto3
import pandas as pd
import streamlit as st
from botocore.config import Config
from decouple import config

from generate_pre_signed_url import zip_s3_bucket_contents

boto_config = Config(read_timeout=900, connect_timeout=900, retries={"max_attempts": 0})

lambda_client = boto3.client(
    "lambda",
    config=boto_config,
    aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
    region_name=config("AWS_REGION"),
)

AWS_LAMBDA_NAME = config("AWS_LAMBDA_NAME")


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))


def validate_process_code(code: str) -> bool:
    """Validate process code format - customize based on your requirements."""
    # Example: Requires at least 5 characters, alphanumeric
    return bool(code and len(code) >= 5 and code.isalnum())


def invoke_lambda(event_payload: dict) -> dict:
    """Invoke Lambda function with better error handling and timeout management."""
    try:
        response = lambda_client.invoke(
            FunctionName=AWS_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(event_payload),
        )

        # Check for Lambda execution errors
        if "FunctionError" in response:
            error_details = json.loads(response["Payload"].read())
            raise Exception(f"Lambda execution failed: {error_details}")

        response_body = json.loads(response["Payload"].read())
        print("Lambda invoked successfully:", response_body)
        return response_body
    except Exception as e:
        print(f"Error invoking Lambda function: {e}")
        return {"statusCode": 500, "body": str(e)}


def process_single_code(
    email: str, login: str, password: str, process_code: str
) -> Tuple[str, dict]:
    """Process a single code and return both code and response."""
    event_payload = {
        "email": email,
        "login": login,
        "password": password,
        "process_code": process_code,
    }
    return process_code, invoke_lambda(event_payload)


def initialize_session_state():
    """Initialize session state variables."""
    if "form_data" not in st.session_state:
        st.session_state.form_data = {
            "email": "",
            "login": "",
            "process_codes": [""] * 5,
        }
    if "processing_history" not in st.session_state:
        st.session_state.processing_history = []


def run():
    initialize_session_state()

    if not st.session_state.authenticated:
        st.warning("Você precisa estar autenticado para acessar esta página.")
        st.stop()

    st.title("AutoBMG Processos")

    # Add help information in an expandable section
    with st.expander("ℹ️ Como usar este formulário"):
        st.markdown(
            """
        1. Preencha suas credenciais de acesso do sistema BMG
        2. Digite até 5 códigos de processo para processamento em paralelo
        3. Clique em 'Enviar' para iniciar o processamento
        4. Acompanhe o progresso em tempo real
        5. Faça o download dos arquivos processados
        
        **Observações:**
        - Você pode processar de 1 a 5 processos simultaneamente
        - O tempo de processamento pode variar dependendo do tamanho dos arquivos
        - Os links de download expiram após 1 hora
        """
        )

    # Main form
    with st.form("process_form"):
        email = st.text_input(
            "Email",
            value=st.session_state.form_data["email"],
            placeholder="Digite o seu email",
            help="Email para receber notificações",
        )

        login = st.text_input(
            "Login",
            value=st.session_state.form_data["login"],
            placeholder="Digite o seu login do sistema do BMG",
        )

        password = st.text_input(
            "Senha", type="password", placeholder="Digite sua senha do sistema do BMG"
        )

        # Process code inputs with validation
        process_codes = []
        for i in range(5):
            code = st.text_input(
                f"Código do processo {i+1}",
                value=st.session_state.form_data["process_codes"][i],
                placeholder=f"Digite o código do processo {i+1}",
                key=f"process_code_{i}",
                help="Código deve ter pelo menos 5 caracteres alfanuméricos",
            )
            process_codes.append(code)

        submit_button = st.form_submit_button("Enviar")

    # Status containers
    status_container = st.container()
    progress_container = st.container()
    download_container = st.container()

    if submit_button:
        # Validate inputs
        validation_errors = []
        if not validate_email(email):
            validation_errors.append("Email inválido")
        if not login:
            validation_errors.append("Login é obrigatório")
        if not password:
            validation_errors.append("Senha é obrigatória")

        valid_codes = [
            code for code in process_codes if code and validate_process_code(code)
        ]
        if not valid_codes:
            validation_errors.append("Forneça pelo menos um código de processo válido")

        if validation_errors:
            for error in validation_errors:
                st.error(error)
        else:
            # Save form data for persistence
            st.session_state.form_data = {
                "email": email,
                "login": login,
                "process_codes": process_codes,
            }

            with status_container:
                st.info("🔄 Iniciando processamento dos documentos...")

            progress_bar = progress_container.progress(0)
            progress_text = progress_container.empty()

            # Process codes in parallel
            successful_codes = []
            total_codes = len(valid_codes)

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
                            st.toast(
                                f"✅ Processo {code} concluído com sucesso!", icon="✅"
                            )
                        else:
                            st.toast(f"❌ Erro ao processar processo {code}", icon="❌")
                    except Exception as e:
                        st.toast(
                            f"❌ Erro ao processar processo {code}: {str(e)}", icon="❌"
                        )

                    # Update progress
                    progress = (idx + 1) / total_codes
                    progress_bar.progress(progress)
                    progress_text.text(
                        f"Processados {idx + 1} de {total_codes} processo(s)"
                    )

            # Final status update
            progress_bar.empty()
            if successful_codes:
                status_container.success(
                    f"✅ {len(successful_codes)} processo(s) concluído(s) com sucesso!"
                )

                # Generate download links
                with download_container:
                    st.subheader("Downloads disponíveis")
                    for code in successful_codes:
                        download_url, error = zip_s3_bucket_contents(code)
                        if download_url:
                            st.link_button(
                                f"📥 Baixar arquivos - Processo {code}",
                                url=download_url,
                            )
                        else:
                            st.error(
                                f"Erro ao gerar link para processo {code}: {error}"
                            )

                # Add to processing history
                st.session_state.processing_history.append(
                    {
                        "timestamp": st.session_state.get("current_time", ""),
                        "successful": len(successful_codes),
                        "failed": len(valid_codes) - len(successful_codes),
                    }
                )
            else:
                status_container.error("❌ Nenhum processo foi concluído com sucesso")

    # Show processing history in an expandable section
    if st.session_state.processing_history:
        with st.expander("📊 Histórico de Processamento"):
            history_df = pd.DataFrame(st.session_state.processing_history)
            st.dataframe(history_df)


def main():
    run()


if __name__ == "__main__":
    main()
