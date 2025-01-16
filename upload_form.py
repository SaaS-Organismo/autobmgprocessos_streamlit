import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
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


def invoke_lambda(event_payload):
    try:
        response = lambda_client.invoke(
            FunctionName=AWS_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(event_payload),
        )
        response_body = json.loads(response["Payload"].read())
        print("Lambda invoked successfully:", response_body)
        return response_body
    except Exception as e:
        print(f"Error invoking Lambda function: {e}")
        return None


def process_single_code(email, login, password, process_code):
    event_payload = {
        "email": email,
        "login": login,
        "password": password,
        "process_code": process_code,
    }
    return invoke_lambda(event_payload)


def run():
    st.session_state.running = False

    if not st.session_state.authenticated:
        st.warning("Você precisa estar autenticado para acessar esta página.")
        st.stop()

    st.title("AutoBMG Processos")
    st.markdown(
        "Preencha suas credenciais de acesso do sistema do BMG, digite os códigos dos processos e clique em 'Enviar'."
    )

    # Credentials inputs
    email = st.text_input("Email", placeholder="Digite o seu email")
    login = st.text_input("Login", placeholder="Digite o seu login do sistema do BMG")
    password = st.text_input(
        "Senha", type="password", placeholder="Digite sua senha do sistema do BMG"
    )

    # Create 5 process code inputs
    process_codes = []
    for i in range(5):
        code = st.text_input(
            f"Código do processo {i+1}",
            placeholder=f"Digite o código do processo {i+1}",
            key=f"process_code_{i}",
        )
        process_codes.append(code)

    col1, col2 = st.columns([1, 8])
    info_temporary_message = st.empty()
    alert_temporary_message = st.empty()

    if "submit_button" in st.session_state and st.session_state.submit_button == True:
        st.session_state.running = True

    if "processed_codes" in st.session_state and st.session_state.processed_codes:
        info_temporary_message.info(
            "Estamos processando os documentos e isso pode demorar um pouco. Aguarde na página!"
        )

        # Process each successful code
        download_buttons = []
        for process_code in st.session_state.processed_codes:
            download_url, error = zip_s3_bucket_contents(process_code)
            if not error:
                download_buttons.append((process_code, download_url))

        if download_buttons:
            alert_temporary_message.success(
                "Arquivos processados com sucesso! Clique nos botões para baixá-los"
            )
            for process_code, download_url in download_buttons:
                col2.link_button(
                    url=download_url,
                    label=f"Baixar arquivos - Processo {process_code}",
                    disabled=st.session_state.running,
                )
        else:
            alert_temporary_message.error(
                "Erro ao processar os documentos. Tente novamente!"
            )

        info_temporary_message.empty()
        st.session_state.processed_codes = []
        st.session_state.running = False

    if col1.button(
        label="Enviar", disabled=st.session_state.running, key="submit_button"
    ):
        if email and login and password and any(process_codes):
            # Filter out empty process codes
            valid_process_codes = [code for code in process_codes if code]

            if not valid_process_codes:
                alert_temporary_message.warning(
                    "Digite pelo menos um código de processo!"
                )
                return

            info_temporary_message.info(
                "Estamos processando os documentos e isso pode demorar um pouco. Aguarde na página!"
            )

            # Process all codes in parallel using ThreadPoolExecutor
            successful_codes = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_code = {
                    executor.submit(
                        process_single_code, email, login, password, code
                    ): code
                    for code in valid_process_codes
                }

                for future in as_completed(future_to_code):
                    code = future_to_code[future]
                    try:
                        response_body = future.result()
                        if response_body and response_body["statusCode"] == 200:
                            successful_codes.append(code)
                    except Exception as e:
                        print(f"Error processing code {code}: {e}")

            if successful_codes:
                st.session_state.processed_codes = successful_codes
                st.rerun()
            else:
                alert_temporary_message.warning(
                    "Houve um erro ao submeter os dados. Tente novamente."
                )
                info_temporary_message.empty()

            st.session_state.running = False

        else:
            alert_temporary_message.warning(
                "Preencha as credenciais e pelo menos um código de processo!"
            )
