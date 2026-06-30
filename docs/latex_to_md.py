#!/usr/bin/env python3
"""Convert lsat-speedrun-brainlift.tex to markdown."""

import re
import sys
from pathlib import Path


def extract_braced(text: str, start: int) -> tuple[str, int]:
    """Return content inside {...} starting at start (which must point to '{')."""
    assert text[start] == "{"
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    raise ValueError("Unclosed brace")


def convert_inline(s: str) -> str:
    replacements = [
        (r"\\textbar\{\}", "|"),
        (r"P\(correct\\textbar\{\}\$\\theta\$\)", "P(correct|θ)"),
        (r"f\(\$\\theta\$, a, b, c\)", "f(θ, a, b, c)"),
        (r"NL\$\\rightarrow\$symbolic\$\\rightarrow\$solver", "NL→symbolic→solver"),
        (r"premise\$\\rightarrow\$conclusion", "premise→conclusion"),
        (r"drill\$\\rightarrow\$timed\$\\rightarrow\$full", "drill→timed→full"),
        (r"RC\$\\leftrightarrow\$LR", "RC↔LR"),
        (r"A\$>\$B \$\\Rightarrow\$ B\$<\$A", "A>B ⇒ B<A"),
        (r"A\$>\$B, B\$>\$C \$\\Rightarrow\$ A\$>\$C", "A>B, B>C ⇒ A>C"),
    ]
    for pat, rep in replacements:
        s = re.sub(pat, rep, s)

    def math_sub(m: re.Match[str]) -> str:
        inner = m.group(1)
        inner = (
            inner.replace(r"\sim", "∼")
            .replace(r"\rightarrow", "→")
            .replace(r"\Rightarrow", "⇒")
            .replace(r"\leftrightarrow", "↔")
            .replace(r"\neq", "≠")
            .replace(r"\pm", "±")
            .replace(r"\approx", "≈")
            .replace(r"\downarrow", "↓")
            .replace(r"\uparrow", "↑")
            .replace(r"\times", "×")
            .replace(r"\theta", "θ")
            .replace(r"\P{}", "¶")
            .replace(r"\%", "%")
            .replace("--", "–")
        )
        inner = re.sub(r"\\textbar\{\}", "|", inner)
        return inner

    s = re.sub(r"\$([^$]+)\$", math_sub, s)

    # Formatting commands with nested braces
    while True:
        m = re.search(r"\\(textbf|textit|texttt|enquote)\{", s)
        if not m:
            break
        cmd = m.group(1)
        inner, end = extract_braced(s, m.end() - 1)
        inner = convert_inline(inner)
        if cmd == "textbf":
            repl = f"**{inner}**"
        elif cmd == "textit":
            repl = f"*{inner}*"
        elif cmd == "texttt":
            repl = f"`{inner}`"
        else:
            repl = f'"{inner}"'
        s = s[: m.start()] + repl + s[end:]

    s = re.sub(r"\\&", "&", s)
    s = re.sub(r"\\%", "%", s)
    s = re.sub(r"---", "—", s)
    s = re.sub(r"--", "–", s)
    return s.strip()


def find_env_end(text: str, start: int, env: str) -> int:
    begin = rf"\begin{{{env}}}"
    end = rf"\end{{{env}}}"
    depth = 0
    i = start
    while i < len(text):
        if text.startswith(begin, i):
            depth += 1
            i += len(begin)
        elif text.startswith(end, i):
            depth -= 1
            if depth == 0:
                return i + len(end)
            i += len(end)
        else:
            i += 1
    raise ValueError(f"Unclosed {env} environment")


def parse_itemize(text: str, indent: int = 0) -> list[str]:
    prefix = "  " * indent + "- "
    lines: list[str] = []
    i = 0
    while i < len(text):
        text = text[i:].lstrip()
        i = 0
        if not text.startswith(r"\item"):
            break
        text = text[len(r"\item") :].lstrip()
        if text.startswith(r"\begin{itemize}"):
            nested_start = 0
            nested_end = find_env_end(text, 0, "itemize")
            nested = text[:nested_end]
            lines.extend(parse_itemize(nested[len(r"\begin{itemize}") : nested.rfind(r"\end{itemize}")], indent + 1))
            text = text[nested_end:].lstrip()
            i = 0
            continue
        # content until next \item or \end{itemize}
        j = 0
        depth = 0
        while j < len(text):
            if text.startswith(r"\begin{itemize}", j):
                depth += 1
                j += len(r"\begin{itemize}")
                continue
            if text.startswith(r"\end{itemize}", j):
                if depth == 0:
                    break
                depth -= 1
                j += len(r"\end{itemize}")
                continue
            if depth == 0 and text.startswith(r"\item", j):
                break
            j += 1
        chunk = text[:j].strip()
        text = text[j:]
        if r"\begin{itemize}" in chunk:
            head, _, tail = chunk.partition(r"\begin{itemize}")
            head = head.strip()
            if head:
                lines.append(prefix + convert_inline(head))
            nested_block = r"\begin{itemize}" + tail
            inner = nested_block[len(r"\begin{itemize}") : nested_block.rfind(r"\end{itemize}")]
            lines.extend(parse_itemize(inner, indent + 1))
        elif chunk:
            lines.append(prefix + convert_inline(chunk))
    return lines


def convert(tex: str) -> str:
    body = tex.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    body = re.sub(r"\\maketitle\s*", "", body)

    out: list[str] = ["# LSAT Speedrun BrainLift", "", "*Iris Cai*", ""]
    pos = 0

    while pos < len(body):
        body = body[pos:].lstrip()
        pos = 0
        if not body:
            break

        sec = re.match(r"\\(section|subsection|subsubsection)\*?\{", body)
        if sec:
            level = {"section": "##", "subsection": "###", "subsubsection": "####"}[sec.group(1)]
            title, end = extract_braced(body, sec.end() - 1)
            out.append(f"{level} {convert_inline(title)}")
            out.append("")
            pos = end
            continue

        if body.startswith(r"\begin{quote}"):
            end = find_env_end(body, 0, "quote")
            q = body[len(r"\begin{quote}") : body.find(r"\end{quote}")]
            q = re.sub(r"\\itshape\s*", "", q).strip()
            out.append(f"> *{convert_inline(q)}*")
            out.append("")
            pos = end
            continue

        if body.startswith(r"\begin{itemize}"):
            end = find_env_end(body, 0, "itemize")
            block = body[:end]
            inner = block[len(r"\begin{itemize}") : block.rfind(r"\end{itemize}")]
            out.extend(parse_itemize(inner, 0))
            out.append("")
            pos = end
            continue

        header = re.match(r"^([A-Za-z0-9 /&().–—]+):\s*\n\\begin\{itemize\}", body, re.MULTILINE)
        if header:
            out.append(f"#### {convert_inline(header.group(1))}")
            out.append("")
            pos = header.end() - len(r"\begin{itemize}")
            continue

        para = re.match(
            r"^((?:[^\n\\]|\\[a-zA-Z]+(?:\{[^{}]*\})*)+)\n\n",
            body,
        )
        if para and not para.group(1).strip().startswith("\\begin"):
            text = convert_inline(para.group(1).strip())
            if text:
                out.append(text)
                out.append("")
            pos = para.end()
            continue

        # multi-line paragraph before next LaTeX command
        para1 = re.match(
            r"^((?:[^\n\\]+(?:\n[^\n\\]+)*))\n(?=\\)",
            body,
        )
        if para1 and not para1.group(1).strip().startswith("\\"):
            text = convert_inline(para1.group(1).strip())
            if text:
                out.append(text)
                out.append("")
            pos = para1.end()
            continue

        # paragraph before itemize (no blank line), e.g. consolidated headers
        para2 = re.match(r"^([^\n]+)\n\\begin\{itemize\}", body)
        if para2 and not para2.group(1).startswith("\\"):
            out.append(f"#### {convert_inline(para2.group(1).rstrip(':'))}")
            out.append("")
            pos = para2.end() - len(r"\begin{itemize}")
            continue

        # bold paragraph block (Spiky POV)
        bold = re.match(r"\\textbf\{", body)
        if bold:
            end = body.find("\n\n", bold.start())
            if end == -1:
                end = len(body)
            chunk = body[bold.start() : end].strip()
            out.append(convert_inline(chunk))
            out.append("")
            pos = end
            continue

        # skip unknown
        nxt = re.search(r"\\(section|subsection|subsubsection)\*?\{|\\begin\{(quote|itemize)\}", body[1:])
        if nxt:
            pos = nxt.start() + 1
        else:
            break

    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def main() -> None:
    root = Path(__file__).resolve().parent
    tex_path = root / "lsat-speedrun-brainlift.tex"
    md_path = root / "lsat-speedrun-brainlift.md"
    md_path.write_text(convert(tex_path.read_text()))
    print(f"Wrote {md_path} ({len(md_path.read_text().splitlines())} lines)")


if __name__ == "__main__":
    main()
