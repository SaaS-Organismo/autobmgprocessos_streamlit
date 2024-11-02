import streamlit as st
import boto3
from uuid import uuid4
from decouple import config
import json

s3_client = boto3.client('s3', aws_access_key_id=config("AWS_ACCESS_KEY_ID"), aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"), region_name=config("AWS_REGION"))
lambda_client = boto3.client('lambda', aws_access_key_id=config("AWS_ACCESS_KEY_ID"), aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"), region_name=config("AWS_REGION"))

AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME")
AWS_LAMBDA_NAME = config("AWS_LAMBDA_NAME")


def upload_to_s3(file, object_key):
    try:
        s3_client.upload_fileobj(file, AWS_S3_BUCKET_NAME, object_key)
        return True
    except Exception as e:
        return False
    

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
    st.markdown("Baixe a planilha de exemplo abaixo e preencha com seus dados. Preencha seu email, suas credenciais de acesso do sistema BMG, anexe o arquivo e clique em 'Enviar'.")
    st.download_button(
            "Baixar Planilha",
            data=open("./Template AutoBMG.xlsx", "rb").read(), mime="application/octet-stream", file_name="Template AutoBMG.xlsx"
        )
    with st.form(key='registration_form'):
        email = st.text_input("Email", placeholder="Digite o seu email")
        login = st.text_input("Login", placeholder="Digite o seu login do sistema do BMG")
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha do sistema do BMG")
        #st.markdown(f'Baixe e preencha a planilha de <a href="https://docs.google.com/spreadsheets/d/1pWRFz9UeFveDPXpiU2T_2zwFYQqOIbUPfBP9JBlBZgg/edit?usp=sharing" target="_blank">exemplo</a> com seus dados. Anexe o arquivo no local abaixo.',  unsafe_allow_html=True)
        excel_file = st.file_uploader("Planilha", type=["xls", "xlsx"])
        submit_button = st.form_submit_button(label='Enviar')

        if submit_button:
            if login and excel_file is not None:
                object_key = f"uploads/{uuid4()}.xlsx"
                if upload_to_s3(excel_file, object_key):
                    event_payload = {
                        "email": email,
                        "login": login,
                        "password": password,
                        "file_key": object_key
                    }
                    invoke_lambda_async(event_payload)
                    st.success("Formulário enviado com sucesso! Aguarde o retorno dos arquivos no email fornecido.")
                else:
                    st.error("Erro ao enviar o formulário. Tente novamente!")
            else:
                st.warning("")

