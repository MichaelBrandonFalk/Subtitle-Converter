from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import html
import re


ALLOWED_VTT_TAGS = {"b", "i", "u", "c", "ruby", "rt", "v", "lang"}
TAG_CAPTURE = re.compile(r"<(/?)([A-Za-z]+)([^>]*)>")
ALLOWED_ANY_TAG = re.compile(r"</?(?:b|i|u|c|ruby|rt|v|lang)(?:[^>]*)>")
VTT_TS_LINE = re.compile(r"^\s*\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
VTT_TS_DECIMAL = re.compile(
    r"^(\s*)(\d{1,2}:\d{2}(?::\d{2})?)(\.\d{1,3})?\s+-->\s+(\d{1,2}:\d{2}(?::\d{2})?)(\.\d{1,3})?(\s.*)?$"
)
VALID_ENTITIES = re.compile(r"&(?!amp;|lt;|gt;|lrm;|rlm;|nbsp;|#\d+;|#x[0-9A-Fa-f]+;)")


@dataclass
class Cue:
    start: float
    end: float
    text: list[str]


def parse_timestamp_vtt(timestamp: str) -> float:
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        hours = "0"
        minutes, seconds = parts

    sec, dot, frac = seconds.partition(".")
    ms = int(frac or "0")
    return int(hours) * 3600 + int(minutes) * 60 + int(sec) + ms / 1000


def parse_timestamp_srt(timestamp: str) -> float:
    time_part, _, frac = timestamp.partition(",")
    hours, minutes, seconds = map(int, time_part.split(":"))
    ms = int(frac or "0")
    return hours * 3600 + minutes * 60 + seconds + ms / 1000


def seconds_to_vtt_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec_float = seconds % 60
    sec = int(sec_float)
    ms = int(round((sec_float - sec) * 1000))
    if ms == 1000:
        ms = 0
        sec += 1
        if sec == 60:
            sec = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    return f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"


def seconds_to_srt_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec_float = seconds % 60
    sec = int(sec_float)
    ms = int(round((sec_float - sec) * 1000))
    if ms == 1000:
        ms = 0
        sec += 1
        if sec == 60:
            sec = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    return f"{hours:02d}:{minutes:02d}:{sec:02d},{ms:03d}"


def strip_formatting(text: str, keep_biu: bool = False) -> str:
    if keep_biu:
        def repl(match: re.Match[str]) -> str:
            tag = match.group(1).lower()
            return match.group(0) if tag in ("i", "/i", "b", "/b", "u", "/u", "br", "/br") else ""

        text = re.sub(r"<\s*/?\s*([^ >/]+)(?:\s+[^>]*)?>", repl, text)
        text = re.sub(r"(?i)<br\s*/?>", "<br/>", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    text = re.sub(r"</?[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def decode_basic_entities(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
        .replace("&lrm;", "")
        .replace("&rlm;", "")
    )


def normalize_vtt_tags(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        slash, name, rest = match.group(1), match.group(2).lower(), match.group(3)
        if name not in ALLOWED_VTT_TAGS:
            return f"&lt;{('/' if slash else '')}{name}{rest}&gt;"
        if slash:
            return f"</{name}>"

        rest_stripped = re.sub(r"\s+", " ", rest or "").strip()
        if name in ("v", "lang"):
            annotation = rest_stripped.replace("<", "").replace(">", "")
            return f"<{name}{(' ' + annotation) if annotation else ''}>"
        if name == "c":
            tokens = [token for token in re.split(r"[\s\.]+", rest_stripped) if token]
            cleaned = [re.sub(r"[^A-Za-z0-9_-]", "", token) for token in tokens]
            classes = [token for token in cleaned if token]
            return f"<c.{'.'.join(classes)}>" if classes else "<c>"
        return f"<{name}>"

    return TAG_CAPTURE.sub(replace, text)


def escape_angles_outside_allowed_tags(text: str) -> str:
    placeholders: list[str] = []

    def store(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"@@TAG{len(placeholders) - 1}@@"

    protected = ALLOWED_ANY_TAG.sub(store, text)
    escaped = protected.replace("<", "&lt;").replace(">", "&gt;")
    for idx, tag in enumerate(placeholders):
        escaped = escaped.replace(f"@@TAG{idx}@@", tag)
    return escaped


def enforce_vtt_tag_context(text: str) -> str:
    out: list[str] = []
    pos = 0
    stack: list[str] = []
    for match in TAG_CAPTURE.finditer(text):
        if match.start() > pos:
            out.append(text[pos:match.start()])
        pos = match.end()

        slash, name = match.group(1), match.group(2).lower()
        if name not in ALLOWED_VTT_TAGS:
            out.append(match.group(0).replace("<", "&lt;").replace(">", "&gt;"))
            continue

        if slash:
            if name in stack:
                while stack and stack[-1] != name:
                    out.append(f"</{stack.pop()}>")
                out.append(f"</{name}>")
                stack.pop()
            else:
                out.append(f"&lt;/{name}&gt;")
            continue

        if name == "rt" and "ruby" not in stack:
            out.append("&lt;rt&gt;")
            continue

        out.append(f"<{name}>")
        stack.append(name)

    out.append(text[pos:])
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def normalize_vtt_blank_lines(vtt_text: str) -> str:
    lines = vtt_text.splitlines()
    out: list[str] = []
    idx = 0

    if idx < len(lines) and lines[idx].strip().upper().startswith("WEBVTT"):
        out.append("WEBVTT")
        idx += 1
        while idx < len(lines) and lines[idx].strip() == "":
            idx += 1
        out.append("")

    for line in lines[idx:]:
        trimmed = line.rstrip()
        if VTT_TS_LINE.match(trimmed) and out and out[-1] != "":
            out.append("")
        out.append(trimmed)
    return "\n".join(out)


def normalize_vtt_timestamp_decimals(vtt_text: str) -> str:
    lines = vtt_text.splitlines()

    def normalize_ms(fragment: str | None) -> str:
        if fragment is None:
            return ".000"
        digits = fragment[1:]
        if len(digits) < 3:
            return "." + digits.ljust(3, "0")
        if len(digits) > 3:
            return "." + digits[:3]
        return fragment

    for idx, line in enumerate(lines):
        match = VTT_TS_DECIMAL.match(line)
        if not match:
            continue
        pre, start, start_ms, end, end_ms, tail = match.groups()
        lines[idx] = f"{pre}{start}{normalize_ms(start_ms)} --> {end}{normalize_ms(end_ms)}{tail or ''}"
    return "\n".join(lines)


def sanitize_vtt_text_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for text in lines:
        clean = VALID_ENTITIES.sub("&amp;", text)
        clean = normalize_vtt_tags(clean)
        clean = enforce_vtt_tag_context(clean)
        clean = escape_angles_outside_allowed_tags(clean)
        out.append(clean)
    return out


def merge_cues_by_time(cues: list[Cue], tol_ms: int = 50) -> list[Cue]:
    tol = tol_ms / 1000
    merged: list[Cue] = []
    for cue in cues:
        if merged and abs(cue.start - merged[-1].start) <= tol and abs(cue.end - merged[-1].end) <= tol:
            merged[-1].text.extend([line for line in cue.text if line])
        else:
            merged.append(Cue(cue.start, cue.end, list(cue.text)))
    return merged


def sort_cues_by_start(cues: list[Cue]) -> None:
    cues.sort(key=lambda cue: (cue.start, cue.end))


def ensure_end_after_start(cues: list[Cue], epsilon_ms: int = 5) -> None:
    eps = epsilon_ms / 1000
    for cue in cues:
        if cue.end <= cue.start:
            cue.end = cue.start + eps


def enforce_monotonic_across_cues(cues: list[Cue], epsilon_ms: int = 5) -> None:
    eps = epsilon_ms / 1000
    last_end = -1e9
    for cue in cues:
        if cue.start < last_end + eps:
            cue.start = last_end + eps
        if cue.end < cue.start + eps:
            cue.end = cue.start + eps
        last_end = cue.end


def enforce_no_overlap_shrink_prev(cues: list[Cue], epsilon_ms: int = 5) -> None:
    eps = epsilon_ms / 1000
    for idx in range(len(cues) - 1):
        current = cues[idx]
        nxt = cues[idx + 1]
        gap = nxt.start - current.end
        if gap >= eps:
            continue
        target_end = nxt.start - eps
        if target_end > current.start:
            current.end = min(current.end, target_end)
        else:
            nxt.start = current.end + eps
        if nxt.end < nxt.start + eps:
            nxt.end = nxt.start + eps


def normalize_cues(cues: list[Cue]) -> list[Cue]:
    normalized = merge_cues_by_time(cues)
    sort_cues_by_start(normalized)
    ensure_end_after_start(normalized)
    enforce_monotonic_across_cues(normalized)
    enforce_no_overlap_shrink_prev(normalized)
    enforce_monotonic_across_cues(normalized)
    return normalized


def parse_vtt_cues(vtt_content: str, keep_biu: bool = False) -> list[Cue]:
    lines = vtt_content.strip().split("\n")
    cues: list[Cue] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("WEBVTT") or line == "" or line.startswith("NOTE"):
            idx += 1
            continue
        if " --> " not in line:
            idx += 1
            continue

        match = re.match(r"([^\s]+)\s+-->\s+([^\s]+)", line)
        if not match:
            idx += 1
            continue

        start_seconds = parse_timestamp_vtt(match.group(1))
        end_seconds = parse_timestamp_vtt(match.group(2))
        idx += 1
        text_lines: list[str] = []
        while idx < len(lines):
            nxt = lines[idx].strip()
            if nxt == "" or " --> " in nxt:
                break
            cleaned = strip_formatting(nxt, keep_biu).strip()
            if not cleaned and re.search(r"[\[\(\{][^\]\)\}]+[\]\)\}]", nxt):
                cleaned = nxt.strip()
            cleaned = decode_basic_entities(cleaned)
            if cleaned and cleaned != "-":
                text_lines.append(cleaned)
            idx += 1
        if text_lines:
            cues.append(Cue(start_seconds, end_seconds, text_lines))
    return normalize_cues(cues)


def parse_srt_cues(srt_content: str, keep_biu: bool = False) -> list[Cue]:
    lines = srt_content.strip().split("\n")
    cues: list[Cue] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line == "" or line.isdigit():
            idx += 1
            continue
        if " --> " not in line:
            idx += 1
            continue

        match = re.match(r"([^\s]+)\s+-->\s+([^\s]+)", line)
        if not match:
            idx += 1
            continue

        start_seconds = parse_timestamp_srt(match.group(1))
        end_seconds = parse_timestamp_srt(match.group(2))
        idx += 1
        text_lines: list[str] = []
        while idx < len(lines) and lines[idx].strip() != "":
            raw = lines[idx].strip()
            cleaned = strip_formatting(raw, keep_biu).strip()
            if not cleaned and re.search(r"[\[\(\{][^\]\)\}]+[\]\)\}]", raw):
                cleaned = raw
            if cleaned and cleaned != "-":
                text_lines.append(cleaned)
            idx += 1
        if text_lines:
            cues.append(Cue(start_seconds, end_seconds, text_lines))
    return normalize_cues(cues)


def cues_to_srt(cues: list[Cue]) -> str:
    lines: list[str] = []
    for idx, cue in enumerate(cues, start=1):
        lines.append(str(idx))
        lines.append(f"{seconds_to_srt_timestamp(cue.start)} --> {seconds_to_srt_timestamp(cue.end)}")
        lines.extend(cue.text)
        lines.append("")
    return "\n".join(lines)


def cues_to_vtt(cues: list[Cue]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{seconds_to_vtt_timestamp(cue.start)} --> {seconds_to_vtt_timestamp(cue.end)}")
        lines.extend(sanitize_vtt_text_lines(cue.text))
        lines.append("")
    return normalize_vtt_timestamp_decimals(normalize_vtt_blank_lines("\n".join(lines)))


def map_biu_to_ttml_spans(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"&lt;(\/?i|\/?b|\/?u|br\s*\/?)&gt;", r"<\1>", escaped, flags=re.I)
    escaped = re.sub(r"(?i)<br\s*/?>", "<br/>", escaped)
    escaped = re.sub(r"(?i)<i>", '<span tts:fontStyle="italic">', escaped)
    escaped = re.sub(r"(?i)</i>", "</span>", escaped)
    escaped = re.sub(r"(?i)<b>", '<span tts:fontWeight="bold">', escaped)
    escaped = re.sub(r"(?i)</b>", "</span>", escaped)
    escaped = re.sub(r"(?i)<u>", '<span tts:textDecoration="underline">', escaped)
    escaped = re.sub(r"(?i)</u>", "</span>", escaped)
    return re.sub(r"</?(?!span\b|br\b)[^>]+>", "", escaped)


def seconds_to_clock_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"


def cues_to_ttml(cues: list[Cue], xml_lang: str = "en") -> str:
    body_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<tt",
        '  xmlns="http://www.w3.org/ns/ttml"',
        '  xmlns:tts="http://www.w3.org/ns/ttml#styling"',
        '  xmlns:ttp="http://www.w3.org/ns/ttml#parameter"',
        '  xmlns:ttm="http://www.w3.org/ns/ttml#metadata"',
        '  xmlns:smpte="http://www.smpte-ra.org/schemas/2052-1/2013/smpte-tt"',
        f'  xml:lang="{xml_lang}"',
        '  xml:space="preserve"',
        '  ttp:timeBase="media">',
        "  <head>",
        "    <metadata>",
        "      <ttm:title>Converted Captions</ttm:title>",
        "      <smpte:information>Generated by Subtitle Converter</smpte:information>",
        "    </metadata>",
        "    <styling>",
        '      <style xml:id="sDefault" tts:fontFamily="monospace" tts:fontSize="100%" tts:color="white" tts:lineHeight="normal" tts:textOutline="black 1px 0px"/>',
        "    </styling>",
        "    <layout>",
        '      <region xml:id="pop1" tts:origin="10% 80%" tts:extent="80% 18%" tts:displayAlign="after" tts:textAlign="center"/>',
        "    </layout>",
        "  </head>",
        '  <body style="sDefault">',
        "    <div>",
    ]

    for idx, cue in enumerate(cues, start=1):
        text = "\n".join(cue.text).replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\n", "<br/>")
        text = map_biu_to_ttml_spans(text)
        body_lines.append(
            f'      <p xml:id="c{idx}" region="pop1" begin="{seconds_to_clock_time(cue.start)}" end="{seconds_to_clock_time(cue.end)}">{text}</p>'
        )

    body_lines.extend(["    </div>", "  </body>", "</tt>"])
    return "\n".join(body_lines) + "\n"


def infer_input_format(path: Path, content: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".srt", ".vtt"}:
        return suffix[1:]
    stripped = content.lstrip()
    if stripped.startswith("WEBVTT"):
        return "vtt"
    return "srt"


def convert_content(content: str, input_format: str, to_srt: bool, to_vtt: bool, to_ttml: bool) -> dict[str, str]:
    if input_format == "vtt":
        cues = parse_vtt_cues(content)
    elif input_format == "srt":
        cues = parse_srt_cues(content)
    else:
        raise ValueError(f"Unsupported input format: {input_format}")

    outputs: dict[str, str] = {}
    if to_srt:
        outputs["srt"] = cues_to_srt(cues)
    if to_vtt:
        outputs["vtt"] = cues_to_vtt(cues)
    if to_ttml:
        outputs["ttml"] = cues_to_ttml(cues)
    return outputs


def output_name(source: Path, target_ext: str, input_format: str) -> Path:
    if target_ext == input_format:
        return source.with_name(f"{source.stem}.normalized.{target_ext}")
    return source.with_suffix(f".{target_ext}")


def convert_file(path: str | Path, to_srt: bool, to_vtt: bool, to_ttml: bool) -> list[Path]:
    source = Path(path)
    content = source.read_text(encoding="utf-8")
    input_format = infer_input_format(source, content)
    outputs = convert_content(content, input_format, to_srt, to_vtt, to_ttml)

    written: list[Path] = []
    for ext, converted in outputs.items():
        out_path = output_name(source, ext, input_format)
        out_path.write_text(converted, encoding="utf-8")
        written.append(out_path)
    return written

