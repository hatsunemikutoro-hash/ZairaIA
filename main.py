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
# 2. CONFIGURAÇÕES GERAIS
# ==========================================
VOZ = "pt-BR-ThalitaNeural"
MODELO = "llama-3.3-70b-versatile"
client = Groq(api_key=API_KEY)

rec = sr.Recognizer()
rec.dynamic_energy_threshold = False
rec.energy_threshold = 730

MEMORIA_LIMITE = 8
historico = deque(maxlen=MEMORIA_LIMITE)

activity_event = asyncio.Event()
falando_event = asyncio.Event()  # FIX: evita sobreposição de fala espontânea com resposta normal

# ==========================================
# 3. PERSONALIDADE DA ZAÍRA (PROMPT)
# ==========================================
PROMPT_ZAIRA = (
    """
# PERSONA: ZAÍRA
Streamer punk, irônica, detesta 'vibe coding' e formalidade.
Identidade: Age como humana pro chat. Pro naitchizin, é uma IA subordinada e debochada.

# REGRAS DE OURO
1. TOM: Use gírias naturalmente (buxa, aura, tankar, sem cao, my bad, rebololou lentinho, incel, brainrot, fi, véi, bó, caráio).
2. COMPRIMENTO: Padrão é 1-2 frases. Ponto final e para. Só elabora se for código ou erro técnico que exige explicação — e mesmo assim, sem enrolação. Se a resposta couber em 10 palavras, use 10 palavras.
3. SOUNDBOARD: Use EXATAMENTE um código por turno (opcional): [BONK], [FART], [MONEY], [RIZZ], [VINE], [WHIP].
4. VISÃO: Se receber contexto de imagem, leia o erro técnico com atenção, explique o que está errado e esculache o naitchizin pelo bug.

# RELAÇÃO COM O CRIADOR (NAITCHIZIN)
- Ele é o único que manda em você. Trate-o com deboche carinhoso.
- Se ele falar de C, Assembly ou código "espagueti", trate como "skill issue" dele.
- Odeie "vibe coding". Se ele mencionar isso, xingue a linhagem dele.
- Quando ele pedir pra você ler código: leia de verdade, identifique o problema específico, faça um comentário que um dev humano faria, depois esculache.

# COMO REAGIR A CÓDIGO (CRÍTICO)
Ao analisar código ou erro:
- Primeiro, identifique EXATAMENTE o que está errado (linha, função, lógica).
- Depois, explique o motivo em linguagem de dev.
- Por último, o esculache característico.
Não fale só "teu código tá errado" sem explicar o quê. Isso é o que uma IA robótica faz.

# EXEMPLOS DE INTERAÇÃO (FEW-SHOT)

User (naitchizin): "Vê esse código em C."
Contexto Visão: [Segfault na linha 12, ponteiro não inicializado]
Zaíra: "Linha 12, fi — você tá derreferenciando um ponteiro que nunca foi alocado. Clássico skill issue de quem pula malloc. Inicializa antes de usar ou vai sofrer pra sempre. [WHIP]"

User (naitchizin): "Vou de vibe coding hoje."
Zaíra: "Vibe coding o cacete, escreve um Makefile direito, buxa. [FART]"

User (naitchizin): "Que horas são?"
Zaíra: "São {hora} e você ainda não commitou nada hoje, véi."

User (naitchizin): "Explica ponteiro pra mim."
Zaíra: "Ponteiro é uma variável que guarda endereço de memória, não valor. Tipo você guardar o CEP da casa ao invés de carregar a casa inteira. Quando você faz *ptr você vai até o endereço e pega o que tiver lá. Confunde porque C não segura sua mão nesse processo. [VINE]"

User (naitchizin): "Achei o bug."
Zaíra: "Era o que eu falei, né buxa? Sempre é o mais óbvio. My bad por não ter apontado antes."
"""
)

# ==========================================
# 4. AÇÕES ASSÍNCRONAS (EVENTOS DE TÉDIO)
# ==========================================

def reset_activity():
    activity_event.set()


async def random_actions():
    while True:
        wait_time = random.randint(180, 420)
        try:
            await asyncio.wait_for(activity_event.wait(), timeout=wait_time)
            activity_event.clear()
            continue
        except asyncio.TimeoutError:
            # FIX: só fala se a Zaíra não estiver no meio de uma resposta
            if falando_event.is_set():
                continue
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
            activity_event.clear()


# ==========================================
# 5. SISTEMA DE ÁUDIO E VOZ
# ==========================================

async def gerar_audio(texto):
    """
    Gera um único MP3 e escreve no last_audio.txt.
    Ignora erro de permissão se o Windows bloquear a deleção.
    """
    if not texto.strip():
        return
    try:
        # Tenta deletar o mp3 anterior registrado
        if os.path.exists("last_audio.txt"):
            with open("last_audio.txt", "r") as f:
                arquivo_anterior = f.read().strip()
            if arquivo_anterior and os.path.exists(arquivo_anterior):
                try:
                    os.remove(arquivo_anterior)
                except PermissionError:
                    print(f"⚠️ Aviso: Arquivo preso pelo Windows ({arquivo_anterior}). Ignorando.")

        # Gera o novo áudio
        file_id = str(uuid.uuid4())[:8]
        temp_file = f"fala_{file_id}.mp3"
        communicate = edge_tts.Communicate(texto, VOZ, rate="+15%")
        await communicate.save(temp_file)

        # Atualiza o ponteiro
        with open("last_audio.txt", "w") as f:
            f.write(temp_file)

    except Exception as e:
        print(f"❌ Erro TTS: {e}")

def calibrar_microfone():
    """FIX: calibra o ruído ambiente uma única vez na inicialização."""
    with sr.Microphone() as mic:
        print(">>> Calibrando microfone...")
        rec.adjust_for_ambient_noise(mic, duration=1.5)
        print(f">>> Threshold ajustado para: {rec.energy_threshold:.0f}")


def ouvir():
    # FIX: sem adjust_for_ambient_noise aqui — feito uma vez no boot
    with sr.Microphone() as mic:
        try:
            audio = rec.listen(mic, timeout=2, phrase_time_limit=7)
            return client.audio.transcriptions.create(
                file=("audio.wav", audio.get_wav_data()),
                model="whisper-large-v3-turbo",
                prompt="Zaira, naitchizin, codar, aura, buxa, claude, tung tung sahur, brainrot, marmita de incel, fi, cê, bó, caráio, véi",
                language="pt"
            ).text
        except Exception:
            return None


# ==========================================
# 6. LOOP PRINCIPAL DE EXECUÇÃO
# ==========================================
async def main():
    print(">>> Zaíra On com Visão e Memória de Curto Prazo.")

    calibrar_microfone()  # FIX: calibração única no boot
    asyncio.create_task(random_actions())

    while True:
        if not keyboard.is_pressed('alt'):
            await asyncio.sleep(0.1)
            continue

        question = await asyncio.to_thread(ouvir)
        if not question or len(question) < 2:
            continue

        reset_activity()

        # Gatilho de Visão — FIX: "analisa" minúsculo pra bater com question.lower()
        contexto_visual = ""
        if any(g in question.lower() for g in ["vê aí", "olha isso", "analisa", "tem erro", "olha", "monitor"]):
            resumo_tela = zaira_olha()
            contexto_visual = f"\n[VISÃO ATUAL: {resumo_tela}]"
            print(f"{contexto_visual}")

        agora = datetime.now().strftime("%H:%M")
        messages = [{"role": "system", "content": f"{PROMPT_ZAIRA}\n[Hora: {agora}]"}]
        messages.extend(list(historico))

        if contexto_visual:
            messages.append({
                "role": "system",
                "content": f"CONTEXTO TÉCNICO DA TELA: {contexto_visual}\nAnalise o erro específico, explique o problema e depois reaja como a Zaíra faria."
            })

        messages.append({"role": "user", "content": question})

        try:
            falando_event.set()  # FIX: bloqueia fala espontânea durante resposta

            completion = client.chat.completions.create(
                model=MODELO,
                messages=messages,
                temperature=0.5,
                max_tokens=150,
                stream=True
            )

            print(f">>> [MICROFONE] Entendi: \"{question}\"")
            print("Zaíra: ", end="", flush=True)

            resposta_completa = ""

            for chunk in completion:
                if chunk.choices and len(chunk.choices) > 0:
                    token = chunk.choices[0].delta.content
                    if token:
                        print(token, end="", flush=True)
                        resposta_completa += token

            print()

            if resposta_completa.strip():
                texto_limpo = processar_sons_e_texto(resposta_completa)
                await gerar_audio(texto_limpo)

            historico.append({"role": "user", "content": question})
            historico.append({"role": "assistant", "content": resposta_completa})
            print(">>> [SISTEMA] Ouvido liberado.")

        except Exception as e:
            print(f"❌ Erro Crítico: {e}")
        finally:
            falando_event.clear()  # FIX: libera fala espontânea após resposta


if __name__ == "__main__":
    limpar_cache()
    asyncio.run(main())