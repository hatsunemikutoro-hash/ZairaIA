import pygame
import os
import ctypes
import time

# --- Configurações ---
WIDTH, HEIGHT = 400, 600
FPS = 60
LIP_SYNC_SPEED = 140
LAST_AUDIO_INFO = "last_audio.txt"

# Inicialização
pygame.init()
pygame.mixer.init()

# Janela Transparente e Always on Top (Windows)
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SRCALPHA)
ctypes.windll.user32.SetWindowPos(pygame.display.get_wm_info()['window'], -1, 0, 0, 0, 0, 0x0001 | 0x0002)


def load_zaira(path):
    if not os.path.exists(path):
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (100, 0, 255), (50, 50, 300, 400))
        return surf
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (WIDTH, HEIGHT))


img_closed = load_zaira("expressions/fechado.png")
img_open = load_zaira("expressions/falando.png")

clock = pygame.time.Clock()
last_played_file = ""
last_mtime = 0
lip_state = 0
last_lip_toggle = 0

print(">>> Zaíra Visual: Rodando (Modo Anti-Bloqueio Windows)")

running = True
while running:
    now = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False

    # 1. Checa se o Cérebro mandou áudio novo
    if os.path.exists(LAST_AUDIO_INFO):
        try:
            current_mtime = os.path.getmtime(LAST_AUDIO_INFO)
            if current_mtime > last_mtime:
                with open(LAST_AUDIO_INFO, "r") as f:
                    new_audio_path = f.read().strip()

                if os.path.exists(new_audio_path) and new_audio_path != last_played_file:
                    # Mata o áudio atual e LIBERA o arquivo pro Windows
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()

                    # Tenta deletar o arquivo que acabou de tocar (Cleanup)
                    if last_played_file and os.path.exists(last_played_file):
                        try:
                            os.remove(last_played_file)
                        except PermissionError:
                            # Se falhar, o próximo loop ou o encerramento limpa
                            pass

                    # Carrega a nova fala
                    pygame.mixer.music.load(new_audio_path)
                    pygame.mixer.music.play()

                    last_played_file = new_audio_path
                last_mtime = current_mtime
        except Exception as e:
            print(f"Erro no Sync: {e}")

    # 2. Lógica de Lip Sync
    is_speaking = pygame.mixer.music.get_busy()
    if is_speaking:
        if now - last_lip_toggle > LIP_SYNC_SPEED:
            lip_state = 1 - lip_state
            last_lip_toggle = now
    else:
        lip_state = 0

    # 3. Renderização
    screen.fill((0, 255, 0))

    # Efeito de bounce básico
    offset_y = 3 if is_speaking and lip_state else 0
    img = img_open if lip_state else img_closed
    screen.blit(img, (0, offset_y))

    pygame.display.flip()
    clock.tick(FPS)

# 4. Cleanup Final ao fechar
pygame.mixer.music.stop()
pygame.mixer.music.unload()
if last_played_file and os.path.exists(last_played_file):
    try:
        os.remove(last_played_file)
    except:
        pass

pygame.quit()