import os
from dotenv import load_dotenv

from datetime import datetime

# Carrega .env se existir
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)

# Variáveis principais
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

# Outras configurações padrão
TEMP_DIR = os.environ.get("AUTOVIDEO_TEMP_DIR", "temp")
OUTPUTS_DIR = os.environ.get("AUTOVIDEO_OUTPUTS_DIR", "outputs")

# Data Atual para contexto da IA
CURRENT_DATE = datetime.now().strftime("%B %Y") # Ex: "July 2026"

if not PEXELS_API_KEY:
    print("⚠️ Variável de ambiente PEXELS_API_KEY não encontrada. Será usado vídeo de fallback para testes.")
