import ollama
import json
import re
import requests
import urllib.parse
import trafilatura
from collections import Counter
from config import TAVILY_API_KEY, SERPER_API_KEY

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

MODELO_LLM = "phi4-mini"

# Domínios que tipicamente são ruído ou de baixa confiabilidade para verificação factual
BLACKLIST_DOMAINS = [
    "linguee.com",
    "mercadolivre",
    "sephora",
    "facebook.com",
    "vimeo.com",
    "minijogos.com",
    "mercado livre",
    "mercadolivre.com.br",
    "youtube.com/watch",
    "youtube.com",
    "amazon.com",
    "ebay.com",
    "pinterest.com",
    "instagram.com",
    "twitter.com",
    "tiktok.com",
    "reddit.com",
    "cambridge.org",
    "dictionary.com",
    "collinsdictionary.com",
    "merriam-webster.com",
    "dicio.com.br",
    "priberam.org",
    "infopedia.pt",
    "fragrantica.com",
    "belezanaweb.com",
    "shopee.com",
    "aliexpress.com",
    "magazineluiza.com",
    "casasbahia.com",
    "extra.com",
    "pontofrio.com",
    "globo.com/shopping",
    "estantevirtual.com",
    "letras.mus.br",
    "vagalume.com.br",
    "genius.com",
    "lyrics.com",
]

# Padrões/indicadores de fonte confiável (usar como sinal forte)
TRUSTED_PATTERNS = [
    "wikipedia.org",
    "britannica.com",
    "history.com",
    "nationalgeographic.com",
    "nasa.gov",
    "esa.int",
    "nature.com",
    "scientificamerican.com",
    "smithsonianmag.com",
    ".edu",
    ".gov",
    ".gov.br",
    "nytimes.com",
    "bbc.com",
    "theguardian.com",
    "washingtonpost.com",
    "cnn.com",
    "reuters.com",
    "apnews.com",
    "forbes.com",
    ".org",
    "fandom.com",
    "ign.com",
    "gamespot.com",
    "eurogamer.net",
    "kotaku.com",
    "pcinvasion.com",
    "rockpapershotgun.com",
    "reddit.com/r/todayilearned",
    "reddit.com/r/gaming",
    "reddit.com/r/science",
]


def _get_domain(url):
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        # remove porta ou credenciais
        if ":" in domain:
            domain = domain.split(":")[0]
        return domain
    except Exception:
        return ""


def _is_blacklisted(url_or_domain):
    d = (url_or_domain or "").lower()
    for b in BLACKLIST_DOMAINS:
        if b in d:
            return True
    return False


def _is_trusted(url_or_domain):
    d = (url_or_domain or "").lower()
    for t in TRUSTED_PATTERNS:
        if t in d:
            return True
    return False


def _annotate_and_filter_results(results):
    """Anota cada fragmento com 'domain' e 'trusted' e remove fragments blacklisted.
    Retorna lista filtrada e count removidos.
    """
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
    """Remove aspas, quebras de linha e conteúdo explicativo que LLMs às vezes adicionam."""
    if not text:
        return text
    # Mantém apenas a primeira linha e remove explicações do tipo "The translation is: ..."
    first_line = text.splitlines()[-1] if "\n" in text else text
    # Remove frases explicativas separadas por ':'
    if ":" in first_line and len(first_line.split()) > 1:
        parts = first_line.split(":")
        candidate = parts[-1]
    else:
        candidate = first_line
    # Remove quotes and trim
    candidate = re.sub(r"[\"'`]+", "", candidate).strip()
    # Remove trailing punctuation
    candidate = candidate.strip(" .")
    return candidate


def _extrair_conteudo_profundo(url):
    """Usa trafilatura para extrair o texto principal de uma URL."""
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
    """Busca usando Tavily API."""
    if not TavilyClient or not TAVILY_API_KEY:
        return []
    
    try:
        print(f"   📡 Buscando via Tavily: {query}")
        client = TavilyClient(api_key=TAVILY_API_KEY)
        # Tavily search com context depth para obter mais conteúdo
        response = client.search(query=query, search_depth="advanced", max_results=5)
        
        resultados = []
        for r in response.get("results", []):
            content = r.get("content", "")
            # Se o conteúdo for muito curto, tenta extração profunda
            if len(content) < 500:
                deep = _extrair_conteudo_profundo(r.get("url"))
                if deep:
                    content = deep
            
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
    """Busca usando Serper.dev API."""
    if not SERPER_API_KEY:
        return []
    
    try:
        print(f"   📡 Buscando via Serper: {query}")
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5})
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()
        
        resultados = []
        for r in data.get("organic", []):
            snippet = r.get("snippet", "")
            # Serper só dá snippet, então extração profunda é quase obrigatória para RAG de qualidade
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


def pesquisar_dados_brutos(tema, keywords=None):
    """Realiza busca na web usando múltiplas estratégias para maximizar chance de dados reais."""
    print(f"🔍 Pesquisando dados reais sobre: {tema}...")

    # Cabeçalho padrão para evitar Erro 403 (Forbidden) na Wikipedia e em outros sites
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    tema_raw = str(tema)
    tema_clean = re.sub(r"[\n\r]+", " ", tema_raw).strip()
    
    # Extrai e limpa as palavras-chave cedo para uso global
    kws_limpas = []
    if keywords:
        if isinstance(keywords, (list, tuple)):
            kws_limpas = [_sanitize_for_query(str(k)) for k in keywords if k]
        else:
            kws_limpas = [_sanitize_for_query(str(keywords))]

    # === IDENTIFICAÇÃO INTELIGENTE DA ENTIDADE ===
    tema_en = tema_clean
    try:
        print(f"   🧠 Decifrando a entidade real para: {tema_clean}...")

        # Junta as keywords para dar contexto ao LLM (se existirem)
        contexto = (
            ", ".join([str(k) for k in keywords])
            if keywords
            else "Nenhum contexto adicional"
        )

        prompt_entidade = f"""
        Tema original: '{tema_clean}'
        Contexto: {contexto}

        Sua missão é extrair a ENTIDADE PRINCIPAL em INGLÊS para uma busca no Google.
        Seja específico. Não generalize.
        
        EXEMPLOS:
        - "O Segredo por Trás do Som dos Clickers em TLOU" -> "Clicker sound design The Last of Us"
        - "O erro que quase deletou Toy Story 2" -> "Toy Story 2 development accident"
        - "Por que o PS2 tem esse design?" -> "PlayStation 2 console design origin"

        REGRAS:
        1. RESPONDA APENAS com o termo de busca em INGLÊS.
        2. Mantenha o nome do jogo, filme ou pessoa envolvida.
        3. NÃO use termos genéricos como "sound effect" ou "video game" sozinhos.
        """

        print(f"   🧠 Decifrando a entidade real (via {MODELO_LLM})...")
        res_trans = ollama.chat(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt_entidade}],
            options={"temperature": 0.1, "top_p": 0.9}
        )
        conteudo = res_trans.get("message", {}).get("content", "").strip()
        print(f"   ✅ Entidade decifrada.")
        
        # LIMPEZA PARA LLAMA 3.1: Remove conversas e explicações
        # Pega a última linha ou frase se a IA começar a explicar
        tema_en_candidate = _sanitize_for_query(conteudo)
        tema_en = tema_en_candidate or tema_en

        print(f"   🎯 Entidade detectada para busca: '{tema_en}'")
    except Exception as e:
        print(f"   ⚠️ Erro ao decifrar entidade: {e}")
        tema_en = tema_clean

    # === ESTRATÉGIA DE BUSCA INCISIVA ===
    try:
        print(f"   🧠 Gerando perguntas incisivas para aprofundar a busca...")
        prompt_queries = f"""
        Tema: {tema_en}
        Keywords: {kws_limpas}
        
        Sua missão é gerar 3 perguntas em INGLÊS que vão direto na "ferida" do tema.
        Foque em: CAUSA RAIZ, SEGREDOS TÉCNICOS, FALHAS e DADOS NÃO REVELADOS.
        
        EXEMPLO (Xbox 360 RRoD):
        1. "Xbox 360 Red Ring of Death technical engineering failure analysis"
        2. "Why did Xbox 360 GPUs detach from motherboards?"
        3. "Microsoft internal reports on Xbox 360 hardware failure rate"
        
        REGRAS:
        - RESPONDA APENAS com as 3 perguntas (uma por linha).
        - Use termos como: "forensic analysis", "declassified", "technical root cause", "leaked", "behind the scenes".
        """
        print(f"   🧠 Gerando perguntas técnicas (via {MODELO_LLM})...")
        res_queries = ollama.chat(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt_queries}],
            options={"temperature": 0.2}
        )
        print(f"   ✅ Perguntas geradas.")
        perguntas_ia = res_queries.get("message", {}).get("content", "").strip().splitlines()
        perguntas_ia = [q.strip("- ").strip() for q in perguntas_ia if len(q.split()) > 3]
    except:
        perguntas_ia = []

    queries_estritas = []
    queries_amplas = []

    # Se já achou perguntas incisivas, prioriza elas. Se não, usa as padrão.
    if perguntas_ia:
        for q in perguntas_ia[:3]:
            # Tenta exata (com aspas) e tenta ampla (sem aspas)
            # IMPORTANTE: Remover numeração "1.", "2." do começo das perguntas da IA
            q_clean = re.sub(r"^\d+[\.\s]*-?\s*", "", q).strip()
            if q_clean:
                queries_estritas.append(f'"{q_clean}"') 
                queries_amplas.append(q_clean)

    # Adiciona buscas garantidas baseadas na entidade
    queries_estritas.append(f'"{tema_en}" facts')
    queries_estritas.append(f'"{tema_en}" history')
    
    # Filtra e organiza as queries finais
    todas_queries = []
    # Ordem de prioridade: Estritas primeiro, depois amplas
    for q in (queries_estritas + queries_amplas):
        if len(q.split()) > 1 and q not in todas_queries:
            todas_queries.append(q)

    # Filtra queries vazias ou muito genéricas
    todas_queries = [q for q in todas_queries if len(q.split()) > 1]

    resultados_brutos = []

    # 1) Tavily (Prioridade 1)
    if TAVILY_API_KEY:
        for q in todas_queries[:2]: # Usa as 2 melhores queries no Tavily
            results = pesquisar_tavily(q)
            resultados_brutos.extend(results)
            if len(resultados_brutos) >= 15:
                break
    
    # 2) Serper (Prioridade 2)
    if len(resultados_brutos) < 10 and SERPER_API_KEY:
        for q in todas_queries[:2]:
            results = pesquisar_serper(q)
            resultados_brutos.extend(results)
            if len(resultados_brutos) >= 15:
                break

    # 3) DuckDuckGo / DDGS (Fallback)
    if len(resultados_brutos) < 5 and DDGS is not None:
        try:
            with DDGS() as ddgs:
                for q in todas_queries:
                    # Remove aspas para o DuckDuckGo pois ele às vezes falha com queries muito específicas
                    q_ddg = q.replace('"', '')
                    print(f"   📡 Buscando (DDG): {q_ddg}")
                    try:
                        results = ddgs.text(
                            q_ddg, safesearch="moderate", max_results=5
                        )
                    except Exception as e:
                        print(f"   ⚠️ Erro na busca DDG para '{q_ddg}': {e}")
                        results = []

                    for r in results:
                        title = r.get("title") or r.get("heading") or ""
                        body = r.get("body") or r.get("snippet") or ""
                        href = r.get("href") or r.get("url") or ""
                        
                        # FILTRO DE DENSIDADE: Ignora resultados muito curtos ou que parecem anúncios
                        if len(body) < 100:
                            continue
                            
                        fragment_text = f"Título: {title}\nConteúdo: {body}".strip()
                        fragment = {
                            "title": title,
                            "content": body,
                            "url": href,
                            "source": "duckduckgo",
                            "text": fragment_text,
                        }
                        resultados_brutos.append(fragment)

                    # Se já achou fragmentos profundos suficientes, para
                    if len(resultados_brutos) > 20:
                        break

            if resultados_brutos:
                annotated, removed = _annotate_and_filter_results(resultados_brutos)
                print(
                    f"✅ Pesquisa DuckDuckGo concluída. Obtidos {len(resultados_brutos)} fragmentos; removidos por blacklist: {removed}."
                )
                return annotated
            else:
                print(f"⚠️ Nenhum resultado no DuckDuckGo. Tentando API direta...")
        except Exception as e:
            print(f"⚠️ Erro na pesquisa DuckDuckGo: {e}")

    # 2) Wikipedia API fallback (Com Headers Corrigidos)
    try:
        print("   📡 Tentando fallback com Wikipedia API...")
        search_api = "https://en.wikipedia.org/w/api.php"

        # Tenta primeiro com a entidade corrigida (estrito)
        termo_wiki = tema_en
        print(f"   📡 Buscando na Wiki por: {termo_wiki}")

        params = {
            "action": "query",
            "list": "search",
            "srsearch": termo_wiki,
            "format": "json",
            "srlimit": 3,
        }

        # PASSANDO O USER-AGENT AQUI PARA EVITAR O 403
        resp = requests.get(search_api, params=params, headers=req_headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("query", {}).get("search", [])

        for h in hits:
            title = h.get("title")
            page_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
            try:
                # PASSANDO O USER-AGENT AQUI TAMBÉM
                p = requests.get(page_url, headers=req_headers, timeout=10)
                p.raise_for_status()
                j = p.json()
                extract = j.get("extract") or ""
                fragment = {
                    "title": title,
                    "content": extract,
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                    "source": "wikipedia",
                }
                resultados_brutos.append(fragment)
            except Exception:
                continue
        
        # Tentativa de busca mais ampla na Wiki se a primeira falhou
        if not resultados_brutos:
            params["srsearch"] = " ".join(kws_limpas[:2]) if keywords and kws_limpas else tema_en
            resp = requests.get(search_api, params=params, headers=req_headers, timeout=10)
            data = resp.json()
            hits = data.get("query", {}).get("search", [])
            for h in hits:
                # ... repete lógica de extração simplificada se necessário ...
                pass

        if resultados_brutos:
            annotated, removed = _annotate_and_filter_results(resultados_brutos)
            print(
                f"✅ Wikipedia fallback obteve {len(resultados_brutos)} resumos; removidos: {removed}."
            )
            return annotated
    except Exception as e:
        print(f"⚠️ Erro ao consultar Wikipedia: {e}")

    return []


# Helper: normalize text and compute token overlap
STOPWORDS = set(
    [
        "the",
        "and",
        "of",
        "in",
        "a",
        "an",
        "to",
        "for",
        "on",
        "with",
        "by",
        "is",
        "are",
        "that",
        "this",
        "as",
        "it",
        "from",
        "at",
        "be",
    ]
)

def _norm_words(s):
    s2 = re.sub(r"[^a-zA-Z0-9\s]", " ", s.lower())
    toks = [t for t in s2.split() if t and t not in STOPWORDS]
    return toks

def confirmar_fato(fato_text, frags, tema, min_sources=2):
    """Confirma um fato verificando ocorrência em múltiplos fragments.

    Retorna (True, sources_list) se confirmado, caso contrário (False, []).
    Estratégia:
    - Ignora fragments de domínios blacklist
    - Match exato (substring) em fragments distintos
    - Ou overlap de tokens >=6 em pelo menos min_sources fragments
    - Se houver pelo menos 1 fonte "trusted", trata-a como suficiente (min_sources=1)
    - Detecção de conflitos numéricos (anos, valores).
    """
    if not fato_text or not frags:
        return False, []
    norm_fact = _norm_words(fato_text)
    if len(norm_fact) < 4: # Fatos muito curtos não são confiáveis
        return False, []

    sources = set()
    source_trust = {}
    numeros_no_fato = re.findall(r"\d+", fato_text)

    # Filtrar fragments blacklisted
    frags_filtered = [f for f in frags if not f.get("blacklisted")]
    if not frags_filtered:
        return False, []

    # Palavras de interface/ruído para ignorar no overlap
    noise_words = {"cookie", "privacy", "policy", "login", "register", "rights", "reserved", "click", "home", "search"}

    conflito_detectado = False
    
    for f in frags_filtered:
        content = f.get("content") or ""
        title = f.get("title") or ""
        url = f.get("url") or f.get("href") or ""
        combined = (title + " " + content).lower()
        domain_or_url = url or title or f.get("source") or combined[:50]
        trusted_flag = f.get("trusted") or _is_trusted(url or domain_or_url)

        # --- DETECÇÃO DE CONFLITO ---
        if numeros_no_fato:
            # Comparamos o overlap de palavras significativas (sem números) para ver se é o mesmo assunto
            contexto_fato = set(w for w in norm_fact if not w.isdigit())
            contexto_frag = set(w for w in _norm_words(combined) if not w.isdigit())
            overlap_contexto = len(contexto_fato & contexto_frag)
            
            # Se o assunto é muito similar (ex: "Console X lançado")
            if overlap_contexto >= 2: 
                numeros_frag = re.findall(r"\d+", combined)
                for n in numeros_no_fato:
                    # Se o fragmento fala do mesmo assunto mas com outro número de 4 dígitos (ano?)
                    if len(n) == 4 and any(len(nf) == 4 and nf != n for nf in numeros_frag):
                        # Conflito detectado. Se este fragmento for 'trusted', ele invalida o fato.
                        if trusted_flag:
                             print(f"🛑 CONFLITO CRÍTICO: Fonte confiável diz {numeros_frag} mas fato diz {n}")
                             conflito_detectado = True

        if len(fato_text) > 40 and fato_text.lower() in combined:
            sources.add(domain_or_url)
            source_trust[domain_or_url] = trusted_flag
            continue
        
        frag_words = set(_norm_words(combined)) - noise_words
        overlap = len(set(norm_fact) & frag_words)
        
        if overlap >= 6:
            sources.add(domain_or_url)
            source_trust[domain_or_url] = trusted_flag
            continue
            
        if "wikipedia.org" in (url or "").lower():
            wiki_title_words = set(_norm_words(title))
            if len(wiki_title_words & set(norm_fact)) >= 2:
                sources.add(domain_or_url)
                source_trust[domain_or_url] = True
                continue

    if not sources:
        return False, []
    
    if conflito_detectado:
        print(f"⚠️ Fato '{fato_text[:30]}' descartado por conflito de dados.")
        return False, []

    trusted_sources = [s for s in sources if source_trust.get(s)]
    any_trusted = len(trusted_sources) > 0
    fact_lower = fato_text.lower()
    
    if any_trusted and any(w in fact_lower for w in _norm_words(tema.lower())[:2]):
        return True, list(sources)

    entidade_norm = re.sub(r"\(.*\)", "", tema.lower()).strip()
    ent_words = [w for w in _norm_words(entidade_norm) if len(w) > 2]
    
    if not any_trusted:
        if ent_words:
            foco = ""
            for w in ent_words:
                if len(w) > len(foco):
                    foco = w
            if foco and foco not in fact_lower:
                return False, []

        match_count = 0
        for w in ent_words[:3]:
            if w in fact_lower:
                match_count += 1
        if match_count < 2:
            return False, []
        
    curiosity_keywords = ["secret", "hidden", "first", "original", "mistake", "design", "never", "only", "unique", "mystery", "bug", "glitch", "news"]
    if not any(kw in fact_lower for kw in curiosity_keywords) and not any_trusted:
         return False, []

    required = 1 if any_trusted else min_sources
    
    print(f"   DEBUG: Fact: {fato_text[:30]} | Sources: {len(sources)} | Trusted: {any_trusted} | Required: {required} | Sources: {sources}")

    if len(sources) >= required:
        return True, list(sources)
    return False, list(sources)

def gerar_resumo_factual(texto_bruto, tema, use_llm=True):
    """Extrai fatos confirmados a partir do texto de pesquisa.

    - Se use_llm=True: envia um prompt compacto ao LLM com fragmentos estruturados.
    - Se use_llm=False: executa extração heurística em código (mais rápida, sem LLM).

    Aplica verificação cruzada: cada fato precisa ser confirmado em pelo menos 2 fontes
    (configurável) para ser incluído no resultado final.
    """
    if not texto_bruto:
        print("❌ Texto bruto de pesquisa está vazio.")
        return None

    print(f"📝 Extraindo fatos para: {tema} (use_llm={use_llm})...")

    # Normaliza o input: se for string, mantemos; se for dict com 'fragments', usamos isso
    fragments = []
    if isinstance(texto_bruto, dict) and "fragments" in texto_bruto:
        fragments = texto_bruto["fragments"]
    elif isinstance(texto_bruto, list):
        fragments = texto_bruto
    else:
        # Texto longo: converte em um único fragmento para manter compatibilidade
        fragments = [
            {"title": tema, "content": str(texto_bruto), "url": "", "source": "raw"}
        ]

    # Heurística local (sem LLM) - usa spaCy NER quando disponível
    def _local_extract(frags, max_facts=8):
        keywords = [
            "born", "died", "discovered", "founded", "secret", "origin", "found", 
            "named", "first", "created", "launched", "revealed", "developed", 
            "original", "highest", "largest", "only", "unique", "patented"
        ]
        
        # Padrões de ruído de interface (BOILERPLATE)
        boilerplate = [
            "cookie", "privacidade", "termos de uso", "all rights reserved", 
            "inscreva-se", "login", "cadastre-se", "compartilhe", "siga-nos",
            "search", "navigation", "sidebar", "footer", "header", "clique aqui"
        ]

        seen = set()
        facts = []
        dados_chave = {"datas": [], "numeros": [], "locais": []}

        for f in frags:
            text = f.get("content") or ""
            
            # Limpeza NER básica
            ents = []
            if _nlp is not None:
                try:
                    doc = _nlp(text)
                    for ent in doc.ents:
                        ents.append((ent.text, ent.label_))
                        if ent.label_ in ("DATE", "TIME") and ent.text not in dados_chave["datas"]:
                            dados_chave["datas"].append(ent.text)
                        if ent.label_ in ("GPE", "LOC") and ent.text not in dados_chave["locais"]:
                            dados_chave["locais"].append(ent.text)
                        if ent.label_ in ("CARDINAL", "QUANTITY", "PERCENT", "MONEY") and ent.text not in dados_chave["numeros"]:
                            dados_chave["numeros"].append(ent.text)
                except Exception:
                    pass

            # quebra em frases simples
            sentences = re.split(r"[\.\n\r?!]+", text)
            for s in sentences:
                s_clean = s.strip()
                # Aumentamos o tamanho mínimo e filtramos boilerplate
                if not s_clean or len(s_clean) < 45:
                    continue
                
                lowered = s_clean.lower()
                if any(bp in lowered for bp in boilerplate):
                    continue

                score = 0
                for kw in keywords:
                    if kw in lowered:
                        score += 2
                
                # Bonus por números e anos
                if re.search(r"\d{4}", s_clean):
                    score += 2
                if re.search(r"\d+", s_clean):
                    score += 1
                
                if score >= 3: # Subimos a barra do score inicial
                    key = s_clean[:100].lower()
                    if key not in seen:
                        # confirma o fato contra fragments (cross-check)
                        confirmed, sources = confirmar_fato(
                            s_clean, fragments, tema=tema, min_sources=2
                        )
                        if confirmed:
                            facts.append({
                                "fato": s_clean,
                                "detalhe": "",
                                "fonte": f.get("url") or f.get("source") or "",
                                "confirmado_em": sources,
                            })
                            seen.add(key)
                            if len(facts) >= max_facts:
                                return facts, dados_chave
        return facts, dados_chave

    if not use_llm:
        fatos_locais, dados_chave = _local_extract(fragments, max_facts=8)
        dens = "alta" if len(fatos_locais) >= 2 else "baixa"
        if not fatos_locais:
            print("⚠️ Extração local não encontrou fatos suficientemente confirmados.")
            return None
        resultado = {
            "entidade": tema,
            "fatos": fatos_locais,
            "dados_chave": dados_chave,
            "densidade_factual": dens,
        }
        print(
            f"✅ Extração local obteve {len(fatos_locais)} fatos confirmados (densidade: {dens})."
        )
        return resultado

    # Se chegou aqui, vamos preparar um prompt compacto para o LLM
    max_frag = 10
    lista = []
    for i, f in enumerate(fragments[:max_frag], start=1):
        title = f.get("title", "")
        content = (f.get("content") or "").replace("\n", " ").strip()
        url = f.get("url") or f.get("source") or ""
        lista.append(f"[{i}] {title} | {content} | {url}")

    corpo = "\n".join(lista)

    prompt = f"""
Você é um auditor de fatos rigoroso e obsessivo com a veracidade.
Dos fragmentos abaixo, extraia fatos SURPREENDENTES e REAIS sobre "{tema}".

SUA PRIORIDADE É A VERACIDADE:
- Se houver informações conflitantes entre os fragmentos (ex: datas diferentes), cite o conflito.
- Apenas extraia fatos que você tenha ALTA CONFIANÇA de que são reais.
- Ignore boatos, rumores ou opiniões se não forem apresentados como fatos documentados.

REGRAS CRÍTICAS:
1. SEJA LITERAL: Não invente nada. Extraia apenas o que está no texto.
2. VERIFICAÇÃO DE TEMA: Se o fragmento não for sobre "{tema}", IGNORE-O completamente.
3. CITE A FONTE: Cada fato deve terminar com o número da fonte [1], [2], etc.
4. NÍVEL DE CONFIANÇA: Atribua uma nota de 0.0 a 1.0 para a veracidade de cada fato baseado na solidez da fonte.
5. FORMATO JSON:
{{
  "entidade": "{tema}",
  "fatos": [
    {{ 
      "fato": "Texto do fato extraído [Número da fonte]", 
      "detalhe": "Contexto curto do fato [Número da fonte]",
      "confianca": 0.95,
      "conflitos": "Nenhum" 
    }}
  ],
  "dados_chave": {{ "datas": [], "numeros": [], "locais": [] }}
}}

FRAGMENTOS:
{corpo}
"""

    try:
        print(f"📡 Enviando prompt ao LLM ({MODELO_LLM})...")
        resposta = ollama.chat(
            model=MODELO_LLM, 
            messages=[{"role": "user", "content": prompt}] ,
            options={"temperature": 0.2}
        )
        conteudo = resposta.get("message", {}).get("content", "").strip()
        print(f"📥 Resposta do LLM recebida (tamanho: {len(conteudo)})")
        
        # LIMPEZA ROBUSTA DE JSON
        json_match = re.search(r"(\{.*\})", conteudo, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            # Remove blocos de código markdown se o LLM incluiu
            json_str = re.sub(r"```json|```", "", json_str).strip()
            
            try:
                # Tenta o parse direto primeiro
                dados_llm = json.loads(json_str)
            except json.JSONDecodeError:
                # Tenta limpezas agressivas
                print("   ⚠️ Falha no parse JSON inicial, tentando limpeza agressiva...")
                # Remove vírgulas extras no final de listas/objetos
                json_str_clean = re.sub(r",\s*([\]\}])", r"\1", json_str)
                # Remove comentários de linha
                json_str_clean = re.sub(r"//.*", "", json_str_clean)
                
                try:
                    dados_llm = json.loads(json_str_clean)
                except:
                    # Se ainda falhar, tenta extração via regex para campos obrigatórios
                    print("   ⚠️ Falha total no parse JSON, tentando extração via regex...")
                    fatos_rx = re.findall(r'"fato":\s*"(.*?)",\s*"detalhe":\s*"(.*?)"', json_str)
                    fatos_list = []
                    for f_text, d_text in fatos_rx:
                        fatos_list.append({"fato": f_text, "detalhe": d_text})
                    
                    if not fatos_list:
                         # Tenta pegar fatos de um formato menos rígido
                         fatos_rx = re.findall(r'"fato":\s*"(.*?)"', json_str)
                         for f_text in fatos_rx:
                             fatos_list.append({"fato": f_text, "detalhe": ""})

                    dados_llm = {
                        "entidade": tema,
                        "fatos": fatos_list,
                        "dados_chave": {"datas": [], "numeros": [], "locais": []}
                    }
        else:
            # Se não achou chaves, tenta carregar a string inteira ou regex
            try:
                dados_llm = json.loads(conteudo)
            except:
                # Tenta regex direto no conteúdo bruto caso não tenha chaves
                fatos_rx = re.findall(r'"fato":\s*"(.*?)"', conteudo)
                if fatos_rx:
                    fatos_list = [{"fato": f, "detalhe": ""} for f in fatos_rx]
                    dados_llm = {"entidade": tema, "fatos": fatos_list, "dados_chave": {}}
                else:
                    print("   ⚠️ Resposta do LLM sem formato JSON reconhecido.")
                    return None

        # Verificação cruzada dos fatos retornados pelo LLM
        fatos_confirmados = []
        for f in dados_llm.get("fatos", []):
            texto_fato = f.get("fato") or ""
            confirmed, sources = confirmar_fato(texto_fato, fragments, tema=tema, min_sources=2)
            if confirmed:
                f["confirmado_em"] = sources
                fatos_confirmados.append(f)
            else:
                print(
                    f"⚠️ Fato descartado por falta de confirmação: {texto_fato[:140]}..."
                )

        if not fatos_confirmados:
            print("⚠️ Nenhum fato do LLM foi confirmado por múltiplas fontes.")
            return None

        resultado = {
            "entidade": dados_llm.get("entidade", tema),
            "fatos": fatos_confirmados,
            "dados_chave": dados_llm.get("dados_chave", {}),
            "densidade_factual": "alta" if len(fatos_confirmados) >= 2 else "baixa",
        }
        print(f"✅ LLM retornou {len(fatos_confirmados)} fatos confirmados.")
        return resultado
    except Exception as e:
        print(f"⚠️ Erro ao processar fatos com LLM: {e}")
        return None


def validar_densidade(fatos_json):
    """Verifica se o JSON de fatos tem qualidade suficiente para virar um vídeo."""
    if not fatos_json:
        print("❌ JSON de fatos inválido ou nulo.")
        return False

    densidade = fatos_json.get("densidade_factual", "baixa").lower()
    lista_fatos = fatos_json.get("fatos", [])

    if densidade == "baixa" and len(lista_fatos) < 2:
        print(
            f"❌ Densidade factual muito baixa ({densidade}) com apenas {len(lista_fatos)} fatos."
        )
        return False

    # Se tiver pelo menos 2 fatos, vamos aceitar para não travar o pipeline
    if len(lista_fatos) >= 2:
        print(
            f"✅ Tema validado com {len(lista_fatos)} fatos (Densidade: {densidade})."
        )
        return True

    print("❌ Falha na validação de densidade.")
    return False


if __name__ == "__main__":
    tema = "Voyager 1"
    bruto = pesquisar_dados_brutos(tema)
    fatos = gerar_resumo_factual(bruto, tema)
    if validar_densidade(fatos):
        print(json.dumps(fatos, indent=4, ensure_ascii=False))
