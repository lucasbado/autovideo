import os
import asyncio
import requests
import random
import math
import json
import re
import sys
import gc
import multiprocessing
import edge_tts
from faster_whisper import WhisperModel
import torch
import pysubs2
import subprocess
from duckduckgo_search import DDGS
import datetime
from tqdm import tqdm
import ollama

# Importações do MoviePy 2.0+
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
    concatenate_audioclips,
)

# Configurações iniciais
ARQUIVO_AUDIO = os.path.join("temp", "locucao_temp.mp3")
ARQUIVO_VIDEO_BASE = os.path.join("temp", "video_base.mp4")
ARQUIVO_FINAL = os.path.join("outputs", "resultado_tiktok.mp4")
MODELO_LLM = "deepseek-r1:8b"
MODELO_WHISPER = "small"  # 'small' libera VRAM para o LLM e é rápido na GPU
from config import PEXELS_API_KEY, TEMP_DIR, CURRENT_DATE
from knowledge_base_rag import buscar_conhecimento_local
from ollama_client import chat_safe, extract_json_from_text


async def gerar_audio(texto, voz="pt-BR-AntonioNeural"):
    print(f"🎙️ A gerar locução com a voz: {voz}...")
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(ARQUIVO_AUDIO)


async def gerar_roteiro_factual(fatos_json, nicho=None, alucinacoes_anteriores=None):
    """
    Gera um roteiro estritamente baseado nos fatos fornecidos, usando um Agente Especialista.
    (FILA DE MODELO para estabilidade)
    """
    from agents_config import obter_agente, GLOBAL_SAFETY_RULES, BANNED_PHRASES
    agente = obter_agente(nicho)

    # OS FATOS JÁ CHEGAM TRADUZIDOS DO RESEARCHER
    entidade = fatos_json.get("entidade", "Assunto")

    # --- TRUNCAMENTO DE FATOS PARA EVITAR CONTEXT OVERFLOW ---
    fatos_originais = fatos_json.get("fatos", [])
    max_fatos_no_prompt = 10  # Aumentado para 10 fatos para permitir vídeos de 1min+
    fatos_para_prompt = fatos_originais[:max_fatos_no_prompt]
    fatos_str = json.dumps(fatos_para_prompt, ensure_ascii=False, indent=2)
    
    # Adiciona instrução de reparo se houver alucinações
    repair_instruction = ""
    if alucinacoes_anteriores:
        repair_instruction = f"""
### ⚠️ ALERTA DE REPARO ⚠️
Sua tentativa anterior foi REPROVADA pela auditoria por conter informações inventadas (alucinações).
POR FAVOR, NÃO REPITA OS SEGUINTES ERROS:
{json.dumps(alucinacoes_anteriores, indent=2, ensure_ascii=False)}

Certifique-se de ser 100% fiel apenas aos fatos fornecidos abaixo.
"""

    # BUSCA EXEMPLOS DE ESTILO (RAG)
    print(f"🧠 Consultando exemplos de estilo no Vault...")
    exemplos_estilo = await buscar_conhecimento_local(f"roteiro sucesso {nicho or ''}", top_k=2)
    style_instruction = ""
    if exemplos_estilo:
        style_instruction = "\n### ESTRUTURA DE ESTILO - EXEMPLOS DE SUCESSO (IGNORE OS FATOS DOS EXEMPLOS):\n"
        style_instruction += "IMPORTANTE: Use os textos abaixo APENAS para aprender o ritmo, tom e transições. NÃO USE NENHUMA DATA, NOME OU DADO técnico presente nestes exemplos.\n"
        for i, ex in enumerate(exemplos_estilo):
            # Limpa o exemplo de tags de cena para focar no tom
            texto_ex = re.sub(r'\[SCENE:.*?\]', '', ex['text']).strip()
            style_instruction += f"Modelo de Ritmo {i+1}:\n{texto_ex[:500]}...\n\n"

    print(f"\n🧠 Agente Especialista ({agente['persona']}) gerando roteiro para: '{entidade}'")

    # PASSO 1: Gerar o texto bruto do roteiro com sistema de RETRY para tags
    tentativa_roteiro = 0
    max_tentativas_roteiro = 3
    roteiro_final_texto = ""
    roteiro_bruto = ""
    failure_reason = ""
    
    while tentativa_roteiro < max_tentativas_roteiro:
        tentativa_roteiro += 1
        
        extra_instruction = ""
        if tentativa_roteiro > 1:
            reason_text = failure_reason or "não seguiu o formato"
            print(f"⚠️ Tentativa {tentativa_roteiro}: Roteiro anterior falhou ({reason_text}). Enviando prompt limpo com reforço.")
            extra_instruction = f"\nINSTRUÇÃO ADICIONAL: Sua resposta deve ser EXTREMAMENTE concisa e seguir a estrutura de parágrafos e frases pedida. Não inclua texto extra nem explicações."

        prompt_texto = f"""
Você é um {agente['persona']} especializado em {agente['expertise']}. Seu tom é {agente['tom']}.
Data Atual: {CURRENT_DATE}.

### INSTRUÇÃO DE SEGURANÇA CRÍTICA:
Você é um sistema de transcrição DOCUMENTAL TÉCNICA. 
1. Se uma informação não está no JSON abaixo, ela NÃO EXISTE. 
2. Ignore TOTALMENTE seu conhecimento prévio sobre o tema. 

### REGRAS DE NARRATIVA DOCUMENTAL:
- IMPACTO DIRETO: Comece o roteiro DIRETAMENTE com o fato mais impactante ou a data inicial.
- CONECTIVIDADE ÉPICA: Não liste fatos. Crie uma teia narrativa. Use advérbios de escala (colossal, ínfimo, devastador, milimétrico).
- DESFECHO OBRIGATÓRIO: O último parágrafo deve ser uma conclusão ÉPICA sobre o impacto futuro ou o mistério que resta. NÃO repita os fatos iniciais; sintetize a importância.
- SEM FONTES: Jamais inclua URLs, nomes de sites ou referências tipo "Fonte: ..." dentro do roteiro.
- META: Escreva um texto denso para bater aproximadamente 1 minuto de vídeo (200-250 palavras).

### REGRAS DE CONSISTÊNCIA FACTUAL (CRÍTICO):
1. Use APENAS os fatos do JSON. 
2. Se o JSON não fala de um detalhe específico, você NÃO PODE citá-lo.
3. Mantenha-se 100% fiel à verdade contida no arquivo.

{style_instruction}

{repair_instruction}

OBJETIVO: Escrever um roteiro de documentário técnico em PORTUGUÊS DO BRASIL baseado UNICAMENTE nos FATOS fornecidos.

DADOS OBRIGATÓRIOS:
TEMA: {entidade}
FATOS: {fatos_str}

REGRAS DE FORMATAÇÃO:
1. Escreva de 4 a 6 parágrafos densos (máximo de 4 frases cada).
2. Intercale o texto com tags de cena genéricas em inglês. Exemplo: [SCENE: deep space view].
3. O roteiro deve estar contido EXCLUSIVAMENTE dentro das tags <script> e </script>.
"""

        try:
            print(f"🧠 Enviando prompt ao {MODELO_LLM} (Modo Narrativo 3.4 - Tentativa {tentativa_roteiro})...")
            
            res_texto = await chat_safe(
                model=MODELO_LLM, 
                messages=[{"role": "user", "content": prompt_texto}],
                options={
                    "temperature": 0.5, 
                    "num_predict": 2048, 
                    "num_ctx": 8192,
                    "num_gpu": 99
                } 
            )
            
            if not res_texto: return None, None
            
            conteudo_bruto = res_texto["message"]["content"].strip()
            
            # Limpeza DeepSeek (Think blocks já tratados no chat_safe se usarmos extract_json, mas aqui é texto livre)
            conteudo_bruto = re.sub(r"<think>.*?</think>", "", conteudo_bruto, flags=re.DOTALL).strip()

            # Extração
            roteiro_bruto = ""
            script_match = re.search(r"<script>(.*?)</script>", conteudo_bruto, re.DOTALL)
            if script_match:
                roteiro_bruto = script_match.group(1).strip()
            elif "**Script**" in conteudo_bruto:
                roteiro_bruto = conteudo_bruto.split("**Script**")[-1].strip()
            elif "Script:" in conteudo_bruto:
                roteiro_bruto = conteudo_bruto.split("Script:")[-1].strip()
            elif "ETAPA 2" in conteudo_bruto:
                roteiro_bruto = conteudo_bruto.split("ETAPA 2")[-1].strip()
            else:
                # Se não achou nenhum marcador, remove as partes que parecem listas de fatos ou tags
                # e tenta pegar apenas o maior bloco de texto que não contenha tags conhecidas
                temp = re.sub(r"<fatos_selecionados>.*?</fatos_selecionados>", "", conteudo_bruto, flags=re.DOTALL).strip()
                temp = re.sub(r"\*\*Fatos Selecionados:\*\*.*?\n\n", "", temp, flags=re.DOTALL).strip()
                roteiro_bruto = temp

            # --- VALIDAÇÃO DE IDIOMA (Anti-Chinês/Outros) ---
            # Regex para detectar caracteres CJK (Chinês, Japonês, Coreano)
            if re.search(r'[\u4e00-\u9fff]+', roteiro_bruto):
                failure_reason = "gerou texto em idioma incorreto (chinês detectado)"
                print(f"⚠️ Tentativa {tentativa_roteiro} falhou: Roteiro gerado é inválido ({failure_reason}).")
                if tentativa_roteiro < max_tentativas_roteiro:
                    continue
                else:
                    print("❌ Falha crítica: Modelo continuou a gerar em idioma incorreto.")
                    roteiro_final_texto = ""
                    break # Sai do loop de tentativas

            # VALIDAÇÃO DE TAGS (Obrigatório [ ])
            if "[" not in roteiro_bruto or "]" not in roteiro_bruto:
                if tentativa_roteiro < max_tentativas_roteiro:
                    failure_reason = "ausência de tags [SCENE]"
                    continue
                else:
                    print("❌ Falha crítica: Modelo se recusa a incluir tags visuais.")
                    return None, None # RETORNA NULO PARA FORÇAR RETRY OU REPARO

            # --- FILTRO DE METALINGUAGEM (Anti-Explicação da IA) ---
            meta_talk_patterns = [
                r"Vou estruturar minha resposta.*?\.",
                r"Baseado apenas nas informações verificadas.*?\.",
                r"Em resumo, preciso explicar.*?\.",
                r"Minha missão é criar.*?\.",
                r"Aqui está o roteiro.*?:",
                r"Vou destacar esses pontos principais.*?\.",
                r"Mantendo-me factual.*?\.",
                r"Entendido, vou criar.*?\.",
                r"Aqui está uma narração.*?\."
            ]
            for mp in meta_talk_patterns:
                roteiro_bruto = re.sub(mp, "", roteiro_bruto, flags=re.IGNORECASE | re.DOTALL).strip()

            # --- FILTRO DE CLICHÊS (Banned Phrases) ---
            for phrase in BANNED_PHRASES:
                # Escapa a frase para usar em regex e remove com bordas de palavra ou pontuação
                pattern = rf"\b{re.escape(phrase)}[!\?\.]?"
                roteiro_bruto = re.sub(pattern, "", roteiro_bruto, flags=re.IGNORECASE).strip()

            # 1. Remove marcas de tempo e introduções típicas
            roteiro_bruto = re.sub(r"\(\d+-\d+s\)", "", roteiro_bruto)
            roteiro_bruto = re.sub(r"\(Hook.*?\)", "", roteiro_bruto, flags=re.IGNORECASE)
            roteiro_bruto = re.sub(r"\(CTA.*?\)", "", roteiro_bruto, flags=re.IGNORECASE)
            roteiro_bruto = re.sub(r"\(Gancho.*?\)", "", roteiro_bruto, flags=re.IGNORECASE)

            # 3. Remove marcas de roteiro e markdown
            roteiro_limpo = re.sub(r"\*\*.*?\*\*", "", roteiro_bruto) 
            roteiro_limpo = re.sub(r"(HOOK|GANCHO|REVELAÇÃO|MEAT|DETALHES|LOOP|CTA|DESFECHO|CONCLUSÃO|NARRADOR|CENA|VISUAL|ETAPA \d|ROTEIRO FINAL):?", "", roteiro_limpo, flags=re.IGNORECASE)
            
            # --- FILTRO DE SEGURANÇA FINAL (Anti-Lixo) ---
            bad_words = ["pornô", "p0rn", "vulg", "sacana", "desgraça", "burrice", "detonar"]
            for bw in bad_words:
                roteiro_limpo = re.sub(rf"\b{bw}\w*\b", "", roteiro_limpo, flags=re.IGNORECASE)
            
            # Remove números de fontes [1] (caso tenham sobrado fora de colchetes)
            roteiro_limpo = re.sub(r"\s*\[\d+\]\s*", " ", roteiro_limpo)

            # Remove repetições de palavras (ex: "palavra palavra palavra")
            roteiro_limpo = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", roteiro_limpo, flags=re.IGNORECASE)

            # 4. Normalização de texto
            roteiro_limpo = re.sub(r"\n+", " ", roteiro_limpo)
            roteiro_limpo = re.sub(r"\s+", " ", roteiro_limpo).strip()
            
            # --- LIMPEZA DE CABEÇALHOS DE IA (Fonte, Script, etc) ---
            roteiro_limpo = re.sub(r"^(Fonte|Source|Script|Roteiro|Narrador|Cena).*?:\s*", "", roteiro_limpo, flags=re.IGNORECASE)
            
            roteiro_final_texto = roteiro_limpo

            # --- VALIDAÇÃO DE IDIOMA (Anti-Inglês/Anti-Lixo) ---
            common_english = [" the ", " of ", " and ", " is ", " for ", " with ", " that ", " this "]
            english_word_count = sum(1 for word in common_english if word in f" {roteiro_limpo.lower()} ")
            
            if english_word_count >= 3:
                failure_reason = f"detectado idioma incorreto (Inglês detectado: {english_word_count} palavras comuns)"
                print(f"⚠️ Tentativa {tentativa_roteiro} falhou: {failure_reason}")
                if tentativa_roteiro < max_tentativas_roteiro:
                    continue
                else:
                    print("❌ Falha crítica: Modelo persistiu em gerar conteúdo em inglês.")
                    roteiro_final_texto = ""
                    break

            # --- VALIDAÇÃO DE CONTEÚDO E TAMANHO ---
            word_count = len(roteiro_final_texto.split())
            max_words = 400  # O prompt pede 200-250, 400 é um limite generoso.
            forbidden_keywords = ["assistente de ia", "the villain", "catastrophic event", "human:", "aegis da terra"]
            
            is_too_long = word_count > max_words
            has_forbidden_words = any(kw in roteiro_final_texto.lower() for kw in forbidden_keywords)

            if is_too_long or has_forbidden_words:
                failure_reason = f"muito longo ({word_count} palavras)" if is_too_long else f"contém keywords proibidas"
                print(f"⚠️ Tentativa {tentativa_roteiro} falhou: Roteiro gerado é inválido ({failure_reason}).")
                print(f"   --- CONTEÚDO REPROVADO ---\n{roteiro_final_texto[:1000]}...\n   -------------------------") # Mostra o início do roteiro inválido
                if tentativa_roteiro < max_tentativas_roteiro:
                    continue  # Tenta novamente
                else:
                    print("❌ Falha crítica: Modelo continuou a gerar roteiros inválidos.")
                    roteiro_final_texto = ""  # Garante que vai falhar fora do loop

            break # Sucesso
            
        except Exception as e:
            print(f"❌ Erro na tentativa {tentativa_roteiro}: {e}")

    if not roteiro_final_texto:
        return None, None

    # PASSO 2: Gerar Metadados
    print(f"🤖 Gerando metadados e termos de busca visual (via phi4-mini)...")

    prompt_json = f"""
    Com base no ROTEIRO abaixo, gere um JSON para automação visual.
    
    ROTEIRO:
    {roteiro_final_texto}
    
    MISSÃO: Gerar uma lista de 6 a 8 termos de busca visual (visual_search_terms) em INGLÊS.
    
    REGRAS DE CURADORIA VISUAL:
    1. OBJETOS CONCRETOS: Não use termos abstratos como "survival", "secret", "history", "discovery" ou "mystery".
    2. ANALOGIAS CIENTÍFICAS: Se o tema for microscópico ou raro, use termos relacionados: "microscope", "bacteria animation", "laboratory", "dna", "deep space", "astronomy", "cinematic nature".
    3. DIVERSIDADE: Varie os termos para não repetir o mesmo visual o vídeo todo.
    4. IDIOMA: Os termos DEVEM ser em inglês.
    
    ESTRUTURA OBRIGATÓRIA:
    {{
      "titulo": "Título Curto",
      "visual_search_terms": ["term 1", "term 2", "term 3", "term 4", "term 5", "term 6"],
      "hashtags": ["#tag1", "#tag2"]
    }}
    """

    try:
        # Usando phi4-mini para metadados (Fila Segura)
        resposta = await chat_safe(
            model="phi4-mini", 
            messages=[{"role": "user", "content": prompt_json}],
            options={
                "temperature": 0.1,
                "num_gpu": 99,
                "num_thread": 4
            },
            format="json"
        )
        
        if not resposta:
            return roteiro_final_texto, [f"{entidade} cinematic"]
            
        dados_ia = extract_json_from_text(resposta["message"]["content"])
        
        if not dados_ia or "visual_search_terms" not in dados_ia:
            print("   ⚠️ Falha no parse JSON de metadados, usando fallback...")
            return roteiro_final_texto, [f"{entidade} cinematic", "science", "documentary"]

        termos_busca = dados_ia.get("visual_search_terms", [f"{entidade} cinematic"])
        print(f"✅ Curadoria Visual pronta. Termos: {', '.join(termos_busca)}")
        
        # Garante que não há marcas de roteiro no texto final
        final_script = roteiro_bruto.strip()
        if not final_script.endswith("."):
            final_script += "."
            
        return final_script, termos_busca

    except Exception as e:
        print(f"⚠️ Erro ao formatar metadados: {e}")
        return roteiro_final_texto, [f"{entidade} cinematic"]


def obter_url_pexels(termos_lista):
    """
    Realiza múltiplas buscas no Pexels e mescla os resultados para maior variedade.
    """
    if not isinstance(termos_lista, list):
        termos_lista = [str(termos_lista)]

    print(f"🔍 Curadoria Visual: Pesquisando {len(termos_lista)} termos no Pexels...")
    headers = {"Authorization": PEXELS_API_KEY}
    links_finais = []

    # Faz uma busca pequena para cada termo para garantir diversidade
    for termo in termos_lista[:8]: # Limite de 8 buscas por vídeo
        try:
            # Pega apenas 2-3 vídeos por termo
            url = f"https://api.pexels.com/videos/search?query={termo}&orientation=portrait&size=medium&per_page=3"
            resposta = requests.get(url, headers=headers, timeout=10)
            resposta.raise_for_status()
            dados = resposta.json()

            for video in dados.get("videos", []):
                v_files = video.get("video_files", [])
                # Prioriza HD mp4
                link = v_files[0]["link"]
                for f in v_files:
                    if f.get("quality") == "hd" and f.get("file_type") == "video/mp4":
                        link = f["link"]
                        break
                if link not in links_finais:
                    links_finais.append(link)
        except Exception as e:
            print(f"   ⚠️ Falha ao buscar termo '{termo}': {e}")
            continue

    # Se não achou nada, usa o fallback clássico
    if not links_finais:
        print("   ⚠️ Nenhum vídeo encontrado nos termos da IA. Usando fallback...")
        return ["https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"]

    # Embaralha para que a sequência não seja previsível
    random.shuffle(links_finais)
    
    # Limita a 12 vídeos totais (suficiente para 1min+)
    return links_finais[:12]


async def descarregar_videos(urls, dest_dir=TEMP_DIR, max_concurrency=3, retries=3):
    import aiohttp
    import aiofiles
    import asyncio

    print(f"📥 A descarregar {len(urls)} vídeos de fundo (async)...")
    os.makedirs(dest_dir, exist_ok=True)

    sem = asyncio.Semaphore(max_concurrency)

    async def fetch(i, url):
        nome_arquivo = os.path.join(dest_dir, f"video_base_{i}.mp4")
        attempt = 0
        while attempt < retries:
            try:
                async with sem:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    async with aiohttp.ClientSession(headers=headers) as session:
                        async with session.get(url) as resp:
                            resp.raise_for_status()
                            async with aiofiles.open(nome_arquivo, "wb") as f:
                                async for chunk in resp.content.iter_chunked(1024):
                                    await f.write(chunk)
                print(f"✅ Download concluído: {nome_arquivo}")
                return nome_arquivo
            except Exception as e:
                attempt += 1
                wait = 2**attempt
                print(f"⚠️ Erro ao baixar {url}: {e}. Tentativa {attempt}/{retries}. Aguardando {wait}s")
                await asyncio.sleep(wait)
        print(f"❌ Falha ao baixar {url} após {retries} tentativas.")
        return None

    tasks = [asyncio.create_task(fetch(i, url)) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks)

    arquivos = [r for r in results if r]

    if not arquivos:
        return ["https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"]

    return arquivos


def gerar_legendas():
    print("✍️ A transcrever áudio com Faster-Whisper (GPU)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Otimizado para VRAM: int8 em CPU ou float16 em GPU
    compute_type = "float16" if device == "cuda" else "int8"
    
    model = WhisperModel(MODELO_WHISPER, device=device, compute_type=compute_type)
    
    segments, info = model.transcribe(
        ARQUIVO_AUDIO, 
        beam_size=5, 
        word_timestamps=True,
        language="pt"
    )
    
    # Converte o gerador em lista para processamento
    word_level_segments = []
    for segment in segments:
        for word in segment.words:
            word_level_segments.append({
                "start": word.start,
                "end": word.end,
                "text": word.word.strip().upper()
            })
    
    # Limpeza de VRAM e memória para a renderização
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
            
    return word_level_segments


def criar_arquivo_ass(segmentos, output_path, estilo):
    """
    Gera um arquivo de legendas .ass altamente estilizado para queima via FFmpeg.
    """
    subs = pysubs2.SSAFile()
    subs.info["PlayResX"] = 1080
    subs.info["PlayResY"] = 1920
    
    # Configuração do Estilo
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return 255, 255, 255

    r1, g1, b1 = hex_to_rgb(estilo.get("cor_legenda", "#FFFFFF"))
    r2, g2, b2 = hex_to_rgb(estilo.get("stroke_color", "#000000"))
    
    # Cria o estilo customizado
    style = pysubs2.SSAStyle()
    style.fontname = "Arial Black" # Fonte padrão robusta
    style.fontsize = estilo.get("font_size", 75)
    style.primarycolor = pysubs2.Color(r=r1, g=g1, b=b1)
    style.outlinecolor = pysubs2.Color(r=r2, g=g2, b=b2)
    style.outline = 3
    style.shadow = 1
    style.alignment = 2 # Centralizado embaixo
    style.marginv = int(1920 * (1 - estilo.get("posicao_y", 0.7))) # Margem vertical reversa
    
    subs.styles["Default"] = style

    # Adiciona os eventos (legendas)
    for s in segmentos:
        event = pysubs2.SSAEvent(
            start=pysubs2.make_time(s=s["start"]),
            end=pysubs2.make_time(s=s["end"]),
            text=s["text"]
        )
        subs.append(event)
    
    subs.save(output_path)
    return output_path


def montar_video(segmentos_legenda, arquivos_video, estilo=None):
    if estilo is None:
        from styles import ESTILOS
        estilo = ESTILOS["default"]

    print(f"🎬 A montar o vídeo Turbo (Aceleração GPU)...")
    audio = AudioFileClip(ARQUIVO_AUDIO)
    duracao_final = audio.duration

    clips_de_fundo = [VideoFileClip(f).without_audio().with_fps(30) for f in arquivos_video]
    cenas_finais = []

    tempo_atual = 0
    i = 0
    while tempo_atual < duracao_final:
        duracao_cena = random.uniform(4, 6)
        if tempo_atual + duracao_cena > duracao_final:
            duracao_cena = duracao_final - tempo_atual

        video_escolhido = clips_de_fundo[i % len(clips_de_fundo)]
        i += 1

        if video_escolhido.duration < duracao_cena:
            n_loops = math.ceil(duracao_cena / video_escolhido.duration)
            video_temp = concatenate_videoclips([video_escolhido] * n_loops)
            cena = video_temp.subclipped(0, duracao_cena)
        else:
            inicio_maximo = max(0, video_escolhido.duration - duracao_cena - 0.1)
            inicio_aleatorio = random.uniform(0, inicio_maximo)
            cena = video_escolhido.subclipped(inicio_aleatorio, inicio_aleatorio + duracao_cena)

        # REDIMENSIONAMENTO INTELIGENTE 9:16
        ratio_original = cena.w / cena.h
        ratio_alvo = 1080 / 1920
        if ratio_original > ratio_alvo:
            cena = cena.resized(height=1920)
        else:
            cena = cena.resized(width=1080)

        cena = cena.cropped(x_center=int(cena.w / 2), y_center=int(cena.h / 2), width=1080, height=1920)
        cenas_finais.append(cena.with_start(tempo_atual))
        tempo_atual += duracao_cena

    video_base = CompositeVideoClip(cenas_finais, size=(1080, 1920)).with_audio(audio)

    # Filtro Visual (Tint) por Nicho
    tint_layer = None
    if estilo.get("visual_tint"):
        print(f"🎨 Aplicando filtro visual do nicho: {estilo.get('handle')}")
        tint_layer = (
            ColorClip(size=(1080, 1920), color=estilo["visual_tint"])
            .with_opacity(estilo.get("tint_opacity", 0.05))
            .with_duration(duracao_final)
        )

    # Marca d'água (A única coisa que o MoviePy vai renderizar agora)
    handle_text = estilo.get("handle", "@Fatos").upper()
    # Se o perfil estiver no metadado do arquivo (passado via estilo ou manual), usa ele
    if estilo.get("perfil_padrao"):
        handle_text = f"@{estilo['perfil_padrao']}".upper()

    watermark = (
        TextClip(
            text=handle_text,
            font=estilo["font"],
            font_size=35,
            color="white",
            method="caption",
            size=(400, None),
            text_align="center",
        )
        .with_opacity(0.4)
        .with_position(("right", 20))
        .with_duration(duracao_final)
    )

    layers = [video_base]
    if tint_layer: layers.append(tint_layer)
    layers.append(watermark)

    video_com_watermark = CompositeVideoClip(layers)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_output = os.path.join("temp", f"raw_video_{timestamp}.mp4")
    nome_final = os.path.join("outputs", f"video_{timestamp}.mp4")

    # 1. Renderiza o vídeo base sem legendas (Rápido com NVENC)
    print(f"⏳ Fase 1: Renderizando vídeo base...")
    n_cores = multiprocessing.cpu_count()
    video_com_watermark.write_videofile(
        temp_output, 
        fps=30, 
        codec="h264_nvenc", 
        audio_codec="aac", 
        threads=n_cores,
        logger='bar'
    )

    # 2. Gera arquivo ASS
    ass_path = os.path.join("temp", "legendas.ass")
    criar_arquivo_ass(segmentos_legenda, ass_path, estilo)

    # 3. Queima legendas via FFmpeg (Instantâneo)
    print(f"⚡ Fase 2: Queimando legendas via FFmpeg...")
    # Escapa o caminho para o FFmpeg no Windows
    ass_path_ffmpeg = ass_path.replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_output,
        "-vf", f"subtitles='{ass_path_ffmpeg}'",
        "-c:v", "h264_nvenc",
        "-preset", "p1", # Preset de ultra velocidade
        "-c:a", "copy",  # Copia o áudio sem re-encodificar
        nome_final
    ]
    
    subprocess.run(cmd, check=True)
    print(f"✅ Fase 2 concluída: Vídeo final gerado.")

    audio.close()
    for v in clips_de_fundo:
        v.close()
    video_com_watermark.close()

    return nome_final


def limpar_roteiro_para_audio(texto):
    """
    Remove tags de título, marcas de cena e pontuação órfã para garantir um áudio limpo.
    """
    if not texto: return ""
    
    # 1. Remove tags [TITLE: ...] e [SCENE: ...]
    texto_limpo = re.sub(r'\[TITLE:.*?\]', '', texto, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'\[SCENE:.*?\]', '', texto_limpo, flags=re.IGNORECASE)
    
    # 2. Remove cabeçalhos de IA comuns no início
    texto_limpo = re.sub(r'^(Fonte|Source|Script|Roteiro|Narrador|Cena|Hook|Introdução).*?:\s*', '', texto_limpo, flags=re.IGNORECASE | re.MULTILINE)
    
    # 3. Limpa pontuação órfã no início de frases/parágrafos (ex: ", as tardígradas")
    texto_limpo = re.sub(r'(^|[\.\?\!])\s*[,;:]\s*', r'\1 ', texto_limpo)
    
    # 4. Remove múltiplos espaços e novas linhas excessivas
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
    
    return texto_limpo

async def main(tema_externo=None):
    from researcher import pesquisar_dados_brutos, gerar_resumo_factual, validar_densidade
    import ideator_new as ideator

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    if tema_externo:
        if isinstance(tema_externo, dict):
            tema_obj = tema_externo
        else:
            tema_obj = {"title": str(tema_externo), "keywords": []}
    else:
        tema_obj = ideator.gerar_tema_factual()

    tema_title = tema_obj.get("title")
    tema_keywords = tema_obj.get("keywords")

    print(f"🚀 Iniciando geração automatizada para o tema: '{tema_title}' | keywords: {tema_keywords}")

    bruto = await pesquisar_dados_brutos(tema_title, keywords=tema_keywords)
    fatos = await gerar_resumo_factual(bruto, tema_title, use_llm=False)

    if not fatos:
        print("ℹ️ Extração local insuficiente. Tentando LLM para resumo factual...")
        fatos = await gerar_resumo_factual(bruto, tema_title, use_llm=True)

    if not validar_densidade(fatos):
        print("❌ Fatos insuficientes. Encerrando.")
        return

    roteiro, termo_busca = await gerar_roteiro_factual(fatos)

    if not roteiro:
        return

    urls_video = obter_url_pexels(termo_busca)
    arquivos_video = await descarregar_videos(urls_video)

    from styles import obter_estilo
    estilo = obter_estilo(tema_externo if tema_externo else "default")

    await gerar_audio(roteiro, voz=estilo["voz"])
    segmentos = gerar_legendas()

    arquivo_resultado = montar_video(segmentos, arquivos_video, estilo=estilo)

    print("🧹 Limpando arquivos temporários...")
    for arq in os.listdir("temp"):
        caminho = os.path.join("temp", arq)
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
        except Exception as e:
            print(f"⚠️ Erro ao limpar {arq}: {e}")

    print(f"🚀 Sucesso absoluto! O vídeo completo está em: {arquivo_resultado}")


if __name__ == "__main__":
    asyncio.run(main())
