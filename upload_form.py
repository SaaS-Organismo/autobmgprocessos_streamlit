import streamlit as st
import boto3
from uuid import uuid4
from decouple import config
import json

s3_client = boto3.client('s3', aws_access_key_id=config("AWS_ACCESS_KEY_ID"), aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"), region_name=config("AWS_REGION"))
lambda_client = boto3.client('lambda', aws_access_key_id=config("AWS_ACCESS_KEY_ID"), aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"), region_name=config("AWS_REGION"))

AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME")
AWS_LAMBDA_NAME = config("AWS_LAMBDA_NAME")


def invoke_lambda_async(event_payload):    

    try:
        response = lambda_client.invoke(
            FunctionName=AWS_LAMBDA_NAME,
            InvocationType='Event', 
            Payload=json.dumps(event_payload)
        )
        print("Lambda invoked successfully:", response)
        return response
    except Exception as e:
        print(f"Error invoking Lambda function: {e}")
        return None


def run():
    st.title("AutoBMG Processos")
    st.markdown("Preencha seu email, suas credenciais de acesso do sistema do BMG, digite o código do processo e clique em 'Enviar'.")
    with st.form(key='registration_form'):
        email = st.text_input("Email", placeholder="Digite o seu email")
        login = st.text_input("Login", placeholder="Digite o seu login do sistema do BMG")
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha do sistema do BMG")
        process_code = st.text_input("Código do processo", placeholder="Digite o código do processo")
        submit_button = st.form_submit_button(label='Enviar')

        if submit_button:
            if login and process_code is not None:
                event_payload = {
                    "email": email,
                    "login": login,
                    "password": password,
                    "process_code": process_code
                }

                response = invoke_lambda_async(event_payload)
                if response is not None:
                    st.success("Formulário enviado com sucesso! Aguarde o retorno dos arquivos no email fornecido.")
                else:
                    st.warning("Houve um erro ao submeter os dados. Tente novamente.")
            else:
                st.warning("Não foram informados os parâmetros obrigatórios para o download dos arquivos!")
