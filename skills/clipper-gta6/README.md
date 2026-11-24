# Clipper do GTA 6

Uma skill grátis pro Claude Code que transforma lives longas de streamers em cortes verticais prontos pra postar.

Você manda o link de uma live (YouTube, Twitch ou Kick), ou pede as maiores lives de GTA 6 do dia, e recebe:

- o corte vertical (1080×1920): câmera do streamer em cima, jogo embaixo
- título de gancho e legenda palavra por palavra
- um `.txt` com a legenda do post, as hashtags e o crédito da live

## O que ela faz, em 4 passos

1. **Baixa só o áudio.** Uma live de 4 horas fica com algumas centenas de MB, não um vídeo gigante.
2. **Escuta a live inteira no seu computador.** Escreve tudo que o streamer fala e marca onde ele ficou alto
   (grito, surto) e, no YouTube, onde o chat acelerou.
3. **A IA lê 12 minutos por vez e dá nota pra cada momento.** É rigorosa: o que precisa de contexto ou começa
   com enrolação vai pro lixo.
4. **Monta os cortes.** Baixa só os minutos escolhidos, acha a câmera do streamer sozinha e coloca a legenda.

## Instalação

Você precisa do **Claude Code** (pode ser com a sua assinatura do Claude ou de graça, com o Ollama).

### Jeito de graça (Ollama)

1. Instale o Ollama: https://ollama.com/download
2. Instale o Claude Code. No terminal:
   - Mac: `curl -fsSL https://claude.ai/install.sh | bash`
   - Windows (PowerShell): `irm https://claude.ai/install.ps1 | iex`
3. Veja a memória do seu computador (Mac: maçã → Sobre este Mac; Windows: Configurações → Sistema → Sobre).
   - 16 GB → `qwen3.5:9b`
   - 32 GB ou mais → `qwen3.5:27b`
4. No terminal: `ollama launch claude` e escolha o modelo. O Ollama baixa ele sozinho na primeira vez.

### Com a assinatura do Claude

Só instale o Claude Code (passo 2) e abra com `claude`. As escolhas dos cortes ficam bem melhores.

### Colocando a skill

Baixe esta skill (botão verde **Code → Download ZIP**), descompacte, arraste a pasta pra dentro do Claude Code e fale:

> instala essa skill e monta o clipper do GTA 6

Ele confere o que falta no seu computador (ffmpeg, Python), instala e avisa quando tá pronto.

## Usando

- "corta essa live: LINK"
- "acha as maiores lives de GTA 6 de hoje e corta"
- "faz 5 cortes dessa live: LINK"

Os cortes ficam na pasta `clipper-gta6/cortes` da sua pasta de usuário.

## Precisa ter

- Mac, Windows ou Linux
- Python 3.10 ou mais novo (python.org)
- ffmpeg (o Claude instala pra você)
- uns 2 GB livres pros modelos de escuta, mais o áudio das lives

## Respeite os streamers

Corte só quem libera cortes e mantenha o crédito que vem no `.txt` de cada corte.
