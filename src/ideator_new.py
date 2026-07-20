import ollama
import random
import re
import json
import os

MODELO_LLM = "llama3.1"
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
        with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def salvar_tema(tema):
    hist = carregar_historico()
    # Adiciona tanto o título quanto a entidade (se possível extrair do título)
    hist.append(tema)
    # Limita o histórico para não crescer infinitamente, mantendo os últimos 100
    hist = hist[-100:]
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=4, ensure_ascii=False)


def gerar_tema_factual(nicho_especifico=None):
    if nicho_especifico:
        nicho = nicho_especifico
    else:
        nicho = random.choice(NICHOS)

    print(f"💡 Nicho/Contexto escolhido: {nicho}")

    # Carrega histórico para evitar repetição
    historico = carregar_historico()
    exclusoes = ", ".join(historico[-10:]) if historico else "Nenhum"

    # O prompt focado em CURIOSIDADES e NOTÍCIAS
    prompt = f"""
Você é um pesquisador de **CURIOSIDADES OBSCURAS** e **NOTÍCIAS RECENTES**.
Nicho: {nicho}.

Sua missão: Criar UM título de vídeo focado em um fato curioso, um segredo de desenvolvimento, um erro de design ou uma notícia impactante.

REGRAS:
1. FOCO EM CURIOSIDADE/NOTÍCIA: O tema deve ser algo surpreendente (ex: "O segredo por trás do som dos Clickers em The Last of Us", "O erro de design que quase quebrou o PS2", "A nova descoberta da NASA em Marte").
2. NADA DE GENERALIDADES: Evite temas como "História de The Last of Us". Seja específico em um detalhe.
3. NÃO REPETIR: Histórico: {exclusoes}
4. RETORNO: Responda APENAS com um JSON puro: {{"title": "Título Curioso", "keywords": ["entidade", "curiosidade", "segredo", "news"]}}.
"""

    try:
        resposta = ollama.chat(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.8} # Temperatura alta para o ideador ter ideias novas
        )
        conteudo = resposta.get("message", {}).get("content", "").strip()
        
        # Limpeza agressiva para Llama 3.1
        m = re.search(r"\{.*\}", conteudo, re.DOTALL)
        if m:
            json_str = m.group()
            json_str = re.sub(r"//.*", "", json_str)
            dado = json.loads(json_str)
        else:
            clean_content = re.sub(r"```json|```", "", conteudo).strip()
            dado = json.loads(clean_content)

        title = dado.get("title", "").strip()
        keywords = dado.get("keywords", [])

        # Salva no histórico para não repetir
        salvar_tema(title)

        print(f"🎯 Tema Sugerido: {title} | keywords: {keywords}")
        return {"title": title, "keywords": keywords}

    except Exception:
        from knowledge_base import TEMAS_ESTRUTURADOS
        # Evita repetir temas do histórico no fallback
        historico = carregar_historico()
        disponiveis = [t for t in TEMAS_ESTRUTURADOS if t not in historico]
        fallback = random.choice(disponiveis if disponiveis else TEMAS_ESTRUTURADOS)
        return {"title": fallback, "keywords": fallback.split()[:3]}


def gerar_tema_com_base():
    """
    Gera um tema combinando a IA com nosso Banco de Dados de Entidades (knowledge_base.py).
    Isso garante que o tema seja focado em algo que REALMENTE existe e é interessante.
    """
    from knowledge_base import ENTIDADES_POR_NICHO
    
    # Carrega histórico para filtrar entidades já usadas
    historico = carregar_historico()
    
    # Flatten todas as entidades e filtra as que já aparecem no histórico (mesmo que parcialmente)
    todas_entidades = []
    for n in ENTIDADES_POR_NICHO.values():
        todas_entidades.extend(n)
    
    disponiveis = []
    for e in todas_entidades:
        ja_usada = False
        for t in historico:
            if e.lower() in t.lower():
                ja_usada = True
                break
        if not ja_usada:
            disponiveis.append(e)
    
    if not disponiveis:
        # Se esgotar, limpa o histórico de entidades (opcional) ou apenas ignora filtro
        disponiveis = todas_entidades

    entidade = random.choice(disponiveis)
    
    # Encontra o nicho da entidade para o log
    nicho_escolhido = "Desconhecido"
    for k, v in ENTIDADES_POR_NICHO.items():
        if entidade in v:
            nicho_escolhido = k
            break

    print(f"💡 Combinando IA com Entidade Real: {entidade} (Nicho: {nicho_escolhido})")

    prompt = f"""
Você é um estrategista de conteúdo viral.
Sua tarefa é criar um TÍTULO IMPACTANTE para um vídeo de 1 minuto sobre a entidade: "{entidade}".

O vídeo deve focar em um SEGREDO, um ERRO, uma CURIOSIDADE ou uma NOTÍCIA sobre essa entidade.

REGRAS:
1. FOCO TOTAL NA ENTIDADE: "{entidade}".
2. TÍTULO VIRAL: Use ganchos como "O segredo de...", "O erro que ninguém viu...", "A verdade sobre...".
3. RETORNO: Responda APENAS um JSON: {{"title": "Título", "keywords": ["k1", "k2"]}}.
"""

    try:
        resposta = ollama.chat(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7}
        )
        conteudo = resposta.get("message", {}).get("content", "").strip()
        m = re.search(r"\{.*\}", conteudo, re.DOTALL)
        if m:
            json_str = m.group()
            dado = json.loads(json_str)
            return dado
    except:
        pass
    
    return {"title": f"O segredo por trás de {entidade}", "keywords": [entidade]}


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
        "Crim": "True Crime e Mistérios"
    }
    
    # Carrega histórico para filtrar entidades já usadas
    historico = carregar_historico()
    
    chave_base = None
    for k, v in mapa.items():
        if k.lower() in nicho_input.lower():
            chave_base = v
            break
            
    if chave_base and chave_base in ENTIDADES_POR_NICHO:
        # Filtra entidades do nicho que ainda não foram usadas
        entidades_nicho = ENTIDADES_POR_NICHO[chave_base]
        disponiveis = []
        for e in entidades_nicho:
            ja_usada = False
            for t in historico:
                if e.lower() in t.lower():
                    ja_usada = True
                    break
            if not ja_usada:
                disponiveis.append(e)

        if not disponiveis:
            disponiveis = entidades_nicho

        entidade = random.choice(disponiveis)
        print(f"💡 Entidade Real Selecionada ({chave_base}): {entidade}")
        return {"title": f"O segredo oculto de {entidade}", "keywords": [entidade, "secret", "curiosity"]}
    
    return None
