import re
import ollama
import json
from config import CURRENT_DATE

from ollama_client import chat_safe, extract_json_from_text

MODELO_AUDITOR = "llama3.1:8b" # Upgrade para inteligência real

async def verificar_veracidade_roteiro(roteiro, fatos_json, modo_relaxado=False):
    """
    Compara o roteiro gerado com a base de fatos original para detectar alucinações.
    (FILA DE MODELO para evitar travamentos)
    """
    entidade = fatos_json.get("entidade", "Assunto")
    fatos_originais = json.dumps(fatos_json.get("fatos", []), ensure_ascii=False, indent=2)

    instrucao_rigor = "RIGOR TOTAL: Reprove se o roteiro inventar anos, nomes, locais ou motivos técnicos que não estão na lista."
    if modo_relaxado:
        instrucao_rigor = "MODO RELAXADO: Permita detalhes de conhecimento público inofensivos (ex: marcas de escova de dentes) desde que não contradigam a lista de fatos."

    prompt = f"""
Você é um AUDITOR DE VERACIDADE RIGOROSO para um canal de documentários técnicos.
Estamos em {CURRENT_DATE}.

### MISSÃO:
Garantir que o ROTEIRO não contenha NENHUMA informação técnica, histórica ou estatística que não esteja na LISTA DE FATOS.

### REGRAS:
1. ALUCINAÇÃO TÉCNICA: {instrucao_rigor}
2. FLAVOR NARRATIVO (PERMITIDO): Frases de efeito e conectivos dramáticos são aceitos.
3. RIGOR EM DADOS: Se os fatos não dizem uma data ou causa específica, o roteiro NÃO pode inventar.

LISTA DE FATOS (FONTE ÚNICA):
{fatos_originais}

ROTEIRO PARA AUDITORIA:
{roteiro}

### RESPOSTA OBRIGATÓRIA (JSON APENAS):
{{
  "aprovado": true/false,
  "alucinacoes": ["Lista de mentiras técnicas ou dados inventados"],
  "score_fidelidade": 0.0 a 1.0,
  "justificativa": "Explicação curta"
}}
"""

    try:
        print(f"🕵️ Auditando roteiro para '{entidade}' (Relaxado={modo_relaxado})...")
        
        # CHAMADA SEGURA (Fila do Ollama)
        res = await chat_safe(
            model=MODELO_AUDITOR,
            messages=[{"role": "user", "content": prompt}],
            format="json"
        )
        
        if not res:
            return False, {"justificativa": "Falha na resposta do auditor"}

        dados = extract_json_from_text(res.get("message", {}).get("content", ""))
        
        if not dados:
            return False, {"justificativa": "Erro de formato JSON no auditor"}

        aprovado = dados.get("aprovado", False)
        score = dados.get("score_fidelidade", 0)
        
        # --- CALIBRAÇÃO 3.3 ---
        if score >= 0.75:
            aprovado = True
        else:
            aprovado = False
            
        return aprovado, dados
            
    except Exception as e:
        print(f"⚠️ Erro fatal na auditoria: {e}")
        return False, {"justificativa": f"Falha técnica: {e}"}
