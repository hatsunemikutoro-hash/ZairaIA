import os
import glob

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