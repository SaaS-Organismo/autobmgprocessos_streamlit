import streamlit as st
import boto3
from botocore.config import Config
from uuid import uuid4
from decouple import config
import json
import time
from generate_pre_signed_url import zip_s3_bucket_contents
import webbrowser
import json

boto_config = Config(read_timeout=900, connect_timeout=900, retries={'max_attempts': 0}) 

lambda_client = boto3.client(
    "lambda",
    config=boto_config,
    aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
    region_name=config("AWS_REGION"),
)


AWS_LAMBDA_NAME = config("AWS_LAMBDA_NAME")


def invoke_lambda(event_payload):
    # time.sleep(3)
    # return {"statusCode": 200}
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


def run():
    st.session_state.running = False

    if not st.session_state.authenticated:
        st.warning("Você precisa estar autenticado para acessar esta página.")
        st.stop()

    st.title("AutoBMG Processos")
    st.markdown(
        "Preencha suas credenciais de acesso do sistema do BMG, digite o código do processo e clique em 'Enviar'."
    )
    email = st.text_input("Email", placeholder="Digite o seu email")
    login = st.text_input("Login", placeholder="Digite o seu login do sistema do BMG")
    password = st.text_input(
        "Senha", type="password", placeholder="Digite sua senha do sistema do BMG"
    )
    process_code = st.text_input(
        "Código do processo", placeholder="Digite o código do processo"
    )
    col1, col2 = st.columns([1, 8])
    info_temporary_message = st.empty()
    alert_temporary_message = st.empty()
    if "submit_button" in st.session_state and st.session_state.submit_button == True:
        st.session_state.running = True
        

    if "processed" in st.session_state and st.session_state.processed == True:
        info_temporary_message.info(
                "Estamos processando os documentos e isso pode demorar um pouco. Aguarde na página!"
            )
        download_url, error = zip_s3_bucket_contents(process_code)
        if not error:
            alert_temporary_message.success("Arquivos processados com sucesso! Clique no botão para baixá-los")
            col2.link_button(url=download_url, label="Baixar arquivos", disabled=st.session_state.running)
            st.session_state.running = False
        else:
            alert_temporary_message.error(f"Erro ao processar os documentos. Tente novamente!")
        info_temporary_message.empty()
        st.session_state.processed = False
        

    if col1.button(
        label="Enviar", disabled=st.session_state.running, key="submit_button"
    ):
        if email and login and password and process_code:
            # st.session_state.form_submitted = True
            event_payload = {
                "email": email,
                "login": login,
                "password": password,
                "process_code": process_code,
            }
            info_temporary_message.info(
                "Estamos processando os documentos e isso pode demorar um pouco. Aguarde na página!"
            )
            response_body = invoke_lambda(event_payload)
            if response_body["statusCode"] == 200:
                st.session_state.processed = True
            else:
                alert_temporary_message.warning("Houve um erro ao submeter os dados. Tente novamente.")
                info_temporary_message.empty()
                st.session_state.processed = False
            st.session_state.running = False
            st.rerun()
        else:
            alert_temporary_message.warning(
                "Não foram informados os parâmetros obrigatórios para o download dos arquivos!"
            )
