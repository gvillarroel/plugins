# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2", "numpy>=2,<3", "av>=18,<20"]
# ///
"""Create the portable sources for a reviewed weekly markets film."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from playwright.sync_api import Error as BrowserError, sync_playwright
from publicar import digest, locked, previous_hashes, recover

HERE=Path(__file__).resolve().parent
TOOLS=HERE.parents[2]/"scripts"
DEPENDENCIES={"playwright":">=1.51,<2","numpy":">=2,<3","av":">=18,<20"}


def enc(data):
    return (json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode("utf-8")


def package(out,audio,target,receipt=None,portrait=None):
    out=out.resolve()
    portrait=(portrait or out/"vertical").resolve()
    if target.suffix.lower()!=".zip":
        raise ValueError("Choose a .zip filename for the portable source package.")
    if portrait==out:
        raise ValueError("Choose two distinct render directories for the horizontal and vertical films.")
    first,second=sorted((out,portrait))
    with locked(first), locked(second):
        recover(out)
        recover(portrait)
        return package_locked(out,audio,target,receipt,portrait)


def reviewed_format(folder,portrait):
    for name,expected in previous_hashes(folder).items():
        if digest(folder/name)!=expected:
            raise ValueError(f"Reviewed source changed before packaging: {folder/name}")
    qa=json.loads((folder/"verificacion.json").read_bytes())
    if not qa["ok"] or digest(folder/"mercados.mp4")!=qa["mp4Sha256"]:
        raise ValueError("Review both final exports before packaging them.")
    project=json.loads((folder/"proyecto.json").read_bytes())
    width,height=project["width"],project["height"]
    if [width,height]!=qa["viewport"] or (height>width)!=portrait or height==width:
        raise ValueError(f"The reviewed render has the wrong orientation: {folder}")
    timeline=(folder/project["audioTimeline"]).resolve()
    clock=json.loads(timeline.read_bytes())
    shots=json.loads((folder/"guion-visual.json").read_bytes())
    recipe=[{k:v for k,v in row.items() if k!="focus"} for row in shots]
    inputs={"datos":digest(folder/"datos.json"),"palabras":digest(folder/"palabras-voz.json"),"recipe":recipe,
            "timeline":clock,"master":digest(timeline.parent/clock["master"]["file"]),
            "captions":digest(timeline.parent/"captions.srt")}
    return qa["mp4Sha256"],inputs


def package_locked(out,audio,target,receipt,portrait):
    horizontal,reference=reviewed_format(out,False)
    vertical,other=reviewed_format(portrait,True)
    if reference!=other:raise ValueError("The two reviewed formats belong to different episode revisions.")
    films={"horizontal":horizontal,"vertical":vertical}
    files={}
    def copy(path,name):files[name]=path.read_bytes()
    for name in ("generar.py","publicar.py","verificar.py","validar.py","datos.schema.json","escena.html","test_narrated_markets.py",
                 "preparar_guion.py","test_guion_semanal.py","test_validar.py","test_publicar.py","test_subtitulos.py",
                 "cierres.py","test_cierres.py"):
        copy(HERE/name,"productor/assets/examples/narrated-markets/"+name)
    for name in ("scene_audio.py","spanish_captions.py","test_scene_audio.py"):
        copy(HERE.parents[3]/"media-use"/"audio"/"scripts"/name,"media-use/audio/scripts/"+name)
    generated=json.loads((out/"guion-visual.json").read_text(encoding="utf-8"))
    if reference["palabras"]:
        copy(out/'palabras-voz.json','productor/assets/examples/narrated-markets/palabras-voz.json')
    derived={"start","end","stop","focus"}
    files["productor/assets/examples/narrated-markets/guion-visual.json"]=enc(
        [{k:v for k,v in row.items() if k not in derived} for row in generated])
    for name in ("compose_narrated.py","check_narrated_export.py","review_attention.py","cadence_scan.py",
                 "caption_tracks.py","review_solid_regions.py","check_audio_channels.py","open_captions.py"):
        copy(TOOLS/name,"productor/scripts/"+name)
    for name in ("space-grotesk.ttf","OFL.txt"):
        copy(TOOLS.parent/"assets/fonts"/name,"productor/assets/fonts/"+name)
    copy(TOOLS.parent/"assets/palettes/video-colors.json","productor/assets/palettes/video-colors.json")
    copy(TOOLS.parent/"assets/runtime/review-solid-paints.js","productor/assets/runtime/review-solid-paints.js")
    copy(HERE/"reproducir.py","reproducir.py")
    copy(out/"datos.json","datos.json")
    project=json.loads((out/"proyecto.json").read_bytes())
    timeline=(out/project["audioTimeline"]).resolve()
    copy(timeline.parent/"captions.srt","subtitulos.srt")
    if (audio/"duraciones.json").is_file() and not (audio/"timeline.json").is_file():
        copy(audio/"duraciones.json","voces/duraciones.json")
        copy(audio/"narracion.json","voces/narracion.json")
        measured=json.loads(files["voces/duraciones.json"].decode("utf-8-sig"))
        for entry in measured["scenes"]:
            if digest(audio/entry["file"])!=entry["sha256"]:
                raise ValueError("The supplied voice recording differs from its measured metadata.")
        if [s["sha256"] for s in measured["scenes"]]!=[s["original_voice_sha256"] for s in reference["timeline"]["scenes"]]:
            raise ValueError("The supplied recordings belong to a different audio timeline.")
        audio_files=[s["file"] for s in measured["scenes"]]
    else:
        measured=json.loads(timeline.read_bytes())
        audio=timeline.parent
        copy(timeline,"voces/timeline.json")
        copy(audio/"captions.srt","voces/captions.srt")
        audio_files=[measured["master"]["file"]]+[s.get("voice_file") or s.get("voice")
                      for s in measured["scenes"] if s.get("voice_file") or s.get("voice")]
    for name in audio_files:
        path=(audio/name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(audio.resolve()) or path.suffix.lower()!=".wav":
            raise ValueError("Invalid original voice path")
        copy(path,"voces/"+Path(name).as_posix())
    versions={name:version(name) for name in DEPENDENCIES}
    python_minor=f"{sys.version_info.major}.{sys.version_info.minor}"
    requirements=[]
    for name,bounds in DEPENDENCIES.items():
        requirements.extend([f'{name}=={versions[name]}; python_version == "{python_minor}"',
                             f'{name}{bounds}; python_version != "{python_minor}"'])
    files["requirements.txt"]=("\n".join(requirements)+"\n").encode()
    versions.update(python=sys.version.split()[0],ffmpeg=subprocess.check_output(["ffmpeg","-version"]).decode().splitlines()[0],
                    ffprobe=subprocess.check_output(["ffprobe","-version"]).decode().splitlines()[0])
    with sync_playwright() as runtime:
        try: browser=runtime.chromium.launch()
        except BrowserError as exc:
            if os.name!="nt" or "Executable doesn't exist" not in str(exc):raise
            browser=runtime.chromium.launch(channel="msedge")
        versions["chromium"]=browser.version
        browser.close()
    data=json.loads(files["datos.json"])
    cited=["# Datos y fuentes","","Cierres de "+data["inicio"]+" y "+data["fin"]+". Los índices se expresan en puntos, el oro en USD por onza troy, bitcoin en USD por BTC y TLT en USD por participación. La tasa del Tesoro es anual. Los días de bitcoin corresponden a cierres UTC.",""]
    if receipt is not None:
        copy(receipt,"evidencia/recibo.json")
        with tempfile.TemporaryDirectory() as temp:
            validation=Path(temp)
            (validation/"datos.json").write_bytes(files["datos.json"])
            (validation/"recibo.json").write_bytes(files["evidencia/recibo.json"])
            subprocess.run([sys.executable,"-B",str(HERE/"cierres.py"),"compare","datos.json","recibo.json","cotejo"],
                           cwd=validation,check=True)
            copy(validation/"cotejo/comparacion.json","evidencia/comparacion.json")
        counts=json.loads(files["evidencia/comparacion.json"])["counts"]
        cited.extend([f"El recibo congelado permite cotejar {counts['match']} observaciones con sus filas publicadas. "
                      "[Recibo y filas originales](evidencia/recibo.json) · [Comparación por fecha](evidencia/comparacion.json)",""])
    for k,s in data["series"].items():
        urls=s.get("fuentes",[])
        cited.append(f"- {s['nombre']} ({s['unidad']}): "+ " · ".join(f"[Fuente {i+1}]({url})" for i,url in enumerate(urls)))
    cited+=["","El ejemplo de cupón fijo utiliza la relación entre rendimiento exigido y precio de mercado. [Investor.gov, SEC](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-86)",
            "","Motor y voz originales: "+str(measured.get("engine","audio medido"))+" · "+str(measured.get("voice","voz suministrada"))+(". [Ficha del modelo]("+measured["model_card"]+")" if measured.get("model_card") else "")]
    files["FUENTES.md"]=("\n".join(cited)+"\n").encode("utf-8")
    readme="""# Mercados semanales · paquete de reproducción

Extrae el ZIP en cualquier carpeta. El paquete contiene los cierres diarios, las fuentes, los archivos originales de voz o máster, sus frases y tiempos, los subtítulos entregados, la receta y el código de render y revisión. La reproducción usa el máster suministrado o lo recompone a partir de las grabaciones medidas. La receta carga todo mediante rutas relativas al paquete.

Necesitas Python 3.11 o posterior, FFmpeg con libx264, FFprobe, Playwright, Chromium, NumPy y PyAV. requirements.txt fija las versiones usadas para la misma versión mayor y menor de Python. Con otro Python el instalador selecciona versiones compatibles dentro de los intervalos del productor. Para repetir la tipografía de la entrega usa Arial y Georgia. MANIFIESTO.json identifica las versiones de la máquina de referencia y los dos MP4 originales por SHA-256.

```text
python -m pip install -r requirements.txt
python -m playwright install chromium
python reproducir.py --solo-integridad
python productor/assets/examples/narrated-markets/test_narrated_markets.py
python reproducir.py --formato ambos
```

Con las dependencias disponibles, el render y las verificaciones funcionan sin conexión. Para usar Edge en Windows añade `--browser msedge`. `--destino` acepta cualquier directorio de trabajo. Los MP4, los datos normalizados, los gráficos, los subtítulos, los tiempos y el informe de cada formato quedan en reconstruido/horizontal y reconstruido/vertical. El verificador comprueba las frases grabadas, el PCM original, el AAC, los valores de ambas fechas, la atención segundo a segundo y una imagen decodificada por frase. La coincidencia byte a byte también depende de la versión del navegador, el codificador y las fuentes instaladas.

Para preparar otra semana, usa cierres.py para recoger y cotejar los cierres, revisa las fuentes y ejecuta los comandos siguientes desde la raíz de la extracción. La nueva receta activa la partición española de subtítulos. Revisa los dos guiones antes de sintetizar. El productor de voz declara sus dependencias de Piper en el propio archivo. La opción --offline usa un modelo ya instalado.

```text
python productor/assets/examples/narrated-markets/preparar_guion.py --datos otra-semana.json --out borrador
uv run --python 3.13 --script media-use/audio/scripts/scene_audio.py borrador/narracion.json --out audio-nuevo --offline
python productor/assets/examples/narrated-markets/generar.py --datos otra-semana.json --audio audio-nuevo --guion-visual borrador/guion-visual.json --out otra-pelicula
```

Un máster previamente grabado con su timeline admite una pista de lectura nueva con `python media-use/audio/scripts/spanish_captions.py audio-nuevo/timeline.json --out pista-nueva`. El destino debe ser nuevo. La opción --words añade marcas de palabra verificables por la huella del WAV. El informe distingue los límites de frase medidos, los inicios reconocidos y los tiempos interpolados. Para componer con la pista que has elegido, coloca su captions.srt junto al máster y su timeline en una copia del audio. Las atribuciones del episodio están en FUENTES.md.
"""
    files["LEEME.md"]=readme.encode("utf-8")
    files["LEEME.md"]+=("\nPara obtener una copia con subtítulos visibles de forma permanente, instala la dependencia opcional "
                        "Pillow y ejecuta `python productor/scripts/open_captions.py reconstruido/vertical/mercados.mp4 "
                        "mercados-movil-con-subtitulos.mp4 --language spa`. El archivo de salida debe ser nuevo. "
                        "La fuente incluida se distribuye con su licencia en productor/assets/fonts/OFL.txt.\n").encode("utf-8")
    if receipt is not None:
        files["LEEME.md"]+=("\nPara repetir el cotejo de los cierres sin conexión desde la extracción, ejecuta "
                            "`python productor/assets/examples/narrated-markets/cierres.py compare datos.json "
                            "evidencia/recibo.json nuevo-cotejo`. El informe registra la fila de cada cierre y su fuente.\n").encode("utf-8")
    sha={name:hashlib.sha256(content).hexdigest() for name,content in sorted(files.items())}
    files["MANIFIESTO.json"]=enc({"esquema":1,"fechaInicial":data["inicio"],"fechaFinal":data["fin"],"versiones":versions,"peliculas":films,"sha256":sha})
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        archive=Path(temp)/"fuentes.zip"
        with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
            for name,content in sorted(files.items()):
                entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
                bundle.writestr(entry,content,compresslevel=9)
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() or any(hashlib.sha256(bundle.read(k)).hexdigest()!=v for k,v in sha.items()):
                raise RuntimeError("The ZIP does not match its source inventory.")
        archive.replace(target)
    return {"archivo":target.name,"bytes":target.stat().st_size,"miembros":len(files),"sha256":hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--vertical",type=Path,help="Carpeta del render vertical. Por omisión se usa <out>/vertical.")
    p.add_argument("--audio",type=Path,required=True);p.add_argument("--zip",type=Path,required=True)
    p.add_argument("--recibo",type=Path,help="Recibo opcional de cierres.py con las filas originales de esta semana")
    a=p.parse_args();print(json.dumps(package(a.out,a.audio,a.zip,a.recibo,a.vertical),ensure_ascii=False))

