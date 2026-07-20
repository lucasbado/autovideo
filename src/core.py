import os
import asyncio
import requests
import random
import math
import json
import re
import sys
import edge_tts
import whisper
import torch
from duckduckgo_search import DDGS
import datetime
from tqdm import tqdm
import ollama

# Importações do MoviePy 2.0+
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
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

from config import PEXELS_API_KEY, TEMP_DIR


async def gerar_audio(texto, voz="pt-BR-AntonioNeural"):
    print(f"🎙️ A gerar locução com a voz: {voz}...")
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(ARQUIVO_AUDIO)


def gerar_roteiro_factual(fatos_json, nicho=None):
    """
    Gera um roteiro estritamente baseado nos fatos fornecidos, usando um Agente Especialista.
    """
    from agents_config import obter_agente, GLOBAL_SAFETY_RULES, BANNED_PHRASES
    agente = obter_agente(nicho)

    entidade = fatos_json.get("entidade", "Assunto")
    fatos_str = json.dumps(fatos_json.get("fatos", []), ensure_ascii=False, indent=2)
    dados_chave = json.dumps(fatos_json.get("dados_chave", {}), ensure_ascii=False)

    print(f"\n🧠 Agente Especialista ({agente['persona']}) gerando roteiro para: '{entidade}'")

    # PASSO 1: Gerar o texto bruto do roteiro com sistema de RETRY para tags
    tentativa_roteiro = 0
    max_tentativas_roteiro = 3
    roteiro_final_texto = ""
    
    while tentativa_roteiro < max_tentativas_roteiro:
        tentativa_roteiro += 1
        
        extra_instruction = ""
        if tentativa_roteiro > 1:
            print(f"⚠️ Tentativa {tentativa_roteiro}: Roteiro anterior sem tags [SCENE]. Exigindo formato...")
            extra_instruction = "\nATENÇÃO: Você ESQUECEU das tags [SCENE: ...] no último texto. Se não incluir as tags agora, seu output será DELETADO."

        prompt_texto = f"""
{GLOBAL_SAFETY_RULES}
{extra_instruction}

Você é um {agente['persona']}. 
Sua especialidade é {agente['expertise']}.
Seu tom de voz deve ser {agente['tom']}.

OBJETIVO: Criar uma NARRAÇÃO CINEMATOGRÁFICA de MAIS DE 60 SEGUNDOS em PORTUGUÊS DO BRASIL.
O roteiro deve ser um DOCUMENTÁRIO TÉCNICO E SÉRIO. 

--- 
### DADOS REAIS DO TEMA (FONTE ÚNICA DE VERDADE)
TEMA: {entidade}
FATOS VERIFICADOS (Use APENAS o que está aqui): 
{fatos_str}

DADOS CHAVE: {dados_chave}
---

### REGRAS DE OURO (TOLERÂNCIA ZERO PARA FALHAS):
1. **ÂNCORA TEMPORAL**: PROIBIDO inventar anos. Se a pesquisa diz "Anos 90", não diga "Hoje em 2014".
2. **DURAÇÃO (200-250 PALAVRAS)**: Expanda a narração explicando o "COMO" e o "PORQUÊ" técnico.
3. **FORMATO OBRIGATÓRIO**: Intercale a fala com tags de cena: [SCENE: descrição do visual].
4. **PROIBIÇÃO DE CLICHÊS**: É TERMINANTEMENTE PROIBIDO usar: {", ".join(BANNED_PHRASES[:15])}.
5. **VERIFICAÇÃO BIOLÓGICA**: Tardígrados são MULTICELULARES. Eles não foram recuperados da Lua.
6. **GROUNDING ABSOLUTO**: Se um detalhe não está nos fatos, ele NÃO PODE estar no roteiro. Não adicione "colorido", "emocionante", ou detalhes específicos de ações se não forem citados.

### ESTRUTURA OBRIGATÓRIA DA RESPOSTA:

Sua resposta deve ter EXATAMENTE este formato:

<think>
[Análise técnica. Verifique se tardígrados são unicelulares ou se foram resgatados da Lua (spoiler: não).
Planeje a inserção de pelo menos 6 tags [SCENE: ...] ao longo do texto.]
</think>

<fatos_selecionados>
[Números dos fatos usados]
</fatos_selecionados>

<script>
[SCENE: ...]
[Frase 1 de impacto baseada no fato real mais obscuro].
[Frase 2 detalhando o funcionamento técnico].
[SCENE: ...]
...
[Frase final técnica ou reflexiva].
</script>

### ALERTAS DE ALUCINAÇÃO (NUNCA FAÇA):
- NÃO invente armas (revólveres, bombas, pistolas) se não citadas nos fatos.
- NÃO invente perigo de morte imediata (vácuo letal, explosões) se não citado.
- NÃO confunda "Parachutes" (Paraquedas) com "Screws" (Parafusos).
- NÃO use o termo "consola" (Portugal), use "console" (Brasil).
- NÃO adicione diálogos ou cenas de ação fictícias para preencher tempo.
- SE O FATO NÃO ESTÁ NA LISTA, ELE NÃO EXISTE PARA ESTE ROTEIRO.
"""

        try:
            print(f"🧠 Enviando prompt ao {MODELO_LLM} (Tentativa {tentativa_roteiro})...")
            res_texto = ollama.chat(
                model=MODELO_LLM, 
                messages=[{"role": "user", "content": prompt_texto}],
                options={"temperature": 0.3}
            )
            conteudo_bruto = res_texto["message"]["content"].strip()
            
            # Limpeza DeepSeek
            conteudo_bruto = re.sub(r"<think>.*?</think>", "", conteudo_bruto, flags=re.DOTALL).strip()

            # Extração
            if "<script>" in conteudo_bruto:
                roteiro_bruto = re.search(r"<script>(.*?)</script>", conteudo_bruto, re.DOTALL).group(1).strip()
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

            # VALIDAÇÃO DE TAGS (Obrigatório [ ])
            if "[" not in roteiro_bruto or "]" not in roteiro_bruto:
                if tentativa_roteiro < max_tentativas_roteiro:
                    continue
                else:
                    print("❌ Falha crítica: Modelo se recusa a incluir tags visuais.")

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
            
            roteiro_final_texto = roteiro_limpo
            break # Sucesso
            
        except Exception as e:
            print(f"❌ Erro na tentativa {tentativa_roteiro}: {e}")

    if not roteiro_final_texto:
        return None, None

    # PASSO 2: Gerar Metadados
    print(f"🤖 Gerando metadados e termos de busca visual (via phi4-mini)...")

    prompt_json = f"""
    Com base no ROTEIRO abaixo, gere um JSON para automação.
    O 'visual_search' deve ser um termo em inglês que represente fielmente a entidade {entidade}.
    
    ROTEIRO:
    {roteiro_final_texto}
    
    ESTRUTURA:
    {{
      "titulo": "Título Factual",
      "descricao": "...",
      "visual_search": "termo em ingles para pexels",
      "hashtags": ["#curiosidade", "#historia", "#fato"]
    }}
    """

    try:
        # Usando phi4-mini para metadados por ser mais rápido e estável para JSON simples
        resposta = ollama.chat(
            model="phi4-mini", 
            messages=[{"role": "user", "content": prompt_json}],
            options={"temperature": 0.1}
        )
        resposta_texto = resposta["message"]["content"].strip()
        print(f"✅ Metadados processados.")
        
        json_match = re.search(r"\{.*\}", resposta_texto, re.DOTALL)
        if json_match:
            dados_ia = json.loads(json_match.group())
        else:
            dados_ia = json.loads(resposta_texto)

        termo_busca = dados_ia.get("visual_search", f"{entidade} cinematic")
        
        # Garante que não há marcas de roteiro no texto final
        final_script = roteiro_bruto.strip()
        if not final_script.endswith("."):
            final_script += "."
            
        return final_script, termo_busca
    except Exception as e:
        print(f"⚠️ Erro ao formatar metadados: {e}")
        return roteiro_final_texto, f"{entidade} cinematic"


def obter_url_pexels(termo_ingles):
    print(f"🔍 A procurar múltiplos vídeos no Pexels para: '{termo_ingles}'...")
    url = f"https://api.pexels.com/videos/search?query={termo_ingles}&orientation=portrait&size=medium&per_page=5"
    headers = {"Authorization": PEXELS_API_KEY}

    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        dados = resposta.json()

        if not dados.get("videos"):
            return ["https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"]

        links = []
        for video in dados["videos"]:
            video_files = video["video_files"]
            link_download = video_files[0]["link"]
            for f in video_files:
                if f["quality"] == "hd" and f["file_type"] == "video/mp4":
                    link_download = f["link"]
                    break
            links.append(link_download)

        return links
    except Exception:
        return ["https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"]


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
    print("✍️ A transcrever áudio para gerar legendas com o Whisper (GPU)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = whisper.load_model(MODELO_WHISPER, device=device)
    fp16_mode = True if device == "cuda" else False
    resultado = modelo.transcribe(
        ARQUIVO_AUDIO, word_timestamps=True, fp16=fp16_mode, language="pt"
    )
    return resultado["segments"]


def montar_video(segmentos_legenda, arquivos_video, estilo=None):
    if estilo is None:
        from styles import ESTILOS
        estilo = ESTILOS["default"]

    print(f"🎬 A montar o vídeo com Estilo: {estilo.get('cor_legenda')}...")
    audio = AudioFileClip(ARQUIVO_AUDIO)
    duracao_final = audio.duration

    print(f"🖼️ Gerando trocas de cena fluidas para {duracao_final:.2f}s...")

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

        cena = cena.resized(height=1920)
        cena = cena.cropped(x_center=int(cena.w / 2), y_center=int(cena.h / 2), width=1080, height=1920)

        if i % 2 == 0:
            cena = cena.resized(1.05)
            cena = cena.cropped(x_center=int(cena.w / 2), y_center=int(cena.h / 2), width=1080, height=1920)

        cenas_finais.append(cena.with_start(tempo_atual))
        tempo_atual += duracao_cena

    video_base = CompositeVideoClip(cenas_finais, size=(1080, 1920)).with_audio(audio)

    print("✍️ Gerando legendas customizadas...")
    clipes_extras = []

    handle_text = estilo.get("handle", "@Curiosidades")
    watermark = (
        TextClip(
            text=handle_text,
            font=estilo["font"],
            font_size=40,
            color="white",
            method="caption",
            size=(300, None),
        )
        .with_opacity(0.5)
        .with_position(("right", "top"))
        .with_duration(duracao_final)
        .with_start(0)
    )

    clipes_extras.append(watermark)

    for seg in segmentos_legenda:
        palavras = seg.get("words", [])
        if not palavras:
            itens = [{"start": seg["start"], "end": seg["end"], "text": seg["text"].strip().upper()}]
        else:
            itens = []
            max_p = 3
            for j in range(0, len(palavras), max_p):
                fatia = palavras[j : j + max_p]
                txt = " ".join([p["word"].strip() for p in fatia]).upper()
                itens.append({"start": fatia[0]["start"], "end": fatia[-1]["end"], "text": txt})

        for item in itens:
            texto_seguro = f" {item['text']} "
            largura_segura = int(1080 * 0.90)

            txt_clip = TextClip(
                text=texto_seguro,
                font=estilo["font"],
                font_size=estilo["font_size"],
                color=estilo["cor_legenda"],
                stroke_color=estilo["stroke_color"],
                stroke_width=2,
                method="caption",
                size=(largura_segura, None),
                text_align="center",
            )

            pos_y = int(1920 * estilo.get("posicao_y", 0.8))
            txt_clip = (
                txt_clip.with_position(("center", pos_y), relative=False)
                .with_start(item["start"])
                .with_end(item["end"])
            )
            clipes_extras.append(txt_clip)

    video_final = CompositeVideoClip([video_base] + clipes_extras)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_final = os.path.join("outputs", f"video_{timestamp}.mp4")

    print(f"⏳ Renderizando Vídeo Viral ({duracao_final:.2f}s)...")
    video_final.write_videofile(nome_final, fps=30, codec="libx264", audio_codec="aac", logger="bar")

    audio.close()
    for v in clips_de_fundo:
        v.close()
    video_final.close()

    return nome_final


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

    bruto = pesquisar_dados_brutos(tema_title, keywords=tema_keywords)
    fatos = gerar_resumo_factual(bruto, tema_title, use_llm=False)

    if not fatos:
        print("ℹ️ Extração local insuficiente. Tentando LLM para resumo factual...")
        fatos = gerar_resumo_factual(bruto, tema_title, use_llm=True)

    if not validar_densidade(fatos):
        print("❌ Fatos insuficientes. Encerrando.")
        return

    roteiro, termo_busca = gerar_roteiro_factual(fatos)

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
