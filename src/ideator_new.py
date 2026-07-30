import ollama
import random
import re
import json
import os

from config import CURRENT_DATE
from knowledge_base_rag import buscar_conhecimento_local

from ollama_client import chat_safe, extract_json_from_text

MODELO_LLM = "phi4-mini" # Modelo rápido para ideação
HISTORICO_FILE = "temas_gerados.json"

NICHOS = [
    "Astronomia e Exploração Espacial",
    "Arqueologia e Civilizações Antigas",
    "Ciência e Física Quântica",
    "Biologia e Criaturas Reais",
    "História e Mistérios do Passado",
    "Tecnologia e Futuro",
    "Geografia e Lugares Extremos",
]


def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def salvar_tema(tema):
    hist = carregar_historico()
    hist.append(tema)
    with open(HISTORICO_FILE, "w") as f:
        json.dump(hist, f, indent=4)


async def buscar_tendencias_reais(nicho):
    """
    Realiza uma busca na web para encontrar o que está sendo falado agora sobre o nicho.
    """
    from researcher import pesquisar_dados_brutos
    print(f"📡 Buscando tendências reais para: {nicho}...")
    
    query = f"latest discoveries news curiosity in {nicho} 2025 2026"
    resultados = await pesquisar_dados_brutos(query)
    
    if not resultados:
        return "Nenhuma tendência recente encontrada."
        
    resumo_contexto = ""
    for r in resultados[:5]:
        resumo_contexto += f"- {r.get('title')}: {r.get('content')[:200]}...\n"
        
    return resumo_contexto


async def gerar_tema_factual(nicho_especifico=None):
    if nicho_especifico:
        nicho = nicho_especifico
    else:
        nicho = random.choice(NICHOS)

    print(f"💡 Nicho/Contexto escolhido: {nicho}")
    
    # BUSCA DINÂMICA DE TENDÊNCIAS
    contexto_tendencias = await buscar_tendencias_reais(nicho)

    # Carrega histórico para evitar repetição
    historico = carregar_historico()
    exclusoes = ", ".join(historico[-10:]) if historico else "Nenhum"

    # O prompt focado em CURIOSIDADES e NOTÍCIAS
    prompt = f"""
Você é um pesquisador de **CURIOSIDADES FASCINANTES** e **NOTÍCIAS RECENTES**.
Estamos em {CURRENT_DATE}.

Nicho: {nicho}.

CONTEXTO DE TENDÊNCIAS REAIS (Use isso para inspirar o tema):
{contexto_tendencias}

Sua missão: Criar UM título de vídeo focado em um fato curioso, um segredo de desenvolvimento, um erro de design ou uma descoberta interessante (clássica ou recente).

REGRAS:
1. FOCO EM TENDÊNCIAS: Tente usar o contexto de tendências acima para criar algo que as pessoas estão pesquisando AGORA.
2. TÍTULO IMPACTANTE: O tema deve ser algo surpreendente ou interessante.
3. VARIEDADE: Pode ser uma curiosidade famosa já conhecida por muitos, ou uma descoberta científica/tecnológica recente de 2024, 2025 ou 2026.
4. NADA DE GENERALIDADES: Evite temas como "História de The Last of Us". Seja específico em um detalhe.
5. NÃO REPETIR: Histórico: {exclusoes}
6. RETORNO: Responda APENAS com um JSON puro: {{"title": "Título Curioso", "keywords": ["entidade", "curiosidade", "segredo", "news"]}}.
"""

    try:
        # CHAMADA SEGURA (Fila do Ollama)
        res = await chat_safe(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.8}
        )
        
        if not res: return None
        
        conteudo = res.get("message", {}).get("content", "").strip()
        
        # Extração inteligente
        dado = extract_json_from_text(conteudo)
        
        if not dado:
            # Fallback regex se o parse falhar
            m = re.search(r"\{.*\}", conteudo, re.DOTALL)
            if m:
                json_str = m.group()
                json_str = re.sub(r"//.*", "", json_str)
                dado = json.loads(json_str)
            else:
                return None

        title = dado.get("title", "").strip()
        keywords = dado.get("keywords", [])

        # Salva no histórico para não repetir
        salvar_tema(title)

        print(f"🎯 Tema Sugerido: {title} | keywords: {keywords}")
        return {"title": title, "keywords": keywords}

    except Exception:
        from knowledge_base import TEMAS_ESTRUTURADOS
        fallback = random.choice(TEMAS_ESTRUTURADOS)
        return {"title": fallback, "keywords": fallback.split()[:3]}


async def gerar_tema_com_base():
    """
    Gera um tema combinando a IA com nosso Banco de Dados de Entidades (knowledge_base.py).
    Isso garante que o tema seja focado em algo que REALMENTE existe e é interessante.
    """
    from knowledge_base import ENTIDADES_POR_NICHO
    
    nicho_escolhido = random.choice(list(ENTIDADES_POR_NICHO.keys()))
    entidade = random.choice(ENTIDADES_POR_NICHO[nicho_escolhido])

    print(f"💡 Combinando IA com Entidade Real: {entidade} (Nicho: {nicho_escolhido})")

    prompt = f"""
Você é um estrategista de conteúdo viral.
Estamos em {CURRENT_DATE}.

Sua tarefa é criar um TÍTULO IMPACTANTE para um vídeo de 1 minuto sobre a entidade: "{entidade}".

O vídeo deve focar em um SEGREDO, um ERRO, uma CURIOSIDADE FAMOSA ou uma NOTÍCIA/DESCOBERTA RECENTE sobre essa entidade.

REGRAS:
1. FOCO TOTAL NA ENTIDADE: "{entidade}".
2. TÍTULO VIRAL: Use ganchos como "O segredo de...", "O erro que ninguém viu...", "A verdade sobre...".
3. VERACIDADE: NÃO adicione informações que não sejam verdadeiras sobre a entidade.
4. RETORNO: Responda APENAS um JSON: {{"title": "Título", "keywords": ["k1", "k2"]}}.
"""

    try:
        res = await chat_safe(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7}
        )
        if not res: return None
        
        dado = extract_json_from_text(res.get("message", {}).get("content", ""))
        if dado:
            dado['entity'] = entidade 
            return dado
    except:
        pass
    
    return {"title": f"O segredo por trás de {entidade}", "entity": entidade, "keywords": [entidade]}


async def gerar_tema_relacionado():
    """
    Usa o RAG para encontrar o que já pesquisamos e sugere um tema conectado.
    """
    print("🧠 Consultando memória para sugerir tema relacionado...")
    
    # Busca um "resumo" do que o vault sabe
    conhecimento = buscar_conhecimento_local("principais descobertas e fatos pesquisados", top_k=5)
    
    if not conhecimento:
        return await gerar_tema_factual()

    contexto_vault = "\n".join([c['text'][:200] for c in conhecimento])
    
    prompt = f"""
Você é um arquiteto de conteúdo. 
Baseado no que já pesquisamos no nosso Vault, sugira um NOVO tema que se conecte semanticamente.

CONTEXTO DO VAULT (O que já sabemos):
{contexto_vault}

MISSÃO: Sugerir um tema de vídeo que seja um "próximo passo" ou uma curiosidade ligada a esses fatos.
REGRAS: 
1. NÃO REPITA temas que já estão no contexto.
2. Seja específico.
3. Responda APENAS o JSON: {{"title": "Título", "entity": "Termo de busca", "keywords": []}}.
"""

    try:
        res = await chat_safe(model=MODELO_LLM, messages=[{"role": "user", "content": prompt}])
        if not res: return None
        return extract_json_from_text(res["message"]["content"])
    except:
        pass
        
    return await gerar_tema_factual()

def gerar_tema_da_base_por_nicho(nicho_input):
    """
    Tenta mapear o nicho escolhido pelo usuário para nosso Banco de Dados de Entidades Reais.
    """
    from knowledge_base import ENTIDADES_POR_NICHO
    
    # Mapeamento robusto de palavras-chave do menu para as chaves do banco de dados
    mapa = {
        "Game": "Games",
        "Video Game": "Games",
        "Anime": "Games",
        "Desenho": "Games",
        "Ciência": "Ciência e Espaço",
        "Espaço": "Ciência e Espaço",
        "Astronomy": "Ciência e Espaço",
        "História": "História e Mistérios",
        "History": "História e Mistérios",
        "Arqueologia": "História e Mistérios",
        "Ancient": "História e Mistérios",
        "True Crime": "True Crime e Mistérios",
        "Crim": "True Crime e Mistérios",
        "Tecnologia": "Tecnologia e Futuro",
        "Inteligência Artificial": "Tecnologia e Futuro"
    }
    
    chave_base = None
    for k, v in mapa.items():
        if k.lower() in nicho_input.lower():
            chave_base = v
            break
            
    if chave_base and chave_base in ENTIDADES_POR_NICHO:
        entidade = random.choice(ENTIDADES_POR_NICHO[chave_base])
        print(f"💡 Entidade Real Selecionada ({chave_base}): {entidade}")
        return {"title": f"O segredo oculto de {entidade}", "entity": entidade, "keywords": [entidade, "secret", "curiosity"]}
    
    return None
