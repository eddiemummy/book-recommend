# gemini.py
import os
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI


def create_model(temperature: float = 0.0):
    """
    Gemini modelini oluşturur.
    API key'i önce Streamlit secrets'tan, yoksa environment'tan alır.
    """

    api_key = None

    # Streamlit Cloud / local secrets
    if hasattr(st, "secrets"):
        api_key = st.secrets.get("GOOGLE_API_KEY")

    # fallback: env (local export)
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY bulunamadı. "
            ".streamlit/secrets.toml veya environment variable olarak ekleyin."
        )

    return ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=api_key,
        temperature=temperature,
    )
