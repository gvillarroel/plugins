"""Compare every decoded presentation frame to its independently rendered recipe state."""
import io
import json
from fractions import Fraction
import math
import subprocess
from PIL import Image, ImageChops, ImageStat

from motion_recipe import require


def inspect_clock(path, plan):
    fields = "stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time"
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                     "-show_entries", fields, "-of", "json", str(path)])
    result = json.loads(probe)
    streams = result.get("streams", [])
    require(len(streams) == 1, "Falta la pista de imagen")
    stream = streams[0]
    require((stream["width"], stream["height"]) == (plan["width"], plan["height"]),
            "La resolución del MP4 difiere de la receta")
    fps = plan["fps"]
    require(Fraction(stream["avg_frame_rate"]) == fps, "La cadencia del MP4 difiere de la receta")
    frames = result.get("frames", [])
    require(len(frames) == plan["frames"], "El número de fotogramas del MP4 difiere de la receta")
    for i, frame in enumerate(frames):
        pts = float(frame.get("best_effort_timestamp_time", "nan"))
        require(math.isfinite(pts) and abs(pts-i/fps) < .5/fps,
                f"El tiempo de presentación del fotograma {i} difiere de la receta")


def verify_movie(path, plan, png_for_frame):
    inspect_clock(path, plan)
    w, h = plan["width"], plan["height"]
    scale = min(192/w, 128/h, 1)
    size = (max(1,round(w*scale)), max(1,round(h*scale)))
    # Area-averaged RGB keeps localized ink visible on white and tolerates codec noise.
    sw, sh = size
    grid = (max(1,round(sw/8)), max(1,round(sh/8)))
    cmd = ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0",
           "-vf", f"scale={sw}:{sh}:flags=area", "-fps_mode", "passthrough",
           "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    scenes = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        try:
            for scene in plan["scenes"]:
                peak_mean = peak_local = 0
                worst_frame = scene["start"]
                hold = scene["start"] + scene["bridge"] + scene["reveal"]
                for frame in range(scene["start"], scene["end"]):
                    raw = proc.stdout.read(sw*sh*3)
                    require(len(raw)==sw*sh*3, f"Imagen decodificada incompleta en el fotograma {frame}")
                    if frame <= hold or scene.get("video_assets"):
                        with Image.open(io.BytesIO(png_for_frame(frame))) as source:
                            expected = source.convert("RGB").resize(size, Image.Resampling.BOX)
                    actual = Image.frombytes("RGB", size, raw)
                    difference = ImageChops.difference(expected, actual)
                    mean = sum(ImageStat.Stat(difference).mean)/3
                    local = difference.convert("L").resize(grid, Image.Resampling.BOX).getextrema()[1]
                    if local > peak_local:
                        peak_local, worst_frame = local, frame
                    peak_mean = max(peak_mean, mean)
                    require(mean <= 5 and local <= 23,
                            f"{scene['id']} @ {frame/plan['fps']:.3f} s (fotograma {frame}): "
                            f"el MP4 no reproduce la receta; error RGB medio {mean:.1f}, local {local}")
                scenes.append({"id":scene["id"],"checked_frames":scene["end"]-scene["start"],
                               "max_mean_rgb_error":round(peak_mean,3),"max_local_luma_error":peak_local,
                               "worst_local_frame":worst_frame})
            require(not proc.stdout.read(1), "El MP4 contiene fotogramas extra")
            require(proc.wait() == 0, "Falló la decodificación del MP4")
        finally:
            if proc.poll() is None: proc.kill()
    return {"frames":plan["frames"],"comparison_size":list(size),"tile_grid":list(grid),
            "max_allowed_mean_rgb_error":5,"max_allowed_local_luma_error":23,"scenes":scenes}
