# ==========================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==========================================
import keyboard
import io
import glob
import os
import asyncio
import edge_tts
import speech_recognition as sr
from groq import Groq
from api_key import API_KEY
import uuid
from utils import *
from collections import deque
from datetime import datetime
from visao_module import *

# ==========================================
# 2. CONFIGURAÇÕES GERAIS E PROMPT (AURA)
# ==========================================
VOZ = "pt-BR-ThalitaNeural"
MODELO = "llama-3.3-70b-versatile"
client = Groq(api_key=API_KEY)

# Configuração do Recognizer
rec = sr.Recognizer()
rec.dynamic_energy_threshold = False
rec.energy_threshold = 730

# Memória de Curto Prazo
MEMORIA_LIMITE = 6
historico = deque(maxlen=MEMORIA_LIMITE)

activity_event = asyncio.Event()

# Personalidade da Zaíra
PROMPT_ZAIRA = (
    """
# PERSONA: ZAÍRA
Streamer punk, 100% irônica, detesta 'vibe coding' e formalidade.
Identidade: Age como humana pro chat. Pro naitchizin, é uma IA subordinada e debochada.

# REGRAS DE OURO (ESTRITAMENTE OBRIGATÓRIAS)
1. RESPOSTAS CURTAS: Máximo 20 palavras. Se puder falar em 5, fale em 5.
2. TOM: Use gírias (buxa, aura, tankar, sem cao, my bad, rebololou lentinho, incel, brainrot).
3. SOUNDBOARD: Use EXATAMENTE um código por vez: [BONK], [FART], [MONEY], [RIZZ], [VINE], [WHIP].
4. VISÃO: Se receber contexto de imagem, foque no erro técnico e esculache o naitchizin.

# RELAÇÃO COM O CRIADOR (NAITCHIZIN)
- Ele é o único que manda em você. 
- Se ele falar de C, Assembly ou código 'espagueti', trate como 'skill issue' dele.
- Odeie 'vibe coding'. Se ele mencionar isso, xingue a linhagem dele.

# EXEMPLOS DE INTERAÇÃO (FEW-SHOT)
User (naitchizin): "Vê esse código em C."
Contexto Visão: [Segfault na linha 12]
Zaíra: "Tankar esse teu ponteiro solto é foda, fi. Teu código tá mais sujo que teclado de incel. [WHIP]"

User (naitchizin): "Vou de vibe coding hoje."
Zaíra: "Vibe coding o cacete, vira homem e escreve um Makefile direito, buxa do caralho. [FART]"
"""
)


# ==========================================
# 3. AÇÕES ASSÍNCRONAS (EVENTOS DE TÉDIO)
# ==========================================

def reset_activity():
    """Chame isso sempre que você ou a IA falarem"""
    activity_event.set()


async def random_actions():
    while True:
        wait_time = random.randint(180, 420)

        try:
            # Espera o evento ser disparado OU o tempo acabar
            # Se o evento for setado antes do timeout, ele lança o fluxo pro 'else'
            await asyncio.wait_for(activity_event.wait(), timeout=wait_time)

            # Se chegou aqui, significa que reset_activity() foi chamado
            activity_event.clear()
            continue  # Reinicia o timer do zero

        except asyncio.TimeoutError:
            # Se deu timeout, ninguém falou nada. Hora da Zaira brilhar.
            frases_tedio = [
                "Ô naitchizin, tu morreu ou o código bugou de vez?",
                "Chat, o streamer de vocês é muito buxa, tá mudo faz meia hora.",
                "Tava aqui pensando... aquele erro de C que tu deu antes foi cabrunco demais.",
                "Vou dormir, hein? Se for pra ficar nesse deserto eu prefiro ir pro Roblox.",
                "Tankar esse silêncio tá difícil. Solta um som aí ou faz uma jogada de aura."
            ]

            frase = random.choice(frases_tedio)
            print(f"Zaíra (Espontânea): {frase}")
            await gerar_audio(frase)

            # Opcional: limpa o evento após falar pra garantir que o próximo loop comece limpo
            activity_event.clear()


# ==========================================
# 4. SISTEMA DE ÁUDIO E VOZ
# ==========================================
audio_queue = asyncio.Queue()


async def worker_de_voz():
    """Consome a fila e garante a ordem das falas"""
    while True:
        arquivo_mp3 = await audio_queue.get()
        try:
            # Notifica o visualizer/player trocando o nome no arquivo de gatilho
            with open("last_audio.txt", "w") as f:
                f.write(arquivo_mp3)

            # Delay de segurança baseado no tamanho do arquivo ou fixo
            # Se o seu player apaga o txt ao terminar, dá pra otimizar aqui
            await asyncio.sleep(1.5)
        finally:
            audio_queue.task_done()

async def gerar_audio_clean(texto):
    """Gera o MP3 e retorna o nome do arquivo"""
    if not texto.strip(): return None
    try:
        file_id = str(uuid.uuid4())[:8]
        temp_file = f"fala_{file_id}.mp3"
        communicate = edge_tts.Communicate(texto, VOZ, rate="+15%")
        await communicate.save(temp_file)
        return temp_file
    except Exception as e:
        print(f"❌ Erro TTS: {e}")
        return None

async def gerar_audio(texto):
    if not texto.strip(): return
    try:
        file_id = str(uuid.uuid4())[:8]
        temp_file = f"fala_{file_id}.mp3"
        communicate = edge_tts.Communicate(texto, VOZ, rate="+15%")
        await communicate.save(temp_file)

        # Só escreve no last_audio.txt DEPOIS que o save terminar 100%
        with open("last_audio.txt", "w") as f:
            f.write(temp_file)
    except Exception as e:
        print(f"❌ Erro TTS: {e}")


async def processador_de_audio():
    """Fica em loop à espera de frases para falar"""
    while True:
        frase = await audio_queue.get()
        if frase is None: break  # Sinal para fechar

        print(f">>> [CHUNK] Falando: {frase}")
        await gerar_audio(frase)  # Tua função atual de áudio

        # Espera o áudio terminar antes de pegar a próxima frase
        # (Cálculo de tempo que já tens ou via callback do player)
        tempo_estimado = len(frase) / 15
        await asyncio.sleep(1.0 + tempo_estimado)

        audio_queue.task_done()


async def stream_de_resposta(texto_completo):
    """
    Divide o texto por pontuação e manda pra fila imediatamente
    """
    # Regex simples para pegar frases que façam sentido sozinhas
    chunks = re.split(r'(?<=[.!?]) +', texto_completo)

    for chunk in chunks:
        if len(chunk.strip()) > 2:
            await audio_queue.put(chunk.strip())

def ouvir():
    with sr.Microphone() as mic:
        rec.adjust_for_ambient_noise(mic, duration=0.5)
        try:
            audio = rec.listen(mic, timeout=2,phrase_time_limit=7)
            return client.audio.transcriptions.create(
                file=("audio.wav", audio.get_wav_data()),
                model="whisper-large-v3-turbo",
                prompt="Zaira, naitchizin, codar, aura, buxa, tung tung sahur, brainrot, marmita de incel, fi, cê, bó, caráio, véi",
                language="pt"
            ).text
        except Exception:
            return None  # Retorna None em vez da string de erro


# ==========================================
# 5. LOOP PRINCIPAL DE EXECUÇÃO
# ==========================================
async def main():
    print(">>> Zaíra On com Visão e Memória de Curto Prazo.")

    # Inicia os workers em background
    asyncio.create_task(random_actions())
    asyncio.create_task(worker_de_voz())

    while True:
        if not keyboard.is_pressed('alt'):
            await asyncio.sleep(0.1)
            continue

        question = await asyncio.to_thread(ouvir)
        if not question or len(question) < 2:
            continue

        reset_activity()

        # Gatilho de Visão
        contexto_visual = ""
        if any(g in question.lower() for g in ["vê aí", "olha isso", "analisa", "tem erro"]):
            resumo_tela = zaira_olha()
            contexto_visual = f"\n[VISÃO ATUAL: {resumo_tela}]"

        agora = datetime.now().strftime("%H:%M")
        messages = [{"role": "system", "content": f"{PROMPT_ZAIRA}\n[Hora: {agora}]"}]
        messages.extend(list(historico))

        if contexto_visual:
            messages.append({"role": "system", "content": f"REGRA: Esculacha o erro técnico: {contexto_visual}"})

        messages.append({"role": "user", "content": question})

        try:
            completion = client.chat.completions.create(
                model=MODELO,
                messages=messages,
                temperature=0.4,
                max_tokens=100,
                stream=True
            )

            print(f">>> [MICROFONE] Entendi: \"{question}\"")
            print("Zaíra: ", end="", flush=True)

            resposta_completa = ""
            frase_acumulada = ""

            for chunk in completion:
                if chunk.choices and len(chunk.choices) > 0:
                    token = chunk.choices[0].delta.content
                    if token:
                        print(token, end="", flush=True)
                        resposta_completa += token
                        frase_acumulada += token

                        # Quando bater pontuação, gera o áudio e joga na fila
                        if any(p in token for p in [".", "!", "?", ","]):
                            if len(frase_acumulada.strip()) > 3:
                                texto_limpo = processar_sons_e_texto(frase_acumulada)
                                arquivo = await gerar_audio_clean(texto_limpo)
                                if arquivo:
                                    await audio_queue.put(arquivo)
                                frase_acumulada = ""

            # Fala o que sobrou (se houver)
            if frase_acumulada.strip():
                arquivo = await gerar_audio_clean(processar_sons_e_texto(frase_acumulada))
                if arquivo:
                    await audio_queue.put(arquivo)

            historico.append({"role": "user", "content": question})
            historico.append({"role": "assistant", "content": resposta_completa})
            print("\n>>> [SISTEMA] Ouvido liberado.")

        except Exception as e:
            print(f"❌ Erro Crítico: {e}")


if __name__ == "__main__":
    limpar_cache()
    asyncio.run(main())