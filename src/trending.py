import ollama
import random

MODELO_LLM = "llama3.1"

NICHOS = [
    "Mistérios do Universo e Astronomia",
    "Fatos Históricos Bizarros e Pouco Conhecidos",
    "Ciência de Fronteira e Física Quântica",
    "Biologia Extrema e Criaturas Abissais",
    "Arqueologia Proibida e Civilizações Perdidas",
    "Curiosidades do mundo dos Games e E-sports",
    "Tecnologia do Futuro e Inteligência Artificial",
    "Mistérios da Mente Humana e Psicologia",
    "Fatos Curiosos sobre o Corpo Humano",
    "Cinema, Séries e Cultura Pop",
    "Segredos de Marcas Famosas e Negócios",
    "Sobrevivência e Natureza Selvagem",
    "Crimes Reais e Mistérios Não Solvidos",
    "Curiosidades Geográficas e Lugares Abandonados",
    "Desenhos Animados Nostálgicos e Modernos (Curiosidades e Teorias)",
]


def buscar_tendencias_ia():
    # Garantir que estamos na raiz do projeto para qualquer log ou arquivo futuro
    # (Embora este script use apenas chamadas de API por enquanto)
    return _buscar_tendencias_ia()


def _buscar_tendencias_ia():
    print("🔍 Consultando a IA sobre tendências e tópicos de alto interesse...")
    nicho = random.choice(NICHOS)

    prompt = f"""Você é um estrategista de conteúdo viral do TikTok com foco em EDUCAÇÃO E FATOS REAIS.
    
    Nicho: {nicho}.
    
    Sua tarefa: Criar um tema para um vídeo de 1 minuto que seja:
    1. INTRIGANTE: Deve fazer o usuário querer saber a resposta (Curiosity Gap).
    2. FACTUAL: DEVE ser baseado em fatos reais, história ou ciência verificável. NADA de ficção.
    3. ESPECÍFICO: Títulos vagos matam o alcance. Seja direto.
    
    REGRAS DE OURO:
    - Se não souber um fato real e fascinante sobre o nicho, não invente. Escolha outro fato real.
    - Evite temas batidos. Busque algo que pareça um "segredo" ou "incomum".
    - Resposta: Apenas o título. Sem prefácios.
    """

    try:
        resposta = ollama.chat(
            model=MODELO_LLM, messages=[{"role": "user", "content": prompt}]
        )
        tema = resposta["message"]["content"].strip()
        # Limpeza básica caso a IA coloque aspas ou pontos finais
        tema = tema.replace('"', "").replace(".", "").strip()
        return tema
    except Exception as e:
        print(f"⚠️ Erro ao buscar tendências: {e}")
        return "O mistério dos sinais de rádio vindos do centro da galáxia"


if __name__ == "__main__":
    tema = buscar_tendencias_ia()
    print(f"🔥 Tema sugerido: {tema}")
