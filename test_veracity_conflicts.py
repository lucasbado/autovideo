import sys
import os
import json

# Adiciona src ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import researcher
import veracity_check

def test_conflict_detection():
    print("\n--- TESTANDO DETECÇÃO DE CONFLITO EM researcher.py ---")
    tema = "Lançamento do Console X"
    
    # Simula fragmentos com datas conflitantes
    fragments = [
        {
            "title": "Fonte 1",
            "content": "O Console X foi lançado oficialmente em 15 de novembro de 2024.",
            "url": "http://trusted.com",
            "trusted": True
        },
        {
            "title": "Fonte 2",
            "content": "Muitos dizem que o Console X saiu em 2022, mas na verdade foi em 2024.",
            "url": "http://blog.com",
            "trusted": False
        },
        {
            "title": "Fonte Conflitante",
            "content": "O Console X foi um fracasso quando lançado em 2020.",
            "url": "http://fake.com",
            "trusted": False
        }
    ]
    
    fato_duvidoso = "O Console X foi lançado em 2020."
    confirmado, sources = researcher.confirmar_fato(fato_duvidoso, fragments, tema=tema, min_sources=2)
    
    print(f"Fato: {fato_duvidoso}")
    print(f"Resultado: {'Confirmado' if confirmado else 'Descartado'}")
    if not confirmado:
        print("✅ Sucesso: O fato conflitante sem fonte confiável foi descartado.")
    else:
        print("❌ Falha: O fato conflitante deveria ter sido descartado.")

def test_roteiro_auditoria():
    print("\n--- TESTANDO AUDITORIA DE VERACIDADE EM veracity_check.py ---")
    
    fatos_json = {
        "entidade": "Gato de Botas",
        "fatos": [
            {"fato": "O Gato de Botas usa uma capa preta [1]", "detalhe": "Detalhe da vestimenta"},
            {"fato": "Ele é um espadachim habilidoso [2]", "detalhe": "Habilidade principal"}
        ]
    }
    
    # Roteiro com alucinação (inventando que ele voa)
    roteiro_ruim = "[SCENE: Gato lutando] Ele é o melhor espadachim do mundo. [SCENE: Gato voando] Além disso, ele consegue voar para escapar de dragões."
    
    aprovado, auditoria = veracity_check.verificar_veracidade_roteiro(roteiro_ruim, fatos_json)
    
    print(f"Roteiro com alucinação ('voar')")
    print(f"Auditoria: {'Aprovado' if aprovado else 'Reprovado'}")
    print(f"Score: {auditoria.get('score_fidelidade')}")
    print(f"Justificativa: {auditoria.get('justificativa')}")
    
    if not aprovado:
        print("✅ Sucesso: O roteiro alucinado foi reprovado.")
    else:
        print("❌ Falha: O roteiro alucinado deveria ter sido reprovado.")

if __name__ == "__main__":
    try:
        test_conflict_detection()
    except Exception as e:
        print(f"Erro no teste de conflito: {e}")
        
    try:
        test_roteiro_auditoria()
    except Exception as e:
        print(f"Erro no teste de auditoria: {e}")
