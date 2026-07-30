import ollama
import asyncio
import json
import re
import requests
import urllib.parse
import trafilatura
from collections import Counter
from config import TAVILY_API_KEY, SERPER_API_KEY, CURRENT_DATE
from knowledge_base_rag import buscar_conhecimento_local
from ollama_client import chat_safe, extract_json_from_text

# Tenta importar Tavily
try:
    from tavily import TavilyClient
except (ImportError, NameError):
    TavilyClient = None

# duckduckgo_search foi renomeado para ddgs; tente importar ambos para compatibilidade
try:
    from ddgs import DDGS
except Exception:
    try:
        from duckduckgo_search import DDGS
    except Exception:
        DDGS = None

# spaCy é usado opcionalmente para NER local. Se não instalado, prosseguimos com heurísticas.
try:
    import spacy

    try:
        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        # Modelo não instalado localmente
        _nlp = None
except Exception:
    _nlp = None

MODELO_LLM = "phi4-mini" # Modelo Turbo para extração

# Domínios que tipicamente são ruído ou de baixa confiabilidade para verificação factual
BLACKLIST_DOMAINS = [
    "linguee.com", "mercadolivre", "sephora", "facebook.com", "vimeo.com",
    "minijogos.com", "amazon.com", "ebay.com", "pinterest.com", "instagram.com",
    "twitter.com", "tiktok.com", "shopee.com", "aliexpress.com"
]

# Padrões/indicadores de fonte confiável
TRUSTED_PATTERNS = [
    "wikipedia.org", "britannica.com", "history.com", "nationalgeographic.com",
    "nasa.gov", "esa.int", "nature.com", "scientificamerican.com",
    "smithsonianmag.com", ".edu", ".gov", ".gov.br", "nytimes.com", "bbc.com",
    "theguardian.com", "reuters.com", "apnews.com", "forbes.com"
]

def _get_domain(url):
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if ":" in domain:
            domain = domain.split(":")[0]
        return domain
    except Exception:
        return ""

def _is_blacklisted(url_or_domain):
    d = (url_or_domain or "").lower()
    for b in BLACKLIST_DOMAINS:
        if b in d: return True
    return False

def _is_trusted(url_or_domain):
    d = (url_or_domain or "").lower()
    for t in TRUSTED_PATTERNS:
        if t in d: return True
    return False

def _annotate_and_filter_results(results):
    out = []
    removed = 0
    for f in results:
        url = f.get("url") or ""
        domain = _get_domain(url) if url else ""
        f["domain"] = domain
        f["trusted"] = _is_trusted(domain or url)
        f["blacklisted"] = _is_blacklisted(domain or url)
        if f["blacklisted"]:
            removed += 1
            continue
        out.append(f)
    return out, removed

def _sanitize_for_query(text):
    if not text: return text
    quoted = re.findall(r'["\'`](.*?)["\'`]', text)
    candidate = quoted[-1] if quoted else text.splitlines()[-1]
    candidate = re.sub(r"^(Search Term:|Output:|Aqui está o termo de busca:)\s*", "", candidate, flags=re.IGNORECASE).strip()
    candidate = re.sub(r"^\s*-\s*|^\s*\d+\.\s*", "", candidate).strip()
    return candidate.strip(" .")

def _extrair_conteudo_profundo(url):
    try:
        print(f"   📄 Extraindo conteúdo profundo de: {url}")
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            content = trafilatura.extract(downloaded, include_comments=False, include_tables=True, no_fallback=False)
            if content and len(content) > 500:
                return content
    except Exception as e:
        print(f"   ⚠️ Erro ao extrair conteúdo profundo: {e}")
    return None

def pesquisar_tavily(query):
    if not TavilyClient or not TAVILY_API_KEY: return []
    try:
        print(f"   📡 Buscando via Tavily: {query}")
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, search_depth="advanced", max_results=5)
        resultados = []
        for r in response.get("results", []):
            content = r.get("content", "")
            if len(content) < 500:
                deep = _extrair_conteudo_profundo(r.get("url"))
                if deep: content = deep
            resultados.append({
                "title": r.get("title", ""),
                "content": content,
                "url": r.get("url", ""),
                "source": "tavily",
                "text": f"Título: {r.get('title')}\nConteúdo: {content}"
            })
        return resultados
    except Exception as e:
        print(f"   ⚠️ Erro na busca Tavily: {e}")
        return []

def pesquisar_serper(query):
    if not SERPER_API_KEY: return []
    try:
        print(f"   📡 Buscando via Serper: {query}")
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()
        resultados = []
        for r in data.get("organic", []):
            snippet = r.get("snippet", "")
            content = _extrair_conteudo_profundo(r.get("link")) or snippet
            resultados.append({
                "title": r.get("title", ""),
                "content": content,
                "url": r.get("link", ""),
                "source": "serper",
                "text": f"Título: {r.get('title')}\nConteúdo: {content}"
            })
        return resultados
    except Exception as e:
        print(f"   ⚠️ Erro na busca Serper: {e}")
        return []

async def pesquisar_dados_brutos(tema, keywords=None):
    """Realiza busca na web usando múltiplas estratégias para maximizar chance de dados reais."""
    print(f"🔍 Pesquisando dados reais sobre: {tema}...")
    req_headers = {"User-Agent": "Mozilla/5.0"}
    tema_raw = str(tema)
    tema_clean = re.sub(r"[\n\r]+", " ", tema_raw).strip()
    
    # 0) Vault Local (RAG) - PRIORIDADE ZERO
    resultados_brutos = []
    print(f"   📂 Consultando conhecimento local no Vault...")
    conhecimento_local = buscar_conhecimento_local(tema_clean, top_k=5)
    for res in conhecimento_local:
        resultados_brutos.append({
            "title": f"Nota do Vault: {res['source']}",
            "content": res['text'],
            "url": f"obsidian://vault/{res['source']}",
            "source": "vault",
            "trusted": True
        })

    # === IDENTIFICAÇÃO INTELIGENTE DA ENTIDADE ===
    tema_en = tema_clean
    try:
        # Prompt Robusto 3.3: Mantém a especificidade e evita generalização
        prompt_entidade = f"""
        Extract the specific, searchable ENTITY in ENGLISH from the theme below.
        Theme: '{tema_clean}'
        
        RULES:
        1. Be SPECIFIC. "Piri Reis map history" -> "Piri Reis map". NOT just "map".
        2. Output ONLY the term. No explanations.
        """
        res_trans = await chat_safe(model=MODELO_LLM, messages=[{"role": "user", "content": prompt_entidade}])
        if res_trans:
            tema_en = _sanitize_for_query(res_trans.get("message", {}).get("content", ""))
            print(f"   🎯 Entidade para busca: '{tema_en}'")
        
        # Prompt de Pesquisa Histórica/Técnica: Evita o erro de "futuro 2026"
        prompt_queries = f"""
        Generate 3 short, effective search engine queries in ENGLISH about '{tema_en}'.
        Focus on:
        1. Basic facts and official timeline.
        2. Technical details, secrets or mysteries.
        3. Academic or confirmed discoveries (including any updates up to {CURRENT_DATE}).
        
        Output ONLY the 3 queries, one per line. No conversational text. No quotes.
        """
        res_queries = await chat_safe(model=MODELO_LLM, messages=[{"role": "user", "content": prompt_queries}])
        if res_queries:
            todas_queries = res_queries.get("message", {}).get("content", "").strip().splitlines()
            # Limpeza de números se houver
            todas_queries = [re.sub(r"^\d+[\.\s]*-?\s*", "", q).strip() for q in todas_queries if q.strip()]
        else:
            todas_queries = [f"{tema_en} facts", f"{tema_en} history"]
    except Exception as e:
        print(f"   ⚠️ Erro ao gerar queries: {e}")
        todas_queries = [f"{tema_en} facts", f"{tema_en} history"]

    # Executa buscas no Tavily (Prioridade)
    for q in todas_queries[:2]:
        if TAVILY_API_KEY:
            resultados_brutos.extend(pesquisar_tavily(q))
        elif SERPER_API_KEY:
            resultados_brutos.extend(pesquisar_serper(q))
        if len(resultados_brutos) >= 15: break

    # Fallback Wikipedia se estiver muito vazio
    if len(resultados_brutos) < 5:
        try:
            search_api = "https://en.wikipedia.org/w/api.php"
            params = {"action": "query", "list": "search", "srsearch": tema_en, "format": "json", "srlimit": 3}
            resp = requests.get(search_api, params=params, headers=req_headers, timeout=10)
            hits = resp.json().get("query", {}).get("search", [])
            for h in hits:
                title = h.get("title")
                page_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
                p = requests.get(page_url, headers=req_headers, timeout=10)
                resultados_brutos.append({
                    "title": title,
                    "content": p.json().get("extract", ""),
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                    "source": "wikipedia",
                    "trusted": True
                })
        except: pass

    annotated, _ = _annotate_and_filter_results(resultados_brutos)
    return annotated

STOPWORDS = set(["the", "and", "of", "in", "a", "an", "to", "for", "on", "with", "by", "is", "are", "that", "this"])

def _norm_words(s):
    s_clean = re.sub(r"\[.*?\]|\(.*?\)", "", s)
    s_clean = s_clean.replace('"', '').replace("'", "")
    s2 = re.sub(r"[^a-zA-Z0-9\s]", " ", s_clean.lower())
    return [t for t in s2.split() if t and t not in STOPWORDS]

def confirmar_fato(fato_text, frags, tema, min_sources=2):
    if not fato_text or not frags: return False, []
    fato_limpo = re.sub(r"\[\d+\]", "", fato_text).strip()
    norm_fact = _norm_words(fato_limpo)
    if len(norm_fact) < 3: return False, []

    # Check Vault
    try:
        conhecimento_previo = buscar_conhecimento_local(fato_limpo, top_k=1)
        if conhecimento_previo and conhecimento_previo[0].get('score', 999) < 0.8:
            return True, [f"vault://{conhecimento_previo[0]['source']}"]
    except: pass

    sources = set()
    source_trust = {}
    for f in frags:
        if f.get("blacklisted"): continue
        combined = (f.get("title", "") + " " + f.get("content", "")).lower()
        domain_or_url = f.get("domain") or f.get("url") or f.get("source") or combined[:30]
        is_tr = f.get("trusted") or _is_trusted(domain_or_url)
        
        overlap = len(set(norm_fact) & set(_norm_words(combined)))
        if overlap >= (3 if is_tr else 5):
            sources.add(domain_or_url)
            source_trust[domain_or_url] = is_tr
            if is_tr and overlap >= 4: return True, [domain_or_url]

    if len(sources) >= min_sources: return True, list(sources)
    return False, []

async def gerar_resumo_factual(texto_bruto, tema, use_llm=True):
    """Extrai fatos em fila segura para não travar VRAM."""
    if not texto_bruto: return None
    print(f"📝 Extraindo fatos para: {tema}...")
    
    fragments = texto_bruto if isinstance(texto_bruto, list) else [texto_bruto]
    max_frag = 6
    lista = []
    for i, f in enumerate(fragments[:max_frag], start=1):
        content = (f.get("content") or "")[:1200].replace("\n", " ")
        lista.append(f"[{i}] {f.get('title')} | {content}")
    
    prompt = f"""
Extract EXACT and VERIFIED facts in ENGLISH about "{tema}" from the fragments below.
Current Date: {CURRENT_DATE}

MANDATORY JSON STRUCTURE:
{{
  "fatos": [
    {{ 
      "fato": "Short factual statement (STRING ONLY, no brackets, no quotes inside)", 
      "detalhe": "Supporting context (STRING ONLY)", 
      "confianca": 0.95 
    }}
  ]
}}

RULES:
1. NO ARRAYS INSIDE STRINGS: Do NOT use ["fact"]. Use "fact".
2. NO CITATIONS: Do not include [1] or (Source) in the text.
3. BE LITERAL: Extract only what is present in the fragments.
4. ENGLISH ONLY: Facts must be in English.

FRAGMENTS:
""" + "\n".join(lista)
    
    try:
        res = await chat_safe(model=MODELO_LLM, messages=[{"role": "user", "content": prompt}], format="json")
        if not res: return None
        dados_llm = extract_json_from_text(res.get("message", {}).get("content", ""))
        if not dados_llm: return None

        fatos_confirmados = []
        for f in dados_llm.get("fatos", []):
            conf, src = confirmar_fato(f.get("fato"), fragments, tema)
            if conf:
                f["confirmado_em"] = src
                fatos_confirmados.append(f)
        
        if not fatos_confirmados: return None
        return {"entidade": tema, "fatos": fatos_confirmados, "densidade_factual": "alta" if len(fatos_confirmados) > 2 else "baixa"}
    except: return None

async def traduzir_fatos_json(fatos_json):
    if not fatos_json or not fatos_json.get("fatos"): return fatos_json
    print("🌐 Traduzindo fatos...")
    textos = [f.get("fato", "") for f in fatos_json["fatos"]] + [f.get("detalhe", "") for f in fatos_json["fatos"]]
    prompt = f"Translate to Brazilian Portuguese, one per line:\n{json.dumps(textos)}"
    try:
        res = await chat_safe(model="phi4-mini", messages=[{"role": "user", "content": prompt}])
        traducoes = [line.strip() for line in res.get("message", {}).get("content", "").splitlines() if line.strip()]
        num = len(fatos_json["fatos"])
        for i in range(num):
            if i < len(traducoes): fatos_json["fatos"][i]["fato"] = traducoes[i]
            if (i + num) < len(traducoes): fatos_json["fatos"][i]["detalhe"] = traducoes[i + num]
        return fatos_json
    except: return fatos_json

def validar_densidade(fatos_json):
    if not fatos_json: return False
    return len(fatos_json.get("fatos", [])) >= 2

if __name__ == "__main__":
    asyncio.run(gerar_resumo_factual({"title": "Test", "content": "Sample content"}, "Test Topic"))
