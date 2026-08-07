import asyncio
import ollama
import json
import re

# Trava global para impedir concorrência na VRAM do Ollama
ollama_lock = asyncio.Lock()

async def chat_safe(model, messages, options=None, format=None):
    """
    Executa uma chamada ao Ollama garantindo que apenas uma ocorra por vez (fila).
    Isso evita travamentos de VRAM e troca excessiva de modelos.
    """
    async with ollama_lock:
        try:
            # Opções de performance padrão
            default_options = {
                "temperature": 0.2,
                "num_thread": 6,   # Limita uso de CPU para não travar o sistema
                "num_gpu": 99      # Tenta forçar o máximo de camadas para a GPU
            }
            
            if options:
                default_options.update(options)
            
            res = await asyncio.to_thread(
                ollama.chat,
                model=model,
                messages=messages,
                options=default_options,
                format=format
            )
            return res
        except Exception as e:
            print(f"❌ Erro na chamada segura ao Ollama ({model}): {e}")
            return None

async def get_embedding_safe(model, prompt):
    """
    Gera embeddings usando a trava global para evitar colisões com o chat.
    """
    async with ollama_lock:
        try:
            res = await asyncio.to_thread(
                ollama.embeddings,
                model=model,
                prompt=prompt,
                options={
                    "num_thread": 4,
                    "num_gpu": 99
                }
            )
            return res.get("embedding")
        except Exception as e:
            print(f"❌ Erro na chamada de embedding segura ({model}): {e}")
            return None

def recursive_clean_strings(data):
    """
    Remove recursivamente aspas extras, colchetes de lista e caracteres de escape
    que a IA às vezes insere por erro dentro de valores de string.
    """
    if isinstance(data, dict):
        return {k: recursive_clean_strings(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursive_clean_strings(i) for i in data]
    elif isinstance(data, str):
        # Remove [" e "] ou [' e ']
        s = re.sub(r'^\[\s*["\']', '', data)
        s = re.sub(r'["\']\s*\]$', '', s)
        # Remove aspas duplas/simples no início e fim se sobraram
        s = s.strip().strip('"').strip("'")
        # Remove barras de escape desnecessárias
        s = s.replace('\\"', '"').replace("\\'", "'")
        return s
    return data

def extract_json_from_text(text):
    """
    Extrai, limpa e normaliza JSON de uma resposta de texto da IA.
    """
    if not text:
        return None
        
    # Remove blocos <think>
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    
    # Tenta encontrar o padrão { ... }
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        json_str = match.group(1)
        # Limpezas comuns de sintaxe inválida
        json_str = json_str.replace("```json", "").replace("```", "").strip()
        json_str = re.sub(r",\s*([\]\}])", r"\1", json_str) # Trailing commas
        
        try:
            dados = json.loads(json_str)
            # APLICA FAXINA NAS STRINGS
            return recursive_clean_strings(dados)
        except json.JSONDecodeError:
            return None
    return None
