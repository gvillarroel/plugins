"""Publish a local market episode only after its candidate passes the final check."""
from contextlib import contextmanager, nullcontext
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import tempfile

MANIFEST="publicacion.json"
FILES={"datos.json","atencion.json","guion-visual.json","palabras-voz.json","proyecto.json",
       "cotejo-fuentes.json",
       "pre-render.json","composicion.json","post-export.json","verificacion.json","escena.html",
       "mercados.mp4","frases.jpg","audio/master.wav","audio/timeline.json","audio/captions.srt","audio/cortes-subtitulos.json",
       *(f"vista-{n}.png" for n in (0,4,10,12))}
OPTIONAL={"palabras-voz.json","audio/cortes-subtitulos.json","cotejo-fuentes.json",*(f"vista-{n}.png" for n in (0,4,10,12))}


def digest(p):
    if not p.exists(): return None
    if not p.is_file(): raise ValueError(f"Expected a file at {p}")
    with p.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()


def write_json(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write("\n");f.flush();os.fsync(f.fileno())


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


@contextmanager
def locked(target):
    # The kernel releases the lock when the process exits, including after a crash.
    path=target.parent/("."+target.name+".line-world.lock")
    with path.open("a+b") as f:
        if f.tell()==0: f.write(b"0");f.flush()
        f.seek(0)
        if os.name=="nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError as e:
                    if e.errno not in (errno.EACCES,errno.EDEADLK): raise
                    time.sleep(.1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX)
        yield


def output_path(root,name):
    if name not in FILES|{MANIFEST}:
        raise ValueError(f"Unrecognized managed filename {name}")
    p=root/name
    if p.is_symlink() or not p.resolve().is_relative_to(root):
        raise ValueError(f"Cannot replace an output link or a path outside the episode: {p}")
    return p


def workspace(target):
    return target.parent/("."+target.name+".line-world-publicacion")


def cleanup(target,work):
    # Never recursively remove an unknown directory, junction or symlink.
    if (work.resolve()!=workspace(target) or work.is_symlink() or
            (getattr(work,"is_junction",lambda:False)()) or read(work/"owner.json")!={"episode":str(target)}):
        raise ValueError(f"Unrecognized transaction directory {work}")
    shutil.rmtree(work)


def recover(target):
    work=workspace(target)
    if not work.exists(): return
    if not (work/"owner.json").exists():
        raise ValueError(f"Unrecognized transaction directory {work}")
    if work.resolve()!=work or read(work/"owner.json")!={"episode":str(target)}:
        raise ValueError(f"Unrecognized transaction directory {work}")
    journal=work/"active.json"
    if journal.is_file():
        candidate=work/"candidate"
        if candidate.is_dir() and candidate.resolve()==candidate and not candidate.is_symlink():
            shutil.rmtree(candidate)  # Release space before restoring on a full volume.
        record=read(journal)
        for name,(old,new) in reversed(list(record["files"].items())):
            final=output_path(target,name)
            present=digest(final)
            if present==old:continue
            # An independent editor can replace a file after a crash. Keep that
            # edit in place when it matches neither revision recorded by us.
            if present!=new:continue
            if old is None: final.unlink(missing_ok=True)
            else:
                backup=work/"prior"/name
                if digest(backup)!=old:raise ValueError(f"Cannot recover {final} from its backup")
                os.replace(backup,final)
        for directory in record["newDirectories"]:
            if directory!="audio": raise ValueError(f"Unexpected staged directory {directory}")
            parent=output_path(target,"audio/master.wav").parent
            if parent.is_dir() and not any(parent.iterdir()):parent.rmdir()
        journal.rename(work/"rolled-back.json")
    cleanup(target,work)


def previous_hashes(target):
    receipt=target/MANIFEST
    if receipt.is_file():
        data=read(receipt)
        if data.get("schema")!=1 or not isinstance(data.get("files"),dict) or not set(data["files"])<=FILES:
            raise ValueError(f"Invalid episode inventory {receipt}")
        return data["files"]
    # Legacy episodes have no publication manifest. Their existing QA still
    # identifies the last rendered project, its source files, and the movie.
    known={}
    composition=target/"composicion.json"
    if composition.is_file():
        inputs=read(composition).get("inputs",{})
        original=next((Path(k).parent for k in inputs if Path(k).name=="proyecto.json"),target)
        for absolute,sha in inputs.items():
            path=Path(absolute)
            if path.is_absolute() and path.is_relative_to(original):
                name=path.relative_to(original).as_posix()
                if name in FILES:known[name]=sha
    verification=target/"verificacion.json"
    if verification.is_file() and read(verification).get("mp4Sha256"):
        known["mercados.mp4"]=read(verification)["mp4Sha256"]
    # A copied historical episode retains its original absolute receipt paths.
    # Its verified HTML also carries the source JSON and generated shot list.
    html=target/"escena.html"
    start='<script type="application/json" id="payload">'
    if known.get("escena.html") and digest(html)==known["escena.html"]:
        contents=html.read_text(encoding="utf-8")
        if start in contents:
            payload=json.loads(contents.split(start,1)[1].split("</script>",1)[0])
            for name,key in (("datos.json","data"),("guion-visual.json","shots")):
                path=target/name
                if path.is_file() and read(path)==payload.get(key):known[name]=digest(path)
    return known


def legacy_previews(target,known):
    # Old receipts lack hashes for thumbnails. Recreate their encoded bytes from
    # the previously verified movie to distinguish a generated file from an edit.
    movie=target/"mercados.mp4"
    if not known.get("guion-visual.json") or not known.get("mercados.mp4") or digest(movie)!=known["mercados.mp4"]:return
    shots=read(target/"guion-visual.json")
    if not shots:return
    picks=[round((shot["stop"]+shot["end"]-1)/2) for shot in shots]
    rate=read(target/"proyecto.json")["fps"]
    columns=min(3,len(picks));rows=math.ceil(len(picks)/columns)
    select="+".join(f"eq(n\\,{frame})" for frame in picks)
    for name,flags,codec in [
        ("frases.jpg",["-i",str(movie),"-vf",f"select={select},scale=390:-2:flags=lanczos,tile={columns}x{rows}"],"mjpeg"),
        *((f"vista-{i}.png",["-ss",str(picks[i]/rate),"-i",str(movie)],"png") for i in (0,4,10,12) if i<len(picks))]:
        if (target/name).is_file():
            picture=subprocess.check_output(["ffmpeg","-v","error",*flags,"-frames:v","1","-f","image2pipe","-c:v",codec,"-"])
            known[name]=hashlib.sha256(picture).hexdigest()


def commit(target,work,stage,initial,prior,protected):
    generated={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob("*") if p.is_file()}
    if not set(generated)<=FILES:raise ValueError("The candidate contains unexpected generated files")
    if target.is_dir() and not (target/MANIFEST).is_file():legacy_previews(target,prior)
    stale=(set(prior)&OPTIONAL)-set(generated)
    changes={k:v for k,v in generated.items() if initial[k]!=v}
    changes.update({k:None for k in stale if initial[k]==prior[k] and initial[k] is not None})
    write_json(stage/MANIFEST,{"schema":1,"files":generated})
    changes[MANIFEST]=digest(stage/MANIFEST)
    # Older producers did not record every derived report, preview or thumbnail.
    # Their source files and audio must still match a trustworthy prior hash.
    legacy=not (target/MANIFEST).is_file() and bool(prior)
    legacy_outputs={"composicion.json","pre-render.json","post-export.json","verificacion.json"}
    # Detect a replacement or edit made while Chromium/FFmpeg was working, even
    # when the candidate would otherwise reuse that same file without writing.
    for name in set(generated)|set(changes):
        final=target/name
        if digest(final)!=initial[name]:raise ValueError(f"File changed during rendering: {final}")
        if name in changes:final=output_path(target,name)
        unowned=(name!=MANIFEST and name not in prior and not (legacy and name in legacy_outputs))
        changed_prior=name in prior and initial[name]!=prior[name]
        if name in changes and (final.resolve() in protected or (initial[name] is not None and (unowned or changed_prior))):
            raise ValueError(f"Edited input or output preserved at {final}; publish the revised episode to a new --out.")
    if not target.exists():
        os.replace(stage,target)
        return
    new_dirs=set()
    backup_root=work/"prior"
    for name in changes:
        final=output_path(target,name)
        if not final.parent.is_dir():new_dirs.add(final.parent.relative_to(target).as_posix())
        if initial[name] is None:continue
        backup=backup_root/name;backup.parent.mkdir(parents=True,exist_ok=True)
        try: os.link(final,backup)
        except OSError: shutil.copy2(final,backup)
    # Everything needed for rollback is on disk before the first replacement.
    prepared=work/"prepared.json"
    write_json(prepared,{"files":{k:[initial[k],v] for k,v in changes.items()},"newDirectories":sorted(new_dirs)})
    os.replace(prepared,work/"active.json")
    for directory in new_dirs:(target/directory).mkdir()
    for name,new in changes.items():
        final=output_path(target,name)
        if digest(final)!=initial[name]:raise ValueError(f"File changed during publication: {final}")
        if new is None: final.unlink()
        else: os.replace(stage/name,final)
    os.replace(work/"active.json",work/"committed.json")


def publish(out,preflight,build):
    out=out.resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    with locked(out):
        recover(out)
        target=out/"preflight" if preflight and (out/"mercados.mp4").is_file() else out
        with locked(target) if target!=out else nullcontext():
            if target!=out:recover(target)
            work=workspace(target)
            # Atomically install the ownership marker even when a full disk
            # prevents us from writing the first bytes of a transaction.
            with tempfile.TemporaryDirectory(prefix=".line-world-init-",dir=target.parent) as init:
                owned=Path(init)/"transaction";owned.mkdir()
                write_json(owned/"owner.json",{"episode":str(target)})
                os.replace(owned,work)
            try:
                stage=work/"candidate";stage.mkdir()
                initial={name:digest(target/name) for name in FILES|{MANIFEST}}
                prior=previous_hashes(target)
                protected=build(stage,target)
                commit(target,work,stage,initial,prior,protected)
            except BaseException:
                recover(target)
                raise
            cleanup(target,work)
    return target

