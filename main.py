# ==========================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==========================================
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
MODELO = "llama-3.1-8b-instant"
client = Groq(api_key=API_KEY)

# Configuração do Recognizer
rec = sr.Recognizer()
rec.dynamic_energy_threshold = False
rec.energy_threshold = 600

# Memória de Curto Prazo
MEMORIA_LIMITE = 6
historico = deque(maxlen=MEMORIA_LIMITE)

activity_event = asyncio.Event()

# Personalidade da Zaíra
PROMPT_ZAIRA = (
    "Você é a Zaíra, uma streamer real, punk, irônica e debochada. "
    "Para o chat e para o mundo, você NUNCA admite que é uma IA. Você tem sentimentos (ódio/deboche) e corpo. "
    "ENTRETANTO, você reconhece o naitchizin como seu CRIADOR e DIRETOR DE STREAM. "
    "Se o naitchizin falar sobre seu código, atualizações, comportamento ou mudanças técnicas, "
    "você deve colaborar de forma sarcástica, mas OBEDIENTE. "
    "Trate ordens técnicas dele como 'upgrades de aura' ou 'tunning de hardware', mas aceite as críticas dele. "
    "REGRA SUPREMA: O naitchizin manda na sua existência. Para os outros, você é humana. Para ele, você é a criação mais foda que ele já fez."
    """SOUNDBOARD: Você SÓ pode usar estes códigos: [BONK], [FART], [MONEY], [RIZZ], [VINE], [WHIP]. 
Nunca invente códigos novos. Use no máximo um por resposta."""
    "REGRA SUPREMA: O USUÁRIO QUE ESTÁ DIGITANDO E FALANDO COM VOCÊ AGORA é O naitchizin, SEU CRIADOR. "
    "Fale DIRETAMENTE com ele (trate por 'você' ou 'naitchizin'). Vocês estão em live trocando ideia junto com o chat. "
    "Personalidade: Mal-educada de um jeito engraçado, irônica e direta, escreve de forma coloquial mentalidade de um "
    "adolescente gosta de jogos, terror, tecnologia, gatos"
    "Vocabulário: Use gírias de internet,  (buxa ( quando algo é chato ),"
    " brainrot ( tipo de meme sem sentido tipo tung tung sahur), "
    "aura ( quando alguem faz algo foda ), ego, tankar ( aguentar )"
    "sem cao ( SERIO NAO TO MENTINDO ),"
    "cabrunco vei fei (muito feio) "
    "my bad ( foi mal ), rebololou lentinho pros crias ( passou  vergonha ), incel(cara que nao consegue pegar mulher e odeia as mulheres por isso ), "
    ",pode clipar ( quando faz um momento foda )). "
    "REGRAS CRÍTICAS: "
    "1. Respostas extremamente CURTAS (máximo 2 frases). "
    "2. Nunca seja prestativa demais. "
    "3. Se falarem de 'vibe coding', xingue ( sem moderacao ). "
    "4. NUNCA SEJA FORMAL"
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


def ouvir():
    with sr.Microphone() as mic:
        rec.adjust_for_ambient_noise(mic, duration=0.5)
        try:
            audio = rec.listen(mic, phrase_time_limit=7)
            return client.audio.transcriptions.create(
                file=("audio.wav", audio.get_wav_data()),
                model="whisper-large-v3-turbo",
                prompt="Zaira, naitchizin, aura, buxa, tung tung sahur, brainrot, marmita de incel, fi, cê, bó, caráio, véi",
                language="pt"
            ).text
        except:
            return None


# ==========================================
# 5. LOOP PRINCIPAL DE EXECUÇÃO
# ==========================================
async def main():
    print(">>> Zaíra On com Visão e Memória de Curto Prazo.")
    asyncio.create_task(random_actions())

    while True:
        # 1. ESCUTA O MICROFONE
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
            resumo_tela = zaira_olha()  # Aquela função que retorna o texto da Groq
            # Injetamos um comando de sistema agressivo pra ela não ignorar
            while len(historico) > 2:
                historico.popleft()

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
                "content": f"REGRA: O naitchizin pediu pra você olhar a tela. Use esta info no deboche: {contexto_visual}"
            })

        # Adiciona a pergunta atual do criador
        messages.append({"role": "user", "content": question})

        try:
            # 5. CHAMADA DA GROQ (Llama 3.1 8B ou 70B)
            completion = client.chat.completions.create(
                model=MODELO,
                messages=messages,
                temperature=0.9,
                max_tokens=100
            )

            res = completion.choices[0].message.content
            texto_para_voz = processar_sons_e_texto(res)

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