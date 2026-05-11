# -*- coding: utf-8 -*-
"""
===================================
格式化工具模块
===================================

提供各种内容格式化工具函数，用于将通用格式转换为平台特定格式。
"""

import re
import unicodedata
from typing import Any, Dict, List

import markdown2

TRUNCATION_SUFFIX = "\n\n...(本段内容过长已截断)"
PAGE_MARKER_PREFIX = f"\n\n📄"
PAGE_MARKER_SAFE_BYTES = 16 # "\n\n📄 9999/9999"
PAGE_MARKER_SAFE_LEN = 13   # "\n\n📄 9999/9999"
MIN_MAX_WORDS = 10
MIN_MAX_BYTES = 40

# Unicode code point ranges for special characters.
_SPECIAL_CHAR_RANGE = (0x10000, 0xFFFFF)
_SPECIAL_CHAR_REGEX = re.compile(r'[\U00010000-\U000FFFFF]')


def _page_marker(i: int, total: int) -> str:
    return f"{PAGE_MARKER_PREFIX} {i+1}/{total}"


def _is_special_char(c: str) -> bool:
    """判断字符是否为特殊字符
    
    Args:
        c: 字符
        
    Returns:
        True 如果字符为特殊字符，False 否则
    """
    if len(c) != 1:
        return False
    cp = ord(c)
    return _SPECIAL_CHAR_RANGE[0] <= cp <= _SPECIAL_CHAR_RANGE[1]


def _count_special_chars(s: str) -> int:
    """
    计算字符串中的特殊字符数量
    
    Args:
        s: 字符串
    """
    # reg find all (0x10000, 0xFFFFF)
    match = _SPECIAL_CHAR_REGEX.findall(s)
    return len(match)


def _effective_len(s: str, special_char_len: int = 2) -> int:
    """
    计算字符串的有效长度
    
    Args:
        s: 字符串
        special_char_len: 每个特殊字符的长度，默认为 2
        
    Returns:
        s 的有效长度
    """
    n = len(s)
    n += _count_special_chars(s) * (special_char_len - 1)
    return n


def _slice_at_effective_len(s: str, effective_len: int, special_char_len: int = 2) -> tuple[str, str]:
    """
    按有效长度分割字符串
    
    Args:
        s: 字符串
        effective_len: 有效长度
        special_char_len: 每个特殊字符的长度，默认为 2
        
    Returns:
        分割后的前、后部分字符串
    """
    if _effective_len(s, special_char_len) <= effective_len:
        return s, ""
    
    s_ = s[:effective_len]
    n_special_chars = _count_special_chars(s_)
    residual_lens = n_special_chars * (special_char_len - 1) + len(s_) - effective_len
    while residual_lens > 0:
        residual_lens -= special_char_len if _is_special_char(s_[-1]) else 1
        s_ = s_[:-1]
    return s_, s[len(s_):]


def markdown_to_html_document(markdown_text: str) -> str:
    """
    Convert Markdown to a complete HTML document (for email, md2img, etc.).

    Uses markdown2 with table and code block support, wraps with inline CSS
    for compact, readable layout. Reused by notification email and md2img.

    Args:
        markdown_text: Raw Markdown content.

    Returns:
        Full HTML document string with DOCTYPE, head, and body.
    """
    html_content = markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
    )

    css_style = """
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.5;
                color: #24292e;
                font-size: 14px;
                padding: 15px;
                max-width: 900px;
                margin: 0 auto;
            }
            h1 {
                font-size: 20px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.2em;
                margin-bottom: 0.8em;
                color: #0366d6;
            }
            h2 {
                font-size: 18px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.0em;
                margin-bottom: 0.6em;
            }
            h3 {
                font-size: 16px;
                margin-top: 0.8em;
                margin-bottom: 0.4em;
            }
            p {
                margin-top: 0;
                margin-bottom: 8px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 12px 0;
                display: block;
                overflow-x: auto;
                font-size: 13px;
            }
            th, td {
                border: 1px solid #dfe2e5;
                padding: 6px 10px;
                text-align: left;
            }
            th {
                background-color: #f6f8fa;
                font-weight: 600;
            }
            tr:nth-child(2n) {
                background-color: #f8f8f8;
            }
            tr:hover {
                background-color: #f1f8ff;
            }
            blockquote {
                color: #6a737d;
                border-left: 0.25em solid #dfe2e5;
                padding: 0 1em;
                margin: 0 0 10px 0;
            }
            code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: rgba(27,31,35,0.05);
                border-radius: 3px;
                font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            }
            pre {
                padding: 12px;
                overflow: auto;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 3px;
                margin-bottom: 10px;
            }
            hr {
                height: 0.25em;
                padding: 0;
                margin: 16px 0;
                background-color: #e1e4e8;
                border: 0;
            }
            ul, ol {
                padding-left: 20px;
                margin-bottom: 10px;
            }
            li {
                margin: 2px 0;
            }
        """

    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                {css_style}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """


def markdown_to_plain_text(markdown_text: str) -> str:
    """
    将 Markdown 转换为纯文本
    
    移除 Markdown 格式标记，保留可读性
    """
    text = markdown_text
    
    # 移除标题标记 # ## ###
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # 移除加粗 **text** -> text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    
    # 移除斜体 *text* -> text
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    
    # 移除引用 > text -> text
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    # 移除列表标记 - item -> item
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)
    
    # 移除分隔线 ---
    text = re.sub(r'^---+$', '────────', text, flags=re.MULTILINE)
    
    # 移除表格语法 |---|---|
    text = re.sub(r'\|[-:]+\|[-:|\s]+\|', '', text)
    text = re.sub(r'^\|(.+)\|$', r'\1', text, flags=re.MULTILINE)
    
    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def _bytes(s: str) -> int:
    return len(s.encode('utf-8'))


def _is_escaped_pipe(value: str, index: int) -> bool:
    """Return whether value[index] is escaped by an odd number of backslashes."""
    slash_count = 0
    pos = index - 1
    while pos >= 0 and value[pos] == "\\":
        slash_count += 1
        pos -= 1
    return slash_count % 2 == 1


def _parse_markdown_table_row(row: str) -> List[str]:
    """Split a Markdown table row while preserving escaped literal pipes."""
    value = row.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not _is_escaped_pipe(value, len(value) - 1):
        value = value[:-1]

    cells: List[str] = []
    current: List[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value) and value[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _chunk_by_max_bytes(content: str, max_bytes: int) -> List[str]:
    if _bytes(content) <= max_bytes:
        return [content]
    if max_bytes < MIN_MAX_BYTES:
        raise ValueError(f"max_bytes={max_bytes} < {MIN_MAX_BYTES}, 可能陷入无限递归。")
    
    sections: List[str] = []
    suffix = TRUNCATION_SUFFIX
    effective_max_bytes = max_bytes - _bytes(suffix)
    if effective_max_bytes <= 0:
        effective_max_bytes = max_bytes
        suffix = ""
        
    while True:
        chunk, content = slice_at_max_bytes(content, effective_max_bytes)
        if content.strip() != "":
            sections.append(chunk + suffix)
        else:
            # 最后一段了，直接添加并离开循环
            sections.append(chunk)
            break
    return sections


def chunk_content_by_max_bytes(content: str, max_bytes: int, add_page_marker: bool = False) -> List[str]:
    """
    按字节数智能分割消息内容
    
    Args:
        content: 完整消息内容
        max_bytes: 单条消息最大字节数
        add_page_marker: 是否添加分页标记
        
    Returns:
        分割后的区块列表
    """
    def _chunk(content: str, max_bytes: int) -> List[str]:
        # 优先按分隔线/标题分割，保证分页自然
        if max_bytes < MIN_MAX_BYTES:
            raise ValueError(f"max_bytes={max_bytes} < {MIN_MAX_BYTES}, 可能陷入无限递归。")
        
        if _bytes(content) <= max_bytes:
            return [content]
        
        sections, separator = _chunk_by_separators(content)
        if separator == "" and len(sections) == 1:
            # 无法智能分割，则强制按字数分割
            return _chunk_by_max_bytes(content, max_bytes)
        
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_bytes = 0
        separator_bytes = _bytes(separator) if separator else 0
        effective_max_bytes = max_bytes - separator_bytes

        for section in sections:
            section += separator
            section_bytes = _bytes(section)
            
            # 如果单个 section 就超长，需要强制截断
            if section_bytes > effective_max_bytes:
                # 先保存当前积累的内容
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_bytes = 0

                # 强制按字节截断，避免整段被截断丢失
                section_chunks = _chunk(
                    section[:-separator_bytes], effective_max_bytes
                )
                section_chunks[-1] = section_chunks[-1] + separator
                chunks.extend(section_chunks)
                continue

            # 检查加入后是否超长
            if current_bytes + section_bytes > effective_max_bytes:
                # 保存当前块，开始新块
                if current_chunk:
                    chunks.append("".join(current_chunk))
                current_chunk = [section]
                current_bytes = section_bytes
            else:
                current_chunk.append(section)
                current_bytes += section_bytes
                
        # 添加最后一块
        if current_chunk:
            chunks.append("".join(current_chunk))
            
        # 移除最后一个块的分割符
        if (chunks and 
            len(chunks[-1]) > separator_bytes and 
            chunks[-1][-separator_bytes:] == separator
        ):
            chunks[-1] = chunks[-1][:-separator_bytes]
        
        return chunks
    
    if add_page_marker:
        max_bytes = max_bytes - PAGE_MARKER_SAFE_BYTES
    
    chunks = _chunk(content, max_bytes)
    if add_page_marker:
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            chunks[i] = chunk + _page_marker(i, total_chunks)
    return chunks


def slice_at_max_bytes(text: str, max_bytes: int) -> tuple[str, str]:
    """
    按字节数截断字符串，确保不会在多字节字符中间截断

    Args:
        text: 要截断的字符串
        max_bytes: 最大字节数

    Returns:
        (截断后的字符串, 剩余未截断内容)
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, ""

    # 从最大字节数开始向前查找，找到完整的 UTF-8 字符边界
    truncated = encoded[:max_bytes]
    while truncated and (truncated[-1] & 0xC0) == 0x80:
        truncated = truncated[:-1]

    truncated = truncated.decode('utf-8', errors='ignore')
    return truncated, text[len(truncated):]


def format_feishu_markdown(content: str) -> str:
    """
    将通用 Markdown 转换为飞书 lark_md 更友好的格式
    
    转换规则：
    - 飞书不支持 Markdown 标题（# / ## / ###），用加粗代替
    - 引用块尽量保留 Markdown 引用语义
    - 分隔线统一为细线
    - 表格转换为等宽文本表，避免字段被拍平成散乱条目
    
    Args:
        content: 原始 Markdown 内容
        
    Returns:
        转换后的飞书 Markdown 格式内容
        
    Example:
        >>> markdown = "# 标题\\n> 引用\\n| 列1 | 列2 |"
        >>> formatted = format_feishu_markdown(markdown)
        >>> print(formatted)
        **标题**
        > 引用
        ```
        列1  列2
        值1  值2
        ```
    """
    def _display_width(value: str) -> int:
        """Return a rough terminal/card display width for mixed CJK text."""
        width = 0
        for ch in value:
            width += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
        return width

    def _truncate_to_width(value: str, max_width: int = 18) -> str:
        if _display_width(value) <= max_width:
            return value
        suffix = "..."
        target = max(1, max_width - len(suffix))
        chars = []
        width = 0
        for ch in value:
            ch_width = 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
            if width + ch_width > target:
                break
            chars.append(ch)
            width += ch_width
        return "".join(chars).rstrip() + suffix

    def _pad_cell(value: str, width: int) -> str:
        return value + " " * max(0, width - _display_width(value))

    def _flush_table_rows(buffer: List[str], output: List[str]) -> None:
        """将表格缓冲区中的行转换为飞书格式"""
        if not buffer:
            return

        def _parse_row(row: str) -> List[str]:
            """解析表格行，提取单元格"""
            return _parse_markdown_table_row(row)

        rows = []
        for raw in buffer:
            # 跳过分隔行（如 |---|---|）
            if re.match(r'^\s*\|?\s*[:-]+\s*(\|\s*[:-]+\s*)+\|?\s*$', raw):
                continue
            parsed = _parse_row(raw)
            if parsed:
                rows.append(parsed)

        if not rows:
            return

        max_cols = max(len(row) for row in rows)
        normalized_rows = [
            [_truncate_to_width(cell) for cell in (row + [""] * (max_cols - len(row)))]
            for row in rows
        ]
        col_widths = [
            max(_display_width(row[idx]) for row in normalized_rows)
            for idx in range(max_cols)
        ]

        output.append("```")
        for row in normalized_rows:
            output.append("  ".join(_pad_cell(cell, col_widths[idx]) for idx, cell in enumerate(row)).rstrip())
        output.append("```")

    lines = []
    table_buffer: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        # 处理表格行
        if line.strip().startswith('|'):
            table_buffer.append(line)
            continue

        # 刷新表格缓冲区
        if table_buffer:
            _flush_table_rows(table_buffer, lines)
            table_buffer = []

        # 转换标题（# ## ### 等）
        if re.match(r'^#{1,6}\s+', line):
            title = re.sub(r'^#{1,6}\s+', '', line).strip()
            if lines and lines[-1] != "":
                lines.append("")
            line = f"**{title}**" if title else ""
        # 转换引用块
        elif line.startswith('> '):
            quote = line[2:].strip()
            line = f"> {quote}" if quote else ""
        # 转换分隔线
        elif line.strip() == '---':
            line = '────────'
        # 转换列表项
        elif re.match(r'^\s*[-*]\s+\S', line):
            item = re.sub(r'^\s*[-*]\s+', '', line).strip()
            line = f"• {item}"

        lines.append(line)

    # 处理末尾的表格
    if table_buffer:
        _flush_table_rows(table_buffer, lines)

    return "\n".join(lines).strip()


def build_feishu_card_elements(content: str) -> List[Dict[str, Any]]:
    """
    Build Feishu interactive-card elements from Markdown-like report content.

    Feishu custom bot cards only support a small Markdown subset inside a single
    ``lark_md`` text block. Tables, fenced code blocks, and blockquotes often
    appear as literal text. This renderer maps common report Markdown to native
    card modules so the message is actually rendered in Feishu.
    """

    def _is_table_separator(row: str) -> bool:
        return bool(re.match(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$', row))

    def _parse_table_row(row: str) -> List[str]:
        return _parse_markdown_table_row(row)

    def _text(content_value: str, tag: str = "lark_md") -> Dict[str, str]:
        return {"tag": tag, "content": content_value}

    def _div(content_value: str, tag: str = "lark_md") -> Dict[str, Any]:
        return {"tag": "div", "text": _text(content_value, tag)}

    def _normalize_inline(value: str) -> str:
        value = value.strip()
        value = re.sub(r'`([^`]+)`', r'\1', value)
        return value

    def _flush_paragraph(buffer: List[str], output: List[Dict[str, Any]]) -> None:
        if not buffer:
            return
        paragraph = "\n".join(line.strip() for line in buffer if line.strip()).strip()
        if paragraph:
            output.append(_div(_normalize_inline(paragraph)))
        buffer.clear()

    def _build_table(rows: List[List[str]]) -> List[Dict[str, Any]]:
        if not rows:
            return []

        max_cols = max(len(row) for row in rows)
        normalized = [
            [_normalize_inline(cell) for cell in (row + [""] * (max_cols - len(row)))]
            for row in rows
        ]
        header = normalized[0]
        data_rows = normalized[1:]

        # Column sets render like compact tables in Feishu cards and avoid
        # literal Markdown/code fences. Wide tables become unreadable on mobile,
        # so render them as row summaries instead.
        if max_cols <= 4:
            columns = []
            for idx, title in enumerate(header):
                col_elements = [_div(f"**{title or '-'}**")]
                for row in data_rows[:12]:
                    col_elements.append(_div(row[idx] or "-", tag="plain_text"))
                columns.append(
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "vertical_align": "top",
                        "elements": col_elements,
                    }
                )
            result: List[Dict[str, Any]] = [{"tag": "column_set", "columns": columns}]
            if len(data_rows) > 12:
                result.append(_div(f"还有 {len(data_rows) - 12} 行已省略", tag="plain_text"))
            return result

        row_elements: List[Dict[str, Any]] = []
        for row in data_rows[:10]:
            title = row[0] if row else "-"
            details = "　".join(
                f"**{header[idx]}**：{row[idx] or '-'}"
                for idx in range(1, max_cols)
                if header[idx] or row[idx]
            )
            row_elements.append(_div(f"**{title}**\n{details}".strip()))
        if len(data_rows) > 10:
            row_elements.append(_div(f"还有 {len(data_rows) - 10} 行已省略", tag="plain_text"))
        return row_elements

    def _flush_table(buffer: List[str], output: List[Dict[str, Any]]) -> None:
        if not buffer:
            return
        rows = [_parse_table_row(row) for row in buffer if not _is_table_separator(row)]
        output.extend(_build_table(rows))
        buffer.clear()

    elements: List[Dict[str, Any]] = []
    paragraph_buffer: List[str] = []
    table_buffer: List[str] = []
    in_fence = False
    fence_buffer: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            _flush_paragraph(paragraph_buffer, elements)
            _flush_table(table_buffer, elements)
            if in_fence:
                if fence_buffer:
                    elements.append(_div("\n".join(fence_buffer), tag="plain_text"))
                fence_buffer = []
                in_fence = False
            else:
                in_fence = True
            continue

        if in_fence:
            fence_buffer.append(line)
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            _flush_paragraph(paragraph_buffer, elements)
            table_buffer.append(line)
            continue

        _flush_table(table_buffer, elements)

        if not stripped:
            _flush_paragraph(paragraph_buffer, elements)
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            _flush_paragraph(paragraph_buffer, elements)
            level = len(heading_match.group(1))
            title = _normalize_inline(heading_match.group(2))
            if elements and level <= 3:
                elements.append({"tag": "hr"})
            elements.append(_div(f"**{title}**"))
            continue

        if stripped == "---":
            _flush_paragraph(paragraph_buffer, elements)
            elements.append({"tag": "hr"})
            continue

        if stripped.startswith(">"):
            _flush_paragraph(paragraph_buffer, elements)
            quote = re.sub(r'^>\s?', '', stripped).strip()
            if quote:
                elements.append({"tag": "note", "elements": [_text(_normalize_inline(quote))]})
            continue

        list_match = re.match(r'^\s*[-*]\s+(.+)$', line)
        if list_match:
            paragraph_buffer.append(f"• {_normalize_inline(list_match.group(1))}")
            continue

        paragraph_buffer.append(_normalize_inline(line))

    _flush_paragraph(paragraph_buffer, elements)
    _flush_table(table_buffer, elements)
    if fence_buffer:
        elements.append(_div("\n".join(fence_buffer), tag="plain_text"))

    return elements or [_div(content.strip() or "-", tag="plain_text")]


def _chunk_by_separators(content: str) -> tuple[list[str], str]:
    """
    通过分割线等特殊字符将消息内容分割为多个区块
    
    Args:
        content: 完整消息内容
        
    Returns:
        sections: 分割后的区块列表
        separator: 区块之间的分隔符，None 表示无法分割
    """
    # 智能分割：优先按 "---" 分隔（股票之间的分隔线）
    # 其次尝试各级标题分割
    if "\n---\n" in content:
        sections = content.split("\n---\n")
        separator = "\n---\n"
    elif "\n# " in content:
        # 按 # 分割 (兼容一级标题)
        parts = content.split("\n## ")
        sections = [parts[0]] + [f"## {p}" for p in parts[1:]]
        separator = "\n"
    elif "\n## " in content:
        # 按 ## 分割 (兼容二级标题)
        parts = content.split("\n## ")
        sections = [parts[0]] + [f"## {p}" for p in parts[1:]]
        separator = "\n"
    elif "\n### " in content:
        # 按 ### 分割
        parts = content.split("\n### ")
        sections = [parts[0]] + [f"### {p}" for p in parts[1:]]
        separator = "\n"
    elif "\n**" in content:
        # 按 ** 加粗标题分割 (兼容 AI 未输出标准 Markdown 标题的情况)
        parts = content.split("\n**")
        sections = [parts[0]] + [f"**{p}" for p in parts[1:]]
        separator = "\n"
    elif "\n" in content:
        # 按 \n 分割
        sections = content.split("\n")
        separator = "\n"
    else:
        return [content], ""
    return sections, separator


def _chunk_by_max_words(content: str, max_words: int, special_char_len: int = 2) -> list[str]:
    """
    按字数分割消息内容
    
    Args:
        content: 完整消息内容
        max_words: 单条消息最大字数
        special_char_len: 每个特殊字符的长度，默认为 2
        
    Returns:
        分割后的区块列表
    """
    if _effective_len(content, special_char_len) <= max_words:
        return [content]
    if max_words < MIN_MAX_WORDS:
        raise ValueError(
            f"max_words={max_words} < {MIN_MAX_WORDS}, 可能陷入无限递归。"
        )

    sections = []
    suffix = TRUNCATION_SUFFIX
    effective_max_words = max_words - len(suffix)  # 预留后缀，避免边界超限
    if effective_max_words <= 0:
        effective_max_words = max_words
        suffix = ""

    while True:
        chunk, content = _slice_at_effective_len(content, effective_max_words, special_char_len)
        if content.strip() != "":
            sections.append(chunk + suffix)
        else:
            # 最后一段了，直接添加并离开循环
            sections.append(chunk)
            break
    return sections


def chunk_content_by_max_words(
    content: str, 
    max_words: int, 
    special_char_len: int = 2,
    add_page_marker: bool = False
    ) -> list[str]:
    """
    按字数智能分割消息内容
    
    Args:
        content: 完整消息内容
        max_words: 单条消息最大字数
        special_char_len: 每个特殊字符的长度，默认为 2
        add_page_marker: 是否添加分页标记
        
    Returns:
        分割后的区块列表
    """
    def _chunk(content: str, max_words: int, special_char_len: int = 2) -> list[str]:
        if max_words < MIN_MAX_WORDS:
            # Safe guard，避免无限递归
            # 理论上，max_words在每次递归中可以减小到无限小，但实际中不太可能发生，
            # 除非每次_chunk_by_separators都能成功返回分隔符，且max_words初始值太小。
            raise ValueError(f"max_words={max_words} < {MIN_MAX_WORDS}, 可能陷入无限递归。")
        
        if _effective_len(content, special_char_len) <= max_words:
            return [content]

        sections, separator = _chunk_by_separators(content)
        if separator == "" and len(sections) == 1:
            # 无法智能分割，则强制按字数分割
            return _chunk_by_max_words(content, max_words, special_char_len)

        chunks = []
        current_chunk = []
        current_word_len = 0
        separator_len = len(separator) if separator else 0
        effective_max_words = max_words - separator_len # 预留分割符长度，避免边界超限

        for section in sections:
            section += separator
            section_word_len = _effective_len(section, special_char_len)

            # 如果单个 section 就超长，需要强制截断
            if section_word_len > max_words:
                # 先保存当前积累的内容
                if current_chunk:
                    chunks.append("".join(current_chunk))

                # 强制截断这个超长 section
                section_chunks = _chunk(
                    section[:-separator_len], effective_max_words, special_char_len
                    )
                section_chunks[-1] = section_chunks[-1] + separator
                chunks.extend(section_chunks)
                continue

            # 检查加入后是否超长
            if current_word_len + section_word_len > max_words:
                # 保存当前块，开始新块
                if current_chunk:
                    chunks.append("".join(current_chunk))
                current_chunk = [section]
                current_word_len = section_word_len
            else:
                current_chunk.append(section)
                current_word_len += section_word_len

        # 添加最后一块
        if current_chunk:
            chunks.append("".join(current_chunk))

        # 移除最后一个块的分割符
        if (chunks and
            len(chunks[-1]) > separator_len and
            chunks[-1][-separator_len:] == separator
        ):
            chunks[-1] = chunks[-1][:-separator_len]
        return chunks
    
    
    if add_page_marker:
        max_words = max_words - PAGE_MARKER_SAFE_LEN
    
    chunks = _chunk(content, max_words, special_char_len)
    if add_page_marker:
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            chunks[i] = chunk + _page_marker(i, total_chunks)
    return chunks
