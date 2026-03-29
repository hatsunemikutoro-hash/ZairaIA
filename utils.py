import os
import glob
import asyncio
import random
import re
import pygame

if not pygame.mixer.get_init():
    pygame.mixer.init()

def limpar_cache():
    print(">>> [SISTEMA] Faxina nos arquivos de áudio...")
    # Apaga todos os arquivos que começam com 'fala_' e terminam com '.mp3'
    for f in glob.glob("fala_*.mp3"):
        try:
            os.remove(f)
        except:
            pass
    # Reseta o sinalizador pro Visual não ler lixo
    if os.path.exists("last_audio.txt"):
        try:
            os.remove("last_audio.txt")
        except:
            pass


def processar_sons_e_texto(texto):
    """
    Identifica [SOM], toca o mp3 e limpa a string para a voz da Thalita.
    """
    # Procura por padrões tipo [BONK], [RIZZ], etc.
    sons_encontrados = re.findall(r'\[(.*?)\]', texto)

    # Remove os colchetes do texto para a voz não ler errado
    texto_limpo = re.sub(r'\[.*?\]', '', texto).strip()

    # Toca o primeiro som que encontrar (evita spam)
    if sons_encontrados:
        som_nome = sons_encontrados[0].lower().strip()
        caminho_som = f"soundboard/{som_nome}.mp3"

        if os.path.exists(caminho_som):
            try:
                # O mixer do pygame precisa estar iniciado no main.py!
                som_obj = pygame.mixer.Sound(caminho_som)
                som_obj.set_volume(0.4)  # Volume mais baixo pra voz aparecer
                som_obj.play()
                print(f">>> [SOUNDBOARD] Executando: {som_nome}")
            except Exception as e:
                print(f">>> [ERRO] Falha ao tocar som: {e}")
        else:
            print(f">>> [AVISO] Som '{caminho_som}' não encontrado na pasta.")

    return texto_limpo