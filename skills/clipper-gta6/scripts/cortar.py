"""Passos 3 e 4: junta as notas que a IA deu, fica com os melhores e monta os cortes verticais.

Cada corte: câmera do streamer em cima, jogo embaixo, título de gancho, legenda palavra por palavra
e um .txt com a legenda do post e as hashtags.
"""
import json
import subprocess
from pathlib import Path

from comum import (CORTES, YUNET, gravar_json, hms, ler_json, rodar, segundos, ytdlp)  # noqa: F401

L, A = 1080, 1920          # vídeo vertical
CAM_H = 768                # faixa da câmera em cima
JOGO_H = A - CAM_H         # faixa do jogo embaixo


# ================================================================ escolher
def escolher(pasta, manter=3, minimo=15, maximo=90):
    todos, ruins = [], []
    for arq in sorted((pasta / "momentos").glob("bloco_*.json")):
        dados = ler_json(arq)
        if dados is None:
            ruins.append(arq.name)
            continue
        for m in dados if isinstance(dados, list) else dados.get("momentos", []):
            try:
                s, e = segundos(m["inicio"]), segundos(m["fim"])
                m.update(_s=s, _e=e, nota=float(m.get("nota", 0)), _bloco=arq.stem)
                if e - s < minimo:
                    m["_e"] = s + minimo
                if e - s > maximo:
                    m["_e"] = s + maximo
                todos.append(m)
            except (KeyError, ValueError, TypeError):
                ruins.append(f"{arq.name}: {str(m)[:60]}")
    if ruins:
        print("ATENÇÃO, não consegui ler:", *ruins, sep="\n  ")
    todos.sort(key=lambda m: -m["nota"])
    escolhidos = []
    for m in todos:
        if any(m["_s"] < o["_e"] and o["_s"] < m["_e"] for o in escolhidos):
            continue  # sobrepõe um corte melhor
        escolhidos.append(m)
        if len(escolhidos) >= manter:
            break
    escolhidos.sort(key=lambda m: m["_s"])
    gravar_json(pasta / "escolhidos.json", {"possiveis": len(todos), "cortes": escolhidos})
    print(f"\nA IA achou {len(todos)} momentos possíveis e ficou com os {len(escolhidos)} melhores:")
    for i, m in enumerate(escolhidos, 1):
        print(f"  {i}. [{hms(m['_s'])}–{hms(m['_e'])}] nota {m['nota']:.0f}  {m.get('titulo', '')}")
    return escolhidos


# ================================================================ câmera do streamer
def achar_camera(video):
    """Procura o rosto em 14 quadros do trecho e devolve a caixa (x, y, l, a) do rosto mais frequente."""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(video))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    esc = 960 / W
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (960, int(H * esc)), 0.75)
    caixas = []
    for k in range(14):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / 14))
        ok, q = cap.read()
        if not ok:
            continue
        _, rostos = det.detect(cv2.resize(q, (960, int(H * esc))))
        for r in rostos if rostos is not None else []:
            if r[14] >= 0.75 and r[3] / esc > H * 0.05:
                caixas.append([v / esc for v in r[:4]])
    cap.release()
    if len(caixas) < 3:
        return W, H, None
    c = np.array(caixas)
    centros = c[:, :2] + c[:, 2:] / 2
    med = np.median(centros, axis=0)
    perto = c[np.linalg.norm(centros - med, axis=1) < W * 0.08]
    if len(perto) < 3:
        return W, H, None
    return W, H, np.median(perto, axis=0)


def _par(v):
    return int(v) // 2 * 2


def filtro(W, H, rosto):
    if rosto is None:  # sem câmera: jogo inteiro no meio, fundo desfocado
        return ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3[bg];"
                "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p,ass=legenda.ass[v]")
    fx, fy, fw, fh = rosto
    cw = min(W, max(fw * 2.4, 200))
    ch = cw * CAM_H / L
    if ch > H:
        ch, cw = H, H * L / CAM_H
    cx = min(max(fx + fw / 2 - cw / 2, 0), W - cw)
    cy = min(max(fy + fh * 0.65 - ch / 2, 0), H - ch)
    gw = min(W, H * L / JOGO_H)
    gx = (W - gw) / 2
    return (f"[0:v]crop={_par(cw)}:{_par(ch)}:{_par(cx)}:{_par(cy)},scale={L}:{CAM_H},setsar=1[cam];"
            f"[0:v]crop={_par(gw)}:{_par(H)}:{_par(gx)}:0,scale={L}:{JOGO_H},setsar=1[jogo];"
            f"[cam][jogo]vstack=inputs=2,format=yuv420p,ass=legenda.ass[v]")


# ================================================================ legenda
def _ass_tempo(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _limpo(txt):
    return txt.replace("{", "(").replace("}", ")").replace("\\", "/").strip()


# Palavrões são censurados: na legenda viram "PI" e no áudio um bip cobre a palavra.
PALAVROES = {"caralho", "porra", "puta", "puto", "cu", "cú", "merda", "bosta", "cacete",
             "fuder", "fudeu", "fude", "fudei", "fode", "fodeu", "fodendo", "fudendo",
             "viado", "desgraçado", "desgraça", "piranha", "arrombado", "corno", "cuzão"}


def _norm(w):
    import re
    return re.sub(r"[^a-zà-ÿ]", "", w.lower())


def eh_palavrao(w):
    n = _norm(w)
    return n in PALAVROES or any(n.startswith(p) and len(n) <= len(p) + 2 for p in PALAVROES if len(p) > 2)


def censurar(palavras):
    return [(s, e, "pi" if eh_palavrao(w) else w) for s, e, w in palavras]


def palavras_do_trecho(video, idioma, modelo="small"):
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(video), language=idioma, word_timestamps=True, vad_filter=True,
                           condition_on_previous_text=False)
    return [(w.start, w.end, w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()]


def escrever_ass(caminho, titulo, palavras, dur, com_camera):
    y_titulo = CAM_H if com_camera else 520
    y_leg = CAM_H - 60 if com_camera else 1480
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {L}", f"PlayResY: {A}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        "Style: Gancho,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H000000FF,1,0,0,0,100,100,0,0,3,18,0,5,60,60,0,1",
        "Style: Leg,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H000000FF,1,0,0,0,100,100,0,0,1,7,3,5,40,40,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 1,{_ass_tempo(0)},{_ass_tempo(dur)},Gancho,,0,0,0,,{{\\pos(540,{y_titulo})}}{_limpo(titulo).upper()}",
    ]
    grupos = [palavras[i:i + 3] for i in range(0, len(palavras), 3)]
    for g, grupo in enumerate(grupos):
        prox = grupos[g + 1][0][0] if g + 1 < len(grupos) else dur
        for k, (s, e, _) in enumerate(grupo):
            fim = grupo[k + 1][0] if k + 1 < len(grupo) else (prox if prox - e < 0.6 else e + 0.25)
            txt = " ".join(("{\\c&H00E5FF&}" if j == k else "{\\c&HFFFFFF&}") + _limpo(w).upper()
                           for j, (_, _, w) in enumerate(grupo))
            linhas.append(f"Dialogue: 0,{_ass_tempo(s)},{_ass_tempo(fim)},Leg,,0,0,0,,{{\\pos(540,{y_leg})}}{txt}")
    Path(caminho).write_text("\n".join(linhas) + "\n", encoding="utf-8")


# ================================================================ baixar só o pedaço
FORMATO = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"


def tem_video(arq):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", str(arq)], capture_output=True, text=True)
    return r.stdout.strip().isdigit() and int(r.stdout.strip()) > 10


def baixar_trecho(pasta, url, s, e, destino):
    """Tenta baixar só os minutos do corte. Alguns sites (hoje o YouTube) não entregam a imagem desse jeito:
    aí baixa o vídeo da live uma vez só (até 1080p) e recorta aqui no computador."""
    print("      baixando só esse pedaço do vídeo…")
    try:
        rodar(ytdlp() + ["-f", FORMATO, "--no-playlist", "--no-warnings", "-q", "--download-sections",
                         f"*{s:.2f}-{e:.2f}", "--force-keyframes-at-cuts", "--merge-output-format", "mp4",
                         "-o", str(destino), url])
    except subprocess.CalledProcessError:
        pass
    if destino.exists() and tem_video(destino):
        return
    destino.unlink(missing_ok=True)
    inteiro = next(iter(pasta.glob("video_inteiro.*")), None)
    if not inteiro or not tem_video(inteiro):
        print("      esse site não deixa baixar só um pedaço da imagem: baixando o vídeo uma vez (até 1080p)…")
        rodar(ytdlp() + ["-f", FORMATO, "--no-playlist", "--no-warnings", "--merge-output-format", "mp4",
                         "-o", str(pasta / "video_inteiro.%(ext)s"), url])
        inteiro = next(iter(pasta.glob("video_inteiro.*")))
    rodar(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s:.2f}", "-i", inteiro, "-t", f"{e - s:.2f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", destino])


# ================================================================ fazer
def fazer(pasta, modelo_legenda="small"):
    info = ler_json(pasta / "info.json", {})
    escolhidos = ler_json(pasta / "escolhidos.json", {}).get("cortes")
    if not escolhidos:
        raise SystemExit("Nenhum corte escolhido ainda. Rode antes: clip.py escolher " + pasta.name)
    idioma = ler_json(pasta / "transcricao.json", {}).get("idioma")
    destino = CORTES / pasta.name
    destino.mkdir(parents=True, exist_ok=True)
    feitos = []
    for i, m in enumerate(escolhidos, 1):
        s, e = m["_s"], m["_e"]
        print(f"\n[4/4] Corte {i}/{len(escolhidos)}: {m.get('titulo', '')}  ({hms(s)}–{hms(e)})")
        tdir = pasta / f"corte_{i:02d}"
        tdir.mkdir(exist_ok=True)
        trecho = tdir / "trecho.mp4"
        if trecho.exists() and not tem_video(trecho):
            trecho.unlink()
        if not trecho.exists():
            baixar_trecho(pasta, info["url"], s, e, trecho)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", str(trecho)], capture_output=True, text=True).stdout.strip())
        print("      procurando a câmera do streamer…")
        W, H, rosto = achar_camera(trecho)
        print("      câmera achada" if rosto is not None else "      sem câmera: jogo inteiro com fundo desfocado")
        print("      legenda palavra por palavra…")
        palavras = palavras_do_trecho(trecho, idioma, modelo_legenda)
        bips = [(max(0, s - 0.05), e + 0.20) for s, e, w in palavras if eh_palavrao(w)]
        palavras = censurar(palavras)
        escrever_ass(tdir / "legenda.ass", m.get("titulo", ""), palavras, dur, rosto is not None)
        fc = filtro(W, H, rosto)
        mapa_a = "0:a?"
        if bips:
            mudo = ",".join([f"volume=0:enable='between(t,{s:.2f},{e:.2f})'" for s, e in bips])
            ligado = "+".join([f"between(t,{s:.2f},{e:.2f})" for s, e in bips])
            fc += (f";[0:a]{mudo}[am];aevalsrc='sin(2*PI*950*t)':s=44100:d={dur:.2f}[bip0];"
                   f"[bip0]volume='{ligado}':eval=frame[bip];[am][bip]amix=inputs=2:normalize=0[a]")
            mapa_a = "[a]"
            print(f"      {len(bips)} palavrões censurados com 'pi'")
        saida = destino / f"corte_{i:02d}.mp4"
        rodar(["ffmpeg", "-y", "-loglevel", "error", "-i", "trecho.mp4", "-filter_complex",
               fc, "-map", "[v]", "-map", mapa_a, "-c:v", "libx264", "-preset", "medium",
               "-crf", "19", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
               str(saida.resolve())], cwd=tdir)
        post = (f"{m.get('titulo', '')}\n\n{m.get('post', '').strip()}\n\n"
                f"Corte da live de {info.get('uploader') or info.get('channel')}: {info.get('webpage_url') or info['url']}\n")
        saida.with_suffix(".txt").write_text(post, encoding="utf-8")
        feitos.append(saida)
        print(f"      PRONTO: {saida}")
    print(f"\n{len(feitos)} cortes prontos pra postar em {destino}")
    return feitos
