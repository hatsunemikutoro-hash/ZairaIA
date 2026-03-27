import subprocess
import sys
import time
from utils import *
import signal


def run_zaira():
    processes = []

    try:
        # 1. Sobe o Cérebro
        print(">>> [BOOT] Acordando o cérebro...")
        brain = subprocess.Popen([sys.executable, "main.py"])
        processes.append(brain)

        time.sleep(2)  # Breath time

        # 2. Sobe o Visual
        print(">>> [BOOT] Projetando o avatar...")
        avatar = subprocess.Popen([sys.executable, "visual.py"])
        processes.append(avatar)

        print("\n--- ZAÍRA ONLINE (NIGHTZIN LABS) ---")
        print("Pressione Ctrl+C para desligar tudo com segurança.\n")

        # 3. Loop de Monitoramento (Vigia se alguém morreu)
        while True:
            # Se qualquer um dos dois fechar, a gente encerra o programa
            if brain.poll() is not None or avatar.poll() is not None:
                print("\n>>> [AVISO] Um dos processos da Zaíra fechou. Encerrando...")
                break
            time.sleep(1)  # Checa a cada segundo pra não fritar a CPU

    except KeyboardInterrupt:
        print("\n>>> [OFFLINE] Comando de desligamento recebido.")

    finally:
        # 4. Cleanup Geral (Não deixa zumbis no Windows)
        for p in processes:
            if p.poll() is None:  # Se ainda estiver rodando
                print(f">>> Finalizando {p.args[1]}...")
                p.terminate()
                # Dá 1 segundo pro processo fechar os handles de áudio/microfone
                try:
                    p.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    p.kill()  # Se não fechar no amor, vai no kill

        print(">>> Sistema totalmente desligado. Fui.")


if __name__ == "__main__":
    limpar_cache()
    run_zaira()