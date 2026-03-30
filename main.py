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

async def gerar_audio(texto):
    try:
        file_id = str(uuid.uuid4())[:8]
        temp_file = f"fala_{file_id}.mp3"
        communicate = edge_tts.Communicate(texto, VOZ, rate="+15%")
        await communicate.save(temp_file)
        with open("last_audio.txt", "w") as f:
            f.write(temp_file)
    except Exception as e:
        print(f"Erro ao gerar áudio: {e}")


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
    asyncio.create_task(random_actions())

    while True:
        # 1. ESCUTA O MICROFONE

        if not keyboard.is_pressed('alt'):  # Escolha a tecla que preferir
            await asyncio.sleep(0.1)
            continue

        question = await asyncio.to_thread(ouvir)
        if not question or len(question) < 2:
            continue

        # --- MOMENTO 1: Você falou, reseta o tédio ---
        reset_activity()

        # 2. SISTEMA DE GATILHO DE VISÃO
        contexto_visual = ""
        gatilhos = ["vê aí", "olha isso", "vê minha tela", "analisa", "tá vendo", "tem erro"]

        if any(g in question.lower() for g in gatilhos):
            print("👁️ Zaíra focando a visão com Llama 4 Scout...")
            resumo_tela = zaira_olha()
            contexto_visual = f"\n[FOCO PRIORITÁRIO - VISÃO ATUAL DA TELA: {resumo_tela}]"

        # 3. CONTEXTO TEMPORAL
        agora = datetime.now().strftime("%H:%M")
        dia_semana = datetime.now().strftime("%A")

        # 4. MONTAGEM DAS MENSAGENS (CÉREBRO)
        # Começamos com a personalidade base
        messages = [{"role": "system", "content": f"{PROMPT_ZAIRA}\n[Contexto: {agora} de {dia_semana}]"}]

        # Adicionamos o histórico de conversa
        messages.extend(list(historico))

        # SE TEVE VISÃO: Injetamos um System Prompt AGORA (logo antes da pergunta)
        # Isso garante que o Llama 3.1 dê atenção total ao que ela viu
        if contexto_visual:
            messages.append({
                "role": "system",
                "content": f"REGRA: O naitchizin pediu pra você olhar a tela. Use esta info no deboche ( se for mt burrada pode xingar sem limites ex:BURRO FIlho da PUTA): {contexto_visual}"
            })

        # Adiciona a pergunta atual do criador
        messages.append({"role": "user", "content": question})

        try:
            # 5. CHAMADA DA GROQ (Llama 3.1 8B ou 70B)
            completion = client.chat.completions.create(
                model=MODELO,
                messages=messages,
                temperature=0.4,
                max_tokens=100
            )

            res = completion.choices[0].message.content
            texto_para_voz = processar_sons_e_texto(res)

            # --- MONITOR DE TOKENS ---
            uso = completion.usage
            prompt_t = uso.prompt_tokens
            resp_t = uso.completion_tokens
            total_t = uso.total_tokens
            #----------
            print(f"--- [EXTRATO GROQ] ---")
            print(f"📥 Input: {prompt_t} | 📤 Output: {resp_t}")
            print(f"💎 Total: {total_t} tokens gastos.")
            print(f"----------------------")

            print(f">>> [MICROFONE] Entendi: \"{question}\"")
            print(f"Zaíra: {res}")

            # 6. ATUALIZA A MEMÓRIA
            historico.append({"role": "user", "content": question})
            historico.append({"role": "assistant", "content": res})

            # 7. GERA E TOCA O ÁUDIO
            # Garanta que sua função gerar_audio tenha o 'await asyncio.sleep(0.2)'
            await gerar_audio(texto_para_voz)

            # Espera ela terminar de falar + um cooldownzinho
            tempo_estimado = len(texto_para_voz) / 15
            await asyncio.sleep(1.0 + tempo_estimado)

            # --- MOMENTO 2: Terminou de falar, reseta o tédio ---
            reset_activity()

            if os.path.exists("last_audio.txt"):
                os.remove("last_audio.txt")

            print(">>> [SISTEMA] Ouvido liberado.")

        except Exception as e:
            print(f"❌ Erro no loop da Zaíra: {e}")


if __name__ == "__main__":
    limpar_cache()
    asyncio.run(main())