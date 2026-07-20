import ollama
import random

MODELO_LLM = "llama3.1"

NICHOS = [
    "Astronomia e Exploração Espacial",
    "Arqueologia e Civilizações Antigas",
    "Ciência e Física Quântica",
    "Biologia e Criaturas Reais",
    "História e Mistérios do Passado",
    "Tecnologia e Futuro",
    "Geografia e Lugares Extremos"
]

def gerar_tema_factual(nicho_especifico=None):
    """
    Gera um tema baseado em uma entidade ou fenômeno real existente.
    Permite passar um nicho específico (ex: 'Games', 'Desenhos Animados').
    """
    if nicho_especifico:
        nicho = nicho_especifico
    else:
        nicho = random.choice(NICHOS)
        
    print(f"💡 Nicho/Contexto escolhido: {nicho}")
    
    prompt = f"""
    Você é um especialista em curadoria de CURIOSIDADES e fatos desconhecidos para redes sociais.
    Seu objetivo é sugerir um TEMA ou ENTIDADE REAL e ESPECÍFICA que possua fatos SURPREENDENTES dentro do nicho: {nicho}.
    
    REGRAS PARA O TEMA:
    1. Deve ser algo que as pessoas geralmente NÃO sabem (Curiosity Gap).
    2. Deve permitir uma narrativa de "Você sabia que...?" ou "O segredo por trás de...".
    3. Retorne APENAS o nome do assunto em INGLÊS (para melhor pesquisa web).
    
    Exemplos:
    - Em vez de "The Moon", use "The origin of the Moon's dark spots".
    - Em vez de "Minecraft", use "The secret origin of Minecraft's Creepers".
    - Em vez de "Rome", use "The hidden underground city of Rome".
    
    Retorne APENAS o nome do tema em inglês.
    """

    try:
        resposta = ollama.chat(
            model=MODELO_LLM,
            messages=[{"role": "user", "content": prompt}]
        )
        tema = resposta["message"]["content"].strip()
        tema = tema.replace('"', '').replace('.', '').strip()
        print(f"🎯 Tema Sugerido: {tema}")
        return tema
    except Exception as e:
        print(f"⚠️ Erro ao gerar tema: {e}")
        return "History of Video Games"

if __name__ == "__main__":
    gerar_tema_factual()
