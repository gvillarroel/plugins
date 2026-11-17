# Environment and diagnosis

The bundled helper uses `uv` script dependencies: PyDub 0.25.1 and the
conditional `audioop-lts` compatibility package on Python 3.13 or newer.
It does not install system executables or modify the user's environment.

Run the helper's `doctor` command first. `ffmpeg` and `ffprobe` must be executable
on PATH for compressed formats and container inspection. A Python wrapper named
`ffmpeg` does not install those executables. Use the system's normal package
manager when installation is in scope, then rerun diagnosis. Do not change a
global PATH as a side effect of a single edit.

PyDub supports ordinary PCM WAV loading/export without FFmpeg. Decode failures
on compressed audio need the actual FFmpeg stderr, file identity and installed
codec support. Enable the `pydub.converter` logger in custom scripts when needed;
send diagnostics to stderr in an MCP server.

Inspect the container instead of inferring a codec from an extension:

```sh
ffprobe -v error -show_streams -show_format -of json input.m4a
```

Use argument arrays and `shell=False` for external commands. Close the handle
returned by `segment.export(...)`. Avoid playback APIs on headless systems;
create a deliverable and use an available player for listening.

Sources checked 2026-11-17:

- [PyDub installation and FFmpeg](https://github.com/jiaaro/pydub#installation)
- [PyDub API](https://github.com/jiaaro/pydub/blob/master/API.markdown)
- [Python audioop removal](https://docs.python.org/3/library/audioop.html)
- [audioop-lts](https://pypi.org/project/audioop-lts/)
