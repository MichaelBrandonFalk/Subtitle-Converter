const elements = {
  fileInput: document.getElementById("file-input"),
  dropzone: document.getElementById("dropzone"),
  currentFile: document.getElementById("current-file"),
  convertButton: document.getElementById("convert-button"),
  results: document.getElementById("results"),
  toSrt: document.getElementById("to-srt"),
  toVtt: document.getElementById("to-vtt"),
  toTtml: document.getElementById("to-ttml"),
};

let selectedFile = null;

const allowedVttTags = new Set(["b", "i", "u", "c", "ruby", "rt", "v", "lang"]);

function parseTimestampVtt(timestamp) {
  const parts = timestamp.split(":");
  let hours;
  let minutes;
  let seconds;
  if (parts.length === 3) {
    [hours, minutes, seconds] = parts;
  } else {
    hours = "0";
    [minutes, seconds] = parts;
  }
  const [sec, frac = "0"] = seconds.split(".");
  return Number(hours) * 3600 + Number(minutes) * 60 + Number(sec) + Number(frac) / 1000;
}

function parseTimestampSrt(timestamp) {
  const [timePart, frac = "0"] = timestamp.split(",");
  const [hours, minutes, seconds] = timePart.split(":").map(Number);
  return hours * 3600 + minutes * 60 + seconds + Number(frac) / 1000;
}

function secondsToVttTimestamp(totalSeconds) {
  let hours = Math.floor(totalSeconds / 3600);
  let minutes = Math.floor((totalSeconds % 3600) / 60);
  let secFloat = totalSeconds % 60;
  let sec = Math.floor(secFloat);
  let ms = Math.round((secFloat - sec) * 1000);
  if (ms === 1000) {
    ms = 0;
    sec += 1;
    if (sec === 60) {
      sec = 0;
      minutes += 1;
      if (minutes === 60) {
        minutes = 0;
        hours += 1;
      }
    }
  }
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function secondsToSrtTimestamp(totalSeconds) {
  return secondsToVttTimestamp(totalSeconds).replace(".", ",");
}

function secondsToClockTime(totalSeconds) {
  return secondsToVttTimestamp(totalSeconds);
}

function stripFormatting(text) {
  return text.replace(/<\/?[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

function decodeBasicEntities(text) {
  return text
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&nbsp;", " ")
    .replaceAll("&lrm;", "")
    .replaceAll("&rlm;", "");
}

function normalizeVttTags(text) {
  return text.replace(/<(\/?)([A-Za-z]+)([^>]*)>/g, (_, slash, rawName, rest) => {
    const name = rawName.toLowerCase();
    if (!allowedVttTags.has(name)) {
      return `&lt;${slash ? "/" : ""}${name}${rest}&gt;`;
    }
    if (slash) {
      return `</${name}>`;
    }
    const restStripped = (rest || "").replace(/\s+/g, " ").trim();
    if (name === "v" || name === "lang") {
      const annotation = restStripped.replace(/[<>]/g, "");
      return `<${name}${annotation ? ` ${annotation}` : ""}>`;
    }
    if (name === "c") {
      const classes = restStripped
        .split(/[\s.]+/)
        .filter(Boolean)
        .map((token) => token.replace(/[^A-Za-z0-9_-]/g, ""))
        .filter(Boolean);
      return classes.length ? `<c.${classes.join(".")}>` : "<c>";
    }
    return `<${name}>`;
  });
}

function escapeAnglesOutsideAllowedTags(text) {
  const placeholders = [];
  const protectedText = text.replace(/<\/?(?:b|i|u|c|ruby|rt|v|lang)(?:[^>]*)>/g, (tag) => {
    placeholders.push(tag);
    return `@@TAG${placeholders.length - 1}@@`;
  });
  let escaped = protectedText.replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  placeholders.forEach((tag, idx) => {
    escaped = escaped.replaceAll(`@@TAG${idx}@@`, tag);
  });
  return escaped;
}

function enforceVttTagContext(text) {
  const tagPattern = /<(\/?)([A-Za-z]+)([^>]*)>/g;
  const stack = [];
  const out = [];
  let pos = 0;
  let match;
  while ((match = tagPattern.exec(text)) !== null) {
    if (match.index > pos) {
      out.push(text.slice(pos, match.index));
    }
    pos = match.index + match[0].length;
    const slash = match[1];
    const name = match[2].toLowerCase();
    if (!allowedVttTags.has(name)) {
      out.push(match[0].replaceAll("<", "&lt;").replaceAll(">", "&gt;"));
      continue;
    }
    if (slash) {
      if (stack.includes(name)) {
        while (stack.length && stack.at(-1) !== name) {
          out.push(`</${stack.pop()}>`);
        }
        out.push(`</${name}>`);
        stack.pop();
      } else {
        out.push(`&lt;/${name}&gt;`);
      }
      continue;
    }
    if (name === "rt" && !stack.includes("ruby")) {
      out.push("&lt;rt&gt;");
      continue;
    }
    out.push(`<${name}>`);
    stack.push(name);
  }
  out.push(text.slice(pos));
  while (stack.length) {
    out.push(`</${stack.pop()}>`);
  }
  return out.join("");
}

function sanitizeVttTextLines(lines) {
  return lines.map((line) => {
    let clean = line.replace(/&(?!amp;|lt;|gt;|lrm;|rlm;|nbsp;|#\d+;|#x[0-9A-Fa-f]+;)/g, "&amp;");
    clean = normalizeVttTags(clean);
    clean = enforceVttTagContext(clean);
    clean = escapeAnglesOutsideAllowedTags(clean);
    return clean;
  });
}

function mergeCuesByTime(cues, toleranceMs = 50) {
  const tolerance = toleranceMs / 1000;
  const merged = [];
  for (const cue of cues) {
    const previous = merged.at(-1);
    if (previous && Math.abs(cue.start - previous.start) <= tolerance && Math.abs(cue.end - previous.end) <= tolerance) {
      previous.text.push(...cue.text.filter(Boolean));
      continue;
    }
    merged.push({ start: cue.start, end: cue.end, text: [...cue.text] });
  }
  return merged;
}

function normalizeCues(cues) {
  const merged = mergeCuesByTime(cues);
  merged.sort((a, b) => a.start - b.start || a.end - b.end);

  const eps = 0.005;
  for (const cue of merged) {
    if (cue.end <= cue.start) {
      cue.end = cue.start + eps;
    }
  }

  let lastEnd = -1e9;
  for (const cue of merged) {
    if (cue.start < lastEnd + eps) {
      cue.start = lastEnd + eps;
    }
    if (cue.end < cue.start + eps) {
      cue.end = cue.start + eps;
    }
    lastEnd = cue.end;
  }

  for (let idx = 0; idx < merged.length - 1; idx += 1) {
    const current = merged[idx];
    const next = merged[idx + 1];
    if (next.start - current.end >= eps) {
      continue;
    }
    const targetEnd = next.start - eps;
    if (targetEnd > current.start) {
      current.end = Math.min(current.end, targetEnd);
    } else {
      next.start = current.end + eps;
    }
    if (next.end < next.start + eps) {
      next.end = next.start + eps;
    }
  }

  lastEnd = -1e9;
  for (const cue of merged) {
    if (cue.start < lastEnd + eps) {
      cue.start = lastEnd + eps;
    }
    if (cue.end < cue.start + eps) {
      cue.end = cue.start + eps;
    }
    lastEnd = cue.end;
  }

  return merged;
}

function parseVttCues(content) {
  const lines = content.trim().split(/\r?\n/);
  const cues = [];
  let idx = 0;
  while (idx < lines.length) {
    const line = lines[idx].trim();
    if (!line || line.startsWith("WEBVTT") || line.startsWith("NOTE")) {
      idx += 1;
      continue;
    }
    if (!line.includes(" --> ")) {
      idx += 1;
      continue;
    }
    const match = line.match(/^([^\s]+)\s+-->\s+([^\s]+)/);
    if (!match) {
      idx += 1;
      continue;
    }
    const start = parseTimestampVtt(match[1]);
    const end = parseTimestampVtt(match[2]);
    idx += 1;
    const text = [];
    while (idx < lines.length) {
      const next = lines[idx].trim();
      if (!next || next.includes(" --> ")) {
        break;
      }
      const cleaned = decodeBasicEntities(stripFormatting(next));
      if (cleaned && cleaned !== "-") {
        text.push(cleaned);
      }
      idx += 1;
    }
    if (text.length) {
      cues.push({ start, end, text });
    }
  }
  return normalizeCues(cues);
}

function parseSrtCues(content) {
  const lines = content.trim().split(/\r?\n/);
  const cues = [];
  let idx = 0;
  while (idx < lines.length) {
    const line = lines[idx].trim();
    if (!line || /^\d+$/.test(line)) {
      idx += 1;
      continue;
    }
    if (!line.includes(" --> ")) {
      idx += 1;
      continue;
    }
    const match = line.match(/^([^\s]+)\s+-->\s+([^\s]+)/);
    if (!match) {
      idx += 1;
      continue;
    }
    const start = parseTimestampSrt(match[1]);
    const end = parseTimestampSrt(match[2]);
    idx += 1;
    const text = [];
    while (idx < lines.length && lines[idx].trim()) {
      const cleaned = stripFormatting(lines[idx].trim());
      if (cleaned && cleaned !== "-") {
        text.push(cleaned);
      }
      idx += 1;
    }
    if (text.length) {
      cues.push({ start, end, text });
    }
  }
  return normalizeCues(cues);
}

function cuesToSrt(cues) {
  const lines = [];
  cues.forEach((cue, index) => {
    lines.push(String(index + 1));
    lines.push(`${secondsToSrtTimestamp(cue.start)} --> ${secondsToSrtTimestamp(cue.end)}`);
    lines.push(...cue.text);
    lines.push("");
  });
  return lines.join("\n");
}

function normalizeVttBlankLines(text) {
  const lines = text.split(/\r?\n/);
  const output = [];
  let idx = 0;
  if (lines[idx] && lines[idx].trim().toUpperCase().startsWith("WEBVTT")) {
    output.push("WEBVTT");
    idx += 1;
    while (idx < lines.length && !lines[idx].trim()) {
      idx += 1;
    }
    output.push("");
  }
  for (; idx < lines.length; idx += 1) {
    const trimmed = lines[idx].trimEnd();
    if (/^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}/.test(trimmed) && output.length && output.at(-1) !== "") {
      output.push("");
    }
    output.push(trimmed);
  }
  return output.join("\n");
}

function normalizeVttTimestampDecimals(text) {
  return text.replace(
    /^(\s*)(\d{1,2}:\d{2}(?::\d{2})?)(\.\d{1,3})?\s+-->\s+(\d{1,2}:\d{2}(?::\d{2})?)(\.\d{1,3})?(\s.*)?$/gm,
    (_, pre, start, startMs, end, endMs, tail = "") => {
      const normalizeMs = (value) => {
        if (!value) {
          return ".000";
        }
        const digits = value.slice(1);
        if (digits.length < 3) {
          return `.${digits.padEnd(3, "0")}`;
        }
        if (digits.length > 3) {
          return `.${digits.slice(0, 3)}`;
        }
        return value;
      };
      return `${pre}${start}${normalizeMs(startMs)} --> ${end}${normalizeMs(endMs)}${tail}`;
    }
  );
}

function cuesToVtt(cues) {
  const lines = ["WEBVTT", ""];
  for (const cue of cues) {
    lines.push(`${secondsToVttTimestamp(cue.start)} --> ${secondsToVttTimestamp(cue.end)}`);
    lines.push(...sanitizeVttTextLines(cue.text));
    lines.push("");
  }
  return normalizeVttTimestampDecimals(normalizeVttBlankLines(lines.join("\n")));
}

function escapeXml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function mapBiuToTtmlSpans(text) {
  let escaped = escapeXml(text);
  escaped = escaped.replace(/&lt;(\/?i|\/?b|\/?u|br\s*\/?)&gt;/gi, "<$1>");
  escaped = escaped.replace(/<br\s*\/?>/gi, "<br/>");
  escaped = escaped.replace(/<i>/gi, '<span tts:fontStyle="italic">');
  escaped = escaped.replace(/<\/i>/gi, "</span>");
  escaped = escaped.replace(/<b>/gi, '<span tts:fontWeight="bold">');
  escaped = escaped.replace(/<\/b>/gi, "</span>");
  escaped = escaped.replace(/<u>/gi, '<span tts:textDecoration="underline">');
  escaped = escaped.replace(/<\/u>/gi, "</span>");
  return escaped.replace(/<\/?(?!span\b|br\b)[^>]+>/g, "");
}

function cuesToTtml(cues) {
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    "<tt",
    '  xmlns="http://www.w3.org/ns/ttml"',
    '  xmlns:tts="http://www.w3.org/ns/ttml#styling"',
    '  xmlns:ttp="http://www.w3.org/ns/ttml#parameter"',
    '  xmlns:ttm="http://www.w3.org/ns/ttml#metadata"',
    '  xmlns:smpte="http://www.smpte-ra.org/schemas/2052-1/2013/smpte-tt"',
    '  xml:lang="en"',
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
  ];

  cues.forEach((cue, index) => {
    const text = mapBiuToTtmlSpans(cue.text.join("\n").replaceAll("\n", "<br/>"));
    lines.push(
      `      <p xml:id="c${index + 1}" region="pop1" begin="${secondsToClockTime(cue.start)}" end="${secondsToClockTime(cue.end)}">${text}</p>`
    );
  });

  lines.push("    </div>", "  </body>", "</tt>");
  return `${lines.join("\n")}\n`;
}

function inferInputFormat(name, content) {
  const lower = name.toLowerCase();
  if (lower.endsWith(".vtt")) {
    return "vtt";
  }
  if (lower.endsWith(".srt")) {
    return "srt";
  }
  return content.trimStart().startsWith("WEBVTT") ? "vtt" : "srt";
}

function outputName(fileName, inputFormat, targetFormat) {
  const stem = fileName.replace(/\.[^.]+$/, "");
  if (inputFormat === targetFormat) {
    return `${stem}.normalized.${targetFormat}`;
  }
  return `${stem}.${targetFormat}`;
}

function renderResults(outputs) {
  if (!outputs.length) {
    elements.results.innerHTML = '<div class="empty-state"><p>Converted outputs will appear here.</p></div>';
    return;
  }

  elements.results.innerHTML = "";
  for (const output of outputs) {
    const card = document.createElement("article");
    card.className = "result-card";

    const title = document.createElement("h3");
    title.textContent = output.name;
    card.appendChild(title);

    const meta = document.createElement("p");
    meta.textContent = `${output.ext.toUpperCase()} output ready to download`;
    card.appendChild(meta);

    const preview = document.createElement("pre");
    preview.textContent = output.content.slice(0, 1600);
    card.appendChild(preview);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "download-button";
    button.textContent = "Download";
    button.addEventListener("click", () => {
      const blob = new Blob([output.content], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = output.name;
      link.click();
      URL.revokeObjectURL(url);
    });
    card.appendChild(button);

    elements.results.appendChild(card);
  }
}

function updateCurrentFile() {
  elements.currentFile.textContent = selectedFile ? `Selected: ${selectedFile.name}` : "No file selected.";
}

function handleFiles(fileList) {
  selectedFile = fileList?.[0] || null;
  updateCurrentFile();
}

async function convertSelectedFile() {
  if (!selectedFile) {
    window.alert("Choose a subtitle file first.");
    return;
  }
  if (![elements.toSrt.checked, elements.toVtt.checked, elements.toTtml.checked].some(Boolean)) {
    window.alert("Select at least one output format.");
    return;
  }

  const content = await selectedFile.text();
  const inputFormat = inferInputFormat(selectedFile.name, content);
  const cues = inputFormat === "vtt" ? parseVttCues(content) : parseSrtCues(content);

  const outputs = [];
  if (elements.toSrt.checked) {
    outputs.push({ ext: "srt", name: outputName(selectedFile.name, inputFormat, "srt"), content: cuesToSrt(cues) });
  }
  if (elements.toVtt.checked) {
    outputs.push({ ext: "vtt", name: outputName(selectedFile.name, inputFormat, "vtt"), content: cuesToVtt(cues) });
  }
  if (elements.toTtml.checked) {
    outputs.push({ ext: "ttml", name: outputName(selectedFile.name, inputFormat, "ttml"), content: cuesToTtml(cues) });
  }
  renderResults(outputs);
}

elements.fileInput.addEventListener("change", (event) => {
  handleFiles(event.target.files);
});

["dragenter", "dragover"].forEach((eventName) => {
  elements.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropzone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  elements.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropzone.classList.remove("dragging");
  });
});

elements.dropzone.addEventListener("drop", (event) => {
  handleFiles(event.dataTransfer.files);
});

elements.convertButton.addEventListener("click", () => {
  convertSelectedFile().catch((error) => {
    console.error(error);
    window.alert(`Conversion failed: ${error.message}`);
  });
});

updateCurrentFile();
