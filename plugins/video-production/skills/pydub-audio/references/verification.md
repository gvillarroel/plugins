# Verification and delivery

Compare decoded output against the requested duration, channels and sample
rate, plus sensible sample peak. Use PCM for exact-duration checks; compressed
formats can introduce padding or encoder delay. Keep a WAV master and check
lossy delivery with ffprobe and a decode round trip.

Sample peak and RMS dBFS do not establish LUFS, true peak, absence of audible
clicks, intelligibility or artistic quality. When available, listen at the cuts,
crossfades, ducking boundaries and end; record when listening was unavailable.

For a LUFS delivery contract, measure with FFmpeg's `loudnorm` filter, retain
the first-pass integrated loudness/range/true-peak/threshold/offset, and apply a
second pass with the measured parameters. Preserve the intended output rate:
dynamic mode can internally upsample. Independently measure the encoded result
and compare the user's tolerance. Do not label peak normalization as LUFS.
Use [FFmpeg's loudnorm documentation](https://ffmpeg.org/ffmpeg-filters.html#loudnorm)
for current filter options and linear-mode conditions.

For a batch, give each render its own output and report; collect successful
hashes and explicit failures. A process returning success is insufficient if
the requested file is absent, empty, unplayable or outside the requested path.
