"""Rebuild the narrated films using only the members of this extracted source package."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys


ROOT=Path(__file__).resolve().parent


def digest(p):
    with p.open("rb") as s:return hashlib.file_digest(s,"sha256").hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formato",choices=("horizontal","vertical","ambos"),default="ambos")
    parser.add_argument("--destino",type=Path,default=ROOT/"reconstruido")
    parser.add_argument("--solo-integridad",action="store_true")
    parser.add_argument("--browser",choices=("msedge","chrome","chromium"))
    args=parser.parse_args()
    inventory=json.loads((ROOT/"MANIFIESTO.json").read_text(encoding="utf-8"))
    for name,want in inventory["sha256"].items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file() or digest(p)!=want:raise ValueError("Invalid member: "+name)
    if args.solo_integridad:
        print(f"OK: {len(inventory['sha256'])} archivos verificados");return
    formats=("horizontal","vertical") if args.formato=="ambos" else (args.formato,)
    for kind in formats:
        destination=args.destino.resolve()/kind
        if destination in (ROOT,ROOT/"voces",ROOT/"productor"): raise ValueError("Use a new output directory.")
        generator=ROOT/"productor/assets/examples/narrated-markets/generar.py"
        args2=[sys.executable,str(generator),"--datos",str(ROOT/"datos.json"),"--audio",str(ROOT/"voces"),
               "--formato",kind,"--out",str(destination)]
        marks=generator.with_name("palabras-voz.json")
        if marks.is_file():args2.extend(["--palabras",str(marks)])
        if (ROOT/"evidencia/recibo.json").is_file():args2.extend(["--recibo",str(ROOT/"evidencia/recibo.json")])
        if args.browser:args2.extend(["--browser",args.browser])
        subprocess.run(args2,check=True,cwd=ROOT)
        actual=digest(destination/"mercados.mp4")
        print(json.dumps({"formato":kind,"sha256":actual,"identico_al_exportado":actual==inventory["peliculas"][kind]}))


if __name__=="__main__":main()

