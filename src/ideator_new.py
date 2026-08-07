import ollama
import random
import re
import json
import os

from config import CURRENT_DATE
from knowledge_base_rag import buscar_conhecimento_local

from ollama_client import chat_safe, extract_json_from_text

MODELO_LLM = "phi4-mini" 
HISTORICO_FILE = "data/temas_historico.json"
DISCOVERY_QUEUE = "data/discovery_queue.json"
KEYWORD_BLACKLIST_FILE = "data/keyword_blacklist.json"

# Unificação de Nichos (Agents + Styles)
NICHOS_CONFIG = {
    "Games": "game development secrets, unreleased prototypes, technical glitches, industry mysteries",
    "Ciência e Espaço": "astronomy discoveries, physics breakthroughs, space mission secrets, cosmic phenomena",
    "História e Mistérios": "archaeological finds, ancient civilizations, historical enigmas, lost documents",
    "True Crime e Mistérios": "forensic science breakthroughs, cold cases, criminal psychology, investigation secrets",
    "Tecnologia e Futuro": "AI innovations, hardware breakthroughs, software architecture, futuristic tech leaks",
    "Desenhos e Anime": "animation techniques, studio production secrets, lost media, voice acting history"
}

NICHOS = list(NICHOS_CONFIG.keys())

def carregar_json(filepath, default_val):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default_val
    return default_val

def salvar_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_niche_seeds(nicho):
    """
    Retorna 3 entidades aleatórias da base manual para servir de 'âncora' para a pesquisa.
    """
    from knowledge_base import ENTIDADES_POR_NICHO
    base = ENTIDADES_POR_NICHO.get(nicho, ["curiosidades", "segredos", "mistérios"])
    return random.sample(base, min(len(base), 3))

async def buscar_tendencias_reais(nicho):
    """
    Realiza uma busca na web misturando sementes manuais com tendências atuais.
    """
    from researcher import pesquisar_dados_brutos
    
    seeds = get_niche_seeds(nicho)
    print(f"📡 Buscando tendências RECENTES (2024-2026) para {nicho}...")
    
    # Constrói uma query que força a internet a buscar coisas SIMILARES às nossas sementes
    # Foco absoluto em notícias RECENTES de 2024, 2025 e 2026.
    seeds_str = " or ".join(seeds)
    query = (
        f"breaking {nicho} technical secrets, leaked production data or major discoveries "
        f"SIMILAR to {seeds_str} PUBLISHED IN 2024 OR 2025 OR 2026. "
        f"Ignore legacy/old facts."
    )
    
    resultados = await pesquisar_dados_brutos(query, nicho=nicho)
    
    if not resultados:
        return f"Sem novidades recentes. Foque em mistérios técnicos de {seeds_str}."
        
    resumo_contexto = "NOTÍCIAS E DESCOBERTAS RECENTES (2024-2026):\n"
    for r in resultados[:6]:
        # Filtro de relevância temporal e de nicho
        content = r.get('content', '').lower()
        title = r.get('title', '').lower()
        
        # Bloqueio de loop de Neutrons/Física em outros nichos
        if nicho != "Ciência e Espaço" and any(w in content + title for w in ["quantum", "neutron", "nuclear", "physics breakthrough"]):
            continue
            
        resumo_contexto += f"- {r.get('title')}: {r.get('content')[:250]}...\n"
        
    return resumo_contexto

async def gerar_tema_factual(nicho_especifico=None):
    # 1. Tenta Discovery Queue
    entity_from_queue = None
    if os.path.exists(DISCOVERY_QUEUE):
        try:
            queue = carregar_json(DISCOVERY_QUEUE, [])
            if queue:
                entity_from_queue = queue.pop(0)
                salvar_json(DISCOVERY_QUEUE, queue)
                print(f"📡 Usando Fila de Descoberta: {entity_from_queue}")
        except: pass

    nicho = nicho_especifico or random.choice(NICHOS)
    seeds = get_niche_seeds(nicho)
    
    if entity_from_queue:
        return {
            "title": f"O segredo por trás de {entity_from_queue}", 
            "entity": entity_from_queue, 
            "keywords": [entity_from_queue], 
            "nicho": nicho
        }

    print(f"💡 Gerando tema HÍBRIDO para: {nicho}")
    
    # 2. Busca Contexto Real do Nicho ancorado nas Seeds
    contexto_tendencias = await buscar_tendencias_reais(nicho)

    # 3. Gestão de Histórico e Blacklist
    historico = carregar_json(HISTORICO_FILE, [])
    blacklist = carregar_json(KEYWORD_BLACKLIST_FILE, [])
    
    exclusoes = ", ".join(historico[-15:]) if historico else "Nenhum"
    termos_proibidos = ", ".join(blacklist[-20:]) if blacklist else "Nenhum"

    prompt = f"""
Você é um Documentarista Especialista no nicho: **{nicho}**.
Estamos em {CURRENT_DATE}.

### REFERÊNCIAS DE ESTILO (TEMAS QUE AMAMOS):
{", ".join(seeds)}

### CONTEXTO REAL DE HOJE (Internet):
{contexto_tendencias}

### MISSÃO:
Crie UM título de vídeo documentário IMPACTANTE em PORTUGUÊS DO BRASIL sobre um fato REAL, um segredo técnico ou um erro de design dentro do nicho {nicho}.

### REGRAS DO SISTEMA HÍBRIDO:
1. IDIOMA OBRIGATÓRIO: Responda o título e a entidade em PORTUGUÊS DO BRASIL.
2. MISTURA: Use o "Contexto Real" para encontrar algo NOVO, mas use as "Referências de Estilo" para garantir que o tema seja profundo e técnico.
2. ZERO CIÊNCIA EM OUTROS NICHOS: Se o nicho é {nicho}, você NÃO PODE falar de física ou astronomia.
3. NÃO REPETIR: 
   - Títulos já usados: {exclusoes}
   - Palavras Proibidas: {termos_proibidos}
4. ESPECIFICIDADE: Seja clínico. Ex: Em vez de "Design de Personagem", fale sobre "O erro na proporção dos quadros do Studio Ghibli".

RESPONDA APENAS O JSON:
{{
  "title": "Título Viral e Curioso",
  "entity": "Entidade pesquisável principal",
  "keywords": ["key1", "key2"]
}}
"""

    try:
        res = await chat_safe(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.9} # Aumentado para mais criatividade
        )
        if not res: return None
        
        dado = extract_json_from_text(res.get("message", {}).get("content", ""))
        if not dado: return None

        # --- VALIDATION: IDIOMA DO TEMA ---
        english_words = [" the ", " in ", " and ", " secrets ", " mystery ", " hidden "]
        if any(w in f" {dado['title'].lower()} " for w in english_words):
            print(f"⚠️ IA gerou título em Inglês. Re-solicitando...")
            return await gerar_tema_factual(nicho_especifico=nicho)

        # Atualiza histórico e blacklist
        historico.append(dado["title"])
        salvar_json(HISTORICO_FILE, historico[-50:])
        
        # Extrai palavras-chave para a blacklist (evita o loop de neutrons)
        # Filtra palavras pequenas
        novos_termos = [w.lower() for w in dado["entity"].split() if len(w) > 3]
        blacklist.extend(novos_termos)
        salvar_json(KEYWORD_BLACKLIST_FILE, blacklist[-100:])

        dado["nicho"] = nicho
        print(f"🎯 Novo Tema Gerado: {dado['title']} [{nicho}]")
        return dado

    except Exception as e:
        print(f"⚠️ Erro na ideação: {e}")
        return None

async def expandir_nicho(tema, fatos_json):
    """
    Analisa os fatos de um tema e sugere 3 novas entidades relacionadas para pesquisa futura.
    """
    if not fatos_json or not fatos_json.get("fatos"): return
    
    print(f"🧠 Expandindo conhecimento para o nicho de: {tema}...")
    fatos_texto = "\n".join([f"- {f['fato']}" for f in fatos_json["fatos"][:5]])
    
    prompt = f"""
    Based on the following facts about '{tema}', suggest 3 SPECIFIC and searchable ENTITIES or MYSTERIES for a new documentary.
    
    FACTS:
    {fatos_texto}
    
    RULES:
    1. Be highly specific.
    2. Suggest only real, searchable terms in ENGLISH.
    3. Response must be a JSON array of strings: ["Entity 1", "Entity 2", "Entity 3"].
    """
    
    try:
        res = await chat_safe(model=MODELO_LLM, messages=[{"role": "user", "content": prompt}])
        if not res: return
        novas_entidades = extract_json_from_text(res["message"]["content"])
        
        if novas_entidades and isinstance(novas_entidades, list):
            queue = carregar_json(DISCOVERY_QUEUE, [])
            queue.extend([e for e in novas_entidades if e not in queue])
            salvar_json(DISCOVERY_QUEUE, queue[-50:])
            print(f"✨ Novas entidades descobertas: {', '.join(novas_entidades)}")
    except: pass

async def gerar_tema_com_base():
    from knowledge_base import ENTIDADES_POR_NICHO
    nicho = random.choice(NICHOS)
    entidades = ENTIDADES_POR_NICHO.get(nicho, ["Misterio"])
    entidade = random.choice(entidades)
    
    return {
        "title": f"O segredo oculto por trás de {entidade}",
        "entity": entidade,
        "keywords": [entidade, "secret"],
        "nicho": nicho
    }

async def gerar_tema_relacionado():
    conhecimento = await buscar_conhecimento_local("principais descobertas e fatos pesquisados", top_k=5)
    if not conhecimento: return await gerar_tema_factual()
    
    contexto_vault = "\n".join([c['text'][:200] for c in conhecimento])
    prompt = f"Baseado no que já pesquisamos:\n{contexto_vault}\nSugira um NOVO tema específico em JSON: {{\"title\":\"\", \"entity\":\"\", \"nicho\":\"\"}}"
    
    try:
        res = await chat_safe(model=MODELO_LLM, messages=[{"role": "user", "content": prompt}])
        return extract_json_from_text(res["message"]["content"])
    except: return await gerar_tema_factual()

def gerar_tema_da_base_por_nicho(nicho_input):
    """
    Tenta mapear o nicho escolhido pelo usuário para nosso Banco de Dados de Entidades Reais.
    """
    from knowledge_base import ENTIDADES_POR_NICHO
    
    # Mapeamento robusto de palavras-chave do menu para as chaves do banco de dados
    mapa = {
        "Game": "Games",
        "Video Game": "Games",
        "Anime": "Desenhos e Anime",
        "Desenho": "Desenhos e Anime",
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
        return {
            "title": f"O segredo oculto de {entidade}", 
            "entity": entidade, 
            "keywords": [entidade, "secret", "curiosity"],
            "nicho": chave_base
        }
    
    return None
