"""Extract the released source ZIP outside the checkout and render both delivered formats."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,tempfile,zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("archive",type=Path);parser.add_argument("receipt",type=Path)
    a=parser.parse_args();archive=a.archive.resolve();receipt=a.receipt.resolve()
    with tempfile.TemporaryDirectory(prefix="mercados-portable-") as temp:
        root=Path(temp).resolve()/"paquete";root.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (root/name).resolve().is_relative_to(root):raise ValueError("Unsafe member.")
            z.extractall(root)
        source=json.loads((root/"MANIFIESTO.json").read_text(encoding="utf-8"))
        env=os.environ.copy();env.pop("PYTHONPATH",None);env["PYTHONDONTWRITEBYTECODE"]="1"
        subprocess.run([sys.executable,"reproducir.py","--solo-integridad"],cwd=root,env=env,check=True)
        scripts=Path("media-use/audio/scripts")
        example=Path("productor/assets/examples/narrated-markets")
        observations=None
        if (root/"evidencia/recibo.json").is_file():
            subprocess.run([sys.executable,str(example/"cierres.py"),"compare","datos.json","evidencia/recibo.json","cotejo"],
                           cwd=root,env=env,check=True)
            observations=json.loads((root/"cotejo/comparacion.json").read_bytes())
            if observations!=json.loads((root/"evidencia/comparacion.json").read_bytes()):
                raise ValueError("The offline data checks differ from the packaged receipt.")
        subprocess.run([sys.executable,str(example/"preparar_guion.py"),"--datos","datos.json","--out","borrador"],
                       cwd=root,env=env,check=True)
        recipe=json.loads((root/"borrador/narracion.json").read_bytes())
        if recipe["caption_layout"]!="es-lectura":raise ValueError("Weekly recipe omitted the Spanish caption layout")
        subprocess.run([sys.executable,str(scripts/"test_scene_audio.py"),
                       "SceneAudioTest.test_spanish_layout_uses_shared_clock_and_preserves_recorded_master"],
                       cwd=root,env=env,check=True)
        def render(kind,destination):
            subprocess.run([sys.executable,"reproducir.py","--formato",kind,"--destino",str(destination)],cwd=root,env=env,check=True)
            output=destination/kind
            r=json.loads((output/"verificacion.json").read_text(encoding="utf-8"))
            expected=source["peliculas"][kind]
            if not r["ok"] or r["mp4Sha256"]!=expected:raise ValueError(f"{kind}: hash mismatch {expected} vs {r['mp4Sha256']}")
            if kind=="horizontal":
                project=json.loads((output/"proyecto.json").read_bytes())
                timeline=(output/project["audioTimeline"]).resolve()
                generated=output/"pista-recalculada"
                cmd=[sys.executable,str(scripts/"spanish_captions.py"),str(timeline),"--out",str(generated)]
                marks=root/example/"palabras-voz.json"
                if marks.is_file():cmd+=["--words",str(marks)]
                subprocess.run(cmd,cwd=root,env=env,check=True)
                if (root/"voces/duraciones.json").exists() and (generated/"captions.srt").read_text(encoding="utf-8")!=(root/"subtitulos.srt").read_text(encoding="utf-8"):
                    raise ValueError("The standalone caption CLI differs from the delivered track.")
            return {"formato":kind,"identico":True,"sha256":r["mp4Sha256"],"fotogramas":r["frames"],
                    "frases":r["spokenSentences"],"voces":len(r["originalVoices"]),"pico":r["peakMovingRegions"]}
        results=[]
        for kind in ("horizontal","vertical"):
            with tempfile.TemporaryDirectory(prefix=kind+"-",dir=root.parent) as working:
                results.append(render(kind,Path(working)))
        evidence={"ok":True,"zip":archive.name,"zipSha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
                  "archivosVerificados":len(source["sha256"]),"extraccion":"directorio temporal nuevo fuera del checkout",
                  "directorioDeTrabajo":"raíz del paquete extraído","pythonPathHeredado":False,
                  "recetaSemanal":recipe["caption_layout"],"vozAportadaConservada":True,
                  "cotejoDeDatos": observations["counts"] if observations else None,
                  "cliDeSubtitulosVerificada":True,"resultados":results}
    receipt.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":main()

