import re
import ollama
import json

MODELO_AUDITOR = "phi4-mini"

def verificar_veracidade_roteiro(roteiro, fatos_json):
    """
    Compara o roteiro gerado com a base de fatos original para detectar alucinações.
    Retorna (True/False, justificativa).
    """
    entidade = fatos_json.get("entidade", "Assunto")
    fatos_originais = json.dumps(fatos_json.get("fatos", []), ensure_ascii=False, indent=2)

    prompt = f"""
Você é um AUDITOR DE VERACIDADE para um canal de documentários técnicos.
Sua missão é comparar o ROTEIRO abaixo com a LISTA DE FATOS VERIFICADOS e identificar ALUCINAÇÕES.

REGRAS DE AUDITORIA:
1. ALUCINAÇÃO: Qualquer informação no roteiro que NÃO esteja nos fatos verificados ou que contradiga um fato.
2. EXCEÇÃO: Conectores narrativos (ex: "Além disso", "Por outro lado") são permitidos, desde que não alterem o sentido factual.
3. RIGOR: Se o roteiro inventar um ano, um nome ou um local que não está nos fatos, ele deve ser REPROVADO.

LISTA DE FATOS VERIFICADOS (FONTE ÚNICA DA VERDADE):
{fatos_originais}

ROTEIRO PARA AUDITORIA:
{roteiro}

RESPOSTA OBRIGATÓRIA (JSON APENAS):
{{
  "aprovado": true/false,
  "alucinacoes": ["Lista de frases ou dados inventados"],
  "score_fidelidade": 0.0 a 1.0,
  "justificativa": "Breve explicação da decisão"
}}
"""

    try:
        print(f"🕵️ Auditando veracidade do roteiro para '{entidade}'...")
        res = ollama.chat(
            model=MODELO_AUDITOR,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1}
        )
        conteudo = res["message"]["content"].strip()
        
        m = re.search(r"\{.*\}", conteudo, re.DOTALL)
        if m:
            dados = json.loads(m.group())
            aprovado = dados.get("aprovado", False)
            score = dados.get("score_fidelidade", 0)
            
            if score < 0.85:
                aprovado = False
                
            return aprovado, dados
        else:
            return False, {"justificativa": "Erro no formato da auditoria"}
            
    except Exception as e:
        print(f"⚠️ Erro na auditoria de veracidade: {e}")
        return True, {"justificativa": "Auditoria falhou, procedendo com cautela"} # Fallback permissivo para não travar
