# Noto Sans SC (PDF export subset)

CJK fallback font for PDF export, loaded only when a page is exported. Latin
text keeps using Inter; these files supply the glyphs Inter lacks.

- Source: Noto Sans SC, SIL Open Font License 1.1 (see `OFL.txt`).
- Weights: Regular (400) and Bold (700), instanced from the variable font at
  `google/fonts/ofl/notosanssc/NotoSansSC[wght].ttf`.
- Charset: GBK-encodable ideographs (U+3400–U+9FFF range) plus CJK punctuation,
  full-width forms, general punctuation and Latin-1, stored as TTF; WOFF costs a slow JS zlib inflate on every export.
  About 7.1 MB per weight.

Regenerate (needs `uv` and a local copy of the variable font):

```bash
uv run --with fonttools python - <<'PY'
import subprocess
for weight, name in (("400", "Regular"), ("700", "Bold")):
    subprocess.run(["fonttools", "varLib.instancer", "NotoSansSC[wght].ttf",
                    f"wght={weight}", "--update-name-table", "-o", f"static-{name}.ttf"], check=True)

chars = []
for cp in range(0x3400, 0xA000):
    try:
        chr(cp).encode("gbk")
        chars.append(chr(cp))
    except UnicodeEncodeError:
        pass
open("gbk-chars.txt", "w", encoding="utf-8").write("".join(chars))

for name in ("Regular", "Bold"):
    subprocess.run(["pyftsubset", f"static-{name}.ttf", f"--output-file={name.lower()}.ttf",
                    "--text-file=gbk-chars.txt",
                    "--unicodes=U+0020-007E,U+00A0-00FF,U+2000-206F,U+3000-303F,U+FF00-FFEF",
                    "--layout-features=*", "--notdef-glyph", "--notdef-outline",
                    "--recommended-glyphs", "--name-IDs=*", "--name-legacy", "--name-languages=*"],
                   check=True)
PY
```
