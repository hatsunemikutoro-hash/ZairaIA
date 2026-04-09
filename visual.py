"""
Zaíra VTuber Controller — VTube Studio API
==========================================
Requisitos:
    pip install websockets pygame numpy

Como usar:
    1. Abra o VTube Studio no PC
    2. Vá em Settings > Plugins > Ative "Allow Plugin API"
    3. Rode este script — o VTS vai pedir aprovação do plugin na tela
    4. Ajuste PARAM_MOUTH_OPEN e PARAM_EYE_* com os nomes exatos dos
       parâmetros do seu modelo (veja no VTS: Parameters > Custom)

Parâmetros comuns em modelos Live2D:
    Boca:  "MouthOpen", "ParamMouthOpenY", "PARAM_MOUTH_OPEN_Y"
    Olhos: "EyeOpenLeft", "EyeOpenRight", "ParamEyeLOpen", "ParamEyeROpen"
"""

import asyncio
import json
import os
import random
import time
import threading

import numpy as np
import pygame
import websockets

# ─────────────────────────────────────────
#  CONFIGURAÇÕES — ajuste conforme seu modelo
# ─────────────────────────────────────────

VTS_URL = "ws://localhost:8001"          # Porta padrão do VTS Plugin API

# Nomes dos parâmetros no VTube Studio
# Abra o VTS > seu modelo > Parameters para ver os nomes exatos
PARAM_MOUTH_OPEN  = "MouthOpen"          # Parâmetro de abertura da boca
PARAM_EYE_LEFT    = "EyeOpenLeft"        # Parâmetro olho esquerdo
PARAM_EYE_RIGHT   = "EyeOpenRight"       # Parâmetro olho direito

# Lip Sync
LIP_SYNC_SMOOTHING  = 0.35   # 0.0 = sem suavização, 1.0 = muito suave
LIP_SYNC_MULTIPLIER = 1.7   # Amplifica o movimento de boca (ajuste a gosto)
LIP_SYNC_MIN        = 0.0    # Valor mínimo da boca (fechada)
LIP_SYNC_MAX        = 1.0    # Valor máximo da boca (aberta)

# Piscar
BLINK_INTERVAL_MIN = 2.0     # Segundos mínimos entre piscadas
BLINK_INTERVAL_MAX = 6.0     # Segundos máximos entre piscadas
BLINK_CLOSE_SPEED  = 0.07    # Velocidade de fechar o olho (segundos por frame)
BLINK_OPEN_SPEED   = 0.04    # Velocidade de abrir o olho

# Áudio
LAST_AUDIO_INFO    = "last_audio.txt"
POLL_INTERVAL      = 0.1     # Segundos entre verificações de novo áudio
SAMPLE_RATE        = 44100
CHUNK_SIZE         = 1024    # Amostras por análise de amplitude

# Plugin info (aparece no VTS na hora de aprovar)
PLUGIN_NAME        = "Zaíra Controller"
PLUGIN_DEVELOPER   = "Zaíra AI"
PLUGIN_ICON        = ""      # Opcional: base64 de imagem 128x128


# ─────────────────────────────────────────
#  ESTADO GLOBAL (thread-safe via asyncio)
# ─────────────────────────────────────────

class ZairaState:
    def __init__(self):
        self.mouth_value    = 0.0   # Valor atual da boca (suavizado)
        self.eye_left       = 1.0   # 1.0 = aberto, 0.0 = fechado
        self.eye_right      = 1.0
        self.is_speaking    = False
        self.raw_amplitude  = 0.0   # Amplitude bruta do áudio atual
        self.auth_token     = ""
        self.token_file     = "vts_token.txt"

    def load_token(self):
        if os.path.exists(self.token_file):
            with open(self.token_file) as f:
                self.auth_token = f.read().strip()

    def save_token(self, token):
        self.auth_token = token
        with open(self.token_file, "w") as f:
            f.write(token)


state = ZairaState()
state.load_token()


# ─────────────────────────────────────────
#  ANÁLISE DE AMPLITUDE (thread separada)
# ─────────────────────────────────────────

def audio_amplitude_thread():
    """Roda em thread separada — analisa amplitude do áudio em tempo real."""
    import sounddevice as sd

    def callback(indata, frames, time_info, status):
        volume = float(np.sqrt(np.mean(indata ** 2)))
        state.raw_amplitude = min(volume * LIP_SYNC_MULTIPLIER * 10, 1.0)

    with sd.InputStream(callback=callback, channels=1,
                        samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE):
        while True:
            time.sleep(0.01)


# ─────────────────────────────────────────
#  VTS API — funções de comunicação
# ─────────────────────────────────────────

async def vts_send(ws, msg_type: str, data: dict = None) -> dict:
    """Envia mensagem para o VTS e aguarda resposta."""
    payload = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": f"zaira_{msg_type}_{int(time.time()*1000)}",
        "messageType": msg_type,
        "data": data or {}
    }
    await ws.send(json.dumps(payload))
    response = await ws.recv()
    return json.loads(response)


async def authenticate(ws) -> bool:
    """Autentica com o VTube Studio. Pede token novo se necessário."""

    # Se já temos token salvo, tenta usar
    if state.auth_token:
        resp = await vts_send(ws, "AuthenticationRequest", {
            "pluginName": PLUGIN_NAME,
            "pluginDeveloper": PLUGIN_DEVELOPER,
            "authenticationToken": state.auth_token
        })
        if resp.get("data", {}).get("authenticated"):
            print("✅ Autenticado com token salvo!")
            return True
        print("⚠️  Token expirado, solicitando novo...")

    # Solicita novo token (VTS mostra popup para o usuário aprovar)
    print("📲 Aguardando aprovação no VTube Studio...")
    resp = await vts_send(ws, "AuthenticationTokenRequest", {
        "pluginName": PLUGIN_NAME,
        "pluginDeveloper": PLUGIN_DEVELOPER,
        "pluginIcon": PLUGIN_ICON
    })

    token = resp.get("data", {}).get("authenticationToken", "")
    if not token:
        print("❌ Falha ao obter token. Aprovação negada ou VTS fechado.")
        return False

    state.save_token(token)
    print(f"🔑 Token obtido: {token[:20]}...")

    # Autentica com o token novo
    resp = await vts_send(ws, "AuthenticationRequest", {
        "pluginName": PLUGIN_NAME,
        "pluginDeveloper": PLUGIN_DEVELOPER,
        "authenticationToken": token
    })

    if resp.get("data", {}).get("authenticated"):
        print("✅ Autenticado com sucesso!")
        return True

    print("❌ Autenticação falhou:", resp)
    return False


async def set_param(ws, param_name: str, value: float):
    """Define o valor de um parâmetro no VTS."""
    await vts_send(ws, "InjectParameterDataRequest", {
        "faceFound": False,
        "mode": "set",
        "parameterValues": [
            {"id": param_name, "value": round(float(value), 4)}
        ]
    })


async def set_params_batch(ws, params: dict):
    """Define vários parâmetros de uma vez (mais eficiente)."""
    param_list = [
        {"id": name, "value": round(float(val), 4)}
        for name, val in params.items()
    ]
    await vts_send(ws, "InjectParameterDataRequest", {
        "faceFound": False,
        "mode": "set",
        "parameterValues": param_list
    })


# ─────────────────────────────────────────
#  LOOP PRINCIPAL DO CONTROLADOR
# ─────────────────────────────────────────

async def blink_loop(ws):
    """Controla o piscar automático com timing aleatório natural."""
    while True:
        # Espera intervalo aleatório
        wait = random.uniform(BLINK_INTERVAL_MIN, BLINK_INTERVAL_MAX)
        await asyncio.sleep(wait)

        # Fecha os olhos gradualmente
        steps_close = 6
        for i in range(steps_close, -1, -1):
            v = i / steps_close
            state.eye_left = v
            state.eye_right = v
            await asyncio.sleep(BLINK_CLOSE_SPEED)

        # Abre os olhos gradualmente
        steps_open = 8
        for i in range(steps_open + 1):
            v = i / steps_open
            state.eye_left = v
            state.eye_right = v
            await asyncio.sleep(BLINK_OPEN_SPEED)

        # Garante que ficou totalmente aberto
        state.eye_left = 1.0
        state.eye_right = 1.0


async def audio_monitor_loop():
    """Monitora o arquivo last_audio.txt e atualiza state.is_speaking."""
    last_played = ""
    last_mtime = 0

    pygame.mixer.init()

    while True:
        await asyncio.sleep(POLL_INTERVAL)

        if not os.path.exists(LAST_AUDIO_INFO):
            state.is_speaking = pygame.mixer.music.get_busy()
            continue

        try:
            current_mtime = os.path.getmtime(LAST_AUDIO_INFO)
            if current_mtime > last_mtime:
                with open(LAST_AUDIO_INFO) as f:
                    new_audio = f.read().strip()

                if os.path.exists(new_audio) and new_audio != last_played:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()

                    if last_played and os.path.exists(last_played):
                        try:
                            os.remove(last_played)
                        except PermissionError:
                            pass

                    pygame.mixer.music.load(new_audio)
                    pygame.mixer.music.play()
                    last_played = new_audio

                last_mtime = current_mtime
        except Exception as e:
            print(f"⚠️  Erro no monitor de áudio: {e}")

        state.is_speaking = pygame.mixer.music.get_busy()


async def param_update_loop(ws):
    """Loop principal — atualiza boca e olhos no VTS ~60x/s."""
    dt = 1 / 60

    while True:
        await asyncio.sleep(dt)

        # ── Lip Sync ──────────────────────────────────────────────────
        if state.is_speaking:
            # Usa amplitude do microfone SE sounddevice estiver ativo,
            # senão faz animação de boca sintética (oscilação suave)
            raw = state.raw_amplitude if state.raw_amplitude > 0 else (
                0.4 + 0.4 * abs(
                    (time.time() * 8 % 2) - 1  # Onda triangular 4Hz
                )
            )
            target_mouth = max(LIP_SYNC_MIN, min(LIP_SYNC_MAX, raw))
        else:
            target_mouth = 0.0

        # Suavização exponencial
        state.mouth_value += (target_mouth - state.mouth_value) * (
            1.0 - LIP_SYNC_SMOOTHING
        )

        # ── Envia para o VTS ─────────────────────────────────────────
        try:
            await set_params_batch(ws, {
                PARAM_MOUTH_OPEN: state.mouth_value,
                PARAM_EYE_LEFT:   state.eye_left,
                PARAM_EYE_RIGHT:  state.eye_right,
            })
        except Exception as e:
            print(f"⚠️  Erro ao enviar parâmetros: {e}")
            break   # Reconecta no loop externo


# ─────────────────────────────────────────
#  ENTRY POINT COM RECONEXÃO AUTOMÁTICA
# ─────────────────────────────────────────

async def main():
    print("🎭 Zaíra VTuber Controller iniciando...")
    print(f"   Conectando em {VTS_URL}")

    # Tenta iniciar captura de amplitude (opcional)
    try:
        import sounddevice
        amp_thread = threading.Thread(target=audio_amplitude_thread, daemon=True)
        amp_thread.start()
        print("🎤 Captura de amplitude ativa (lip sync por áudio real)")
    except ImportError:
        print("ℹ️  sounddevice não instalado — lip sync usará animação sintética")
        print("   Para instalar: pip install sounddevice")

    while True:
        try:
            async with websockets.connect(VTS_URL) as ws:
                if not await authenticate(ws):
                    print("❌ Falha na autenticação. Tentando novamente em 5s...")
                    await asyncio.sleep(5)
                    continue

                print("🚀 Controlador ativo! Parâmetros sendo enviados ao VTS.")
                print(f"   Boca:  {PARAM_MOUTH_OPEN}")
                print(f"   Olhos: {PARAM_EYE_LEFT} / {PARAM_EYE_RIGHT}")
                print("   Pressione Ctrl+C para encerrar.\n")

                # Roda os loops em paralelo
                await asyncio.gather(
                    blink_loop(ws),
                    audio_monitor_loop(),
                    param_update_loop(ws),
                )

        except websockets.exceptions.ConnectionRefusedError:
            print("❌ VTube Studio não encontrado. Verifique se está aberto e")
            print("   com o Plugin API ativado. Tentando novamente em 5s...")
            await asyncio.sleep(5)

        except websockets.exceptions.ConnectionClosedError:
            print("⚠️  Conexão com VTS perdida. Reconectando em 3s...")
            await asyncio.sleep(3)

        except KeyboardInterrupt:
            print("\n👋 Encerrando Zaíra Controller...")
            pygame.mixer.quit()
            break

        except Exception as e:
            print(f"❌ Erro inesperado: {e}. Reconectando em 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())