from __future__ import annotations

import json
import re
from typing import Any

ANALYSIS_SECTIONS: list[tuple[str, str]] = [
    ("muc_tieu_tai_lieu", "1. MỤC TIÊU TÀI LIỆU"),
    ("he_thong_va_api", "2. CÁC HỆ THỐNG VÀ API"),
    ("luong_nghiep_vu", "3. LUỒNG NGHIỆP VỤ CHÍNH"),
    ("bang_du_lieu", "4. CÁC BẢNG DỮ LIỆU"),
    ("test_scenarios", "5. KỊCH BẢN KIỂM THỬ (TEST SCENARIOS)"),
    ("rui_ro_va_cau_hoi", "6. RỦI RO / ĐIỂM CHƯA RÕ"),
]

_KNOWN_KEYS_RE = re.compile(
    r'^\{\s*"(features|requirements|results|conditions|coverage_items|chunk_id|muc_tieu_tai_lieu)"'
)
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_FENCE_JSON_RE = re.compile(r"```json", re.IGNORECASE)
_FENCE_RE = re.compile(r"```")
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_SMART_DOUBLE_QUOTES_RE = re.compile(r"[“”]")
_SMART_SINGLE_QUOTES_RE = re.compile(r"[‘’]")


def try_parse(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


def strip_ai_wrappers(raw: str | None) -> str:
    t = str(raw or "")
    t = _THINK_RE.sub("", t)
    t = _FENCE_JSON_RE.sub("", t)
    t = _FENCE_RE.sub("", t)
    return t.strip()


def balanced_end(t: str, start_idx: int) -> int:
    """Trả về vị trí kết thúc (inclusive) của {...} cân bằng bắt đầu tại start_idx, hoặc -1 nếu bị cắt cụt."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start_idx, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def salvage_array(t: str, key: str) -> list[dict[str, Any]]:
    """Cứu các phần tử {...} hoàn chỉnh của mảng `key` trong chuỗi JSON kể cả khi bị cắt cụt."""
    k = t.find(f'"{key}"')
    if k < 0:
        return []
    i = t.find("[", k)
    if i < 0:
        return []
    i += 1
    out: list[dict[str, Any]] = []
    depth = 0
    in_str = False
    esc = False
    start = -1
    n = len(t)
    while i < n:
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                slice_str = t[start : i + 1]
                obj = try_parse(slice_str) or try_parse(_TRAILING_COMMA_RE.sub(r"\1", slice_str))
                if isinstance(obj, dict):
                    out.append(obj)
                start = -1
        elif c == "]" and depth == 0:
            break
        i += 1
    return out


def repair_candidates(t: str) -> list[str]:
    """Vá JSON bị cắt cụt do chạm giới hạn token."""
    stack: list[str] = []
    in_str = False
    esc = False
    str_start = -1
    last_comma = -1
    last_comma_stack: list[str] | None = None

    for i, c in enumerate(t):
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            str_start = i
            continue
        if c == "{":
            stack.append("}")
        elif c == "[":
            stack.append("]")
        elif c in ("}", "]"):
            if stack:
                stack.pop()
            if not stack:
                return []
        elif c == ",":
            last_comma = i
            last_comma_stack = list(stack)

    cands: list[str] = []
    if in_str and str_start > 0:
        before = t[:str_start].rstrip()
        if before.endswith(":"):
            s = t[:-1] if esc else t
            cands.append(s + '"' + "".join(reversed(stack)))
    if last_comma > 0 and last_comma_stack:
        cands.append(t[:last_comma] + "".join(reversed(last_comma_stack)))
    return cands


def _candidate_fixes(s: str) -> list[str]:
    no_comma = _TRAILING_COMMA_RE.sub(r"\1", s)
    smart_fixed = _TRAILING_COMMA_RE.sub(
        r"\1",
        _SMART_SINGLE_QUOTES_RE.sub("'", _SMART_DOUBLE_QUOTES_RE.sub('"', s)),
    )
    return [s, no_comma, smart_fixed]


def parse_loose(raw: str | None, array_key: str | None = None) -> dict[str, Any] | None:
    """
    Trả về {"data": dict, "salvaged": bool} hoặc None.
    Xử lý: <think> blocks, ```json fences, dấu phẩy thừa, ngoặc kép cong, và JSON bị cắt cụt.
    """
    t = strip_ai_wrappers(raw)
    if not t:
        return None

    starts = [m.start() for m in re.finditer(r'\{\s*"', t)]
    known_starts = [s for s in starts if _KNOWN_KEYS_RE.search(t[s:])]
    other_starts = [s for s in starts if not _KNOWN_KEYS_RE.search(t[s:])]
    ordered = known_starts + other_starts

    for st in ordered[:40]:
        end = balanced_end(t, st)
        if end < 0:
            continue
        candidate = t[st : end + 1]
        for fixed in _candidate_fixes(candidate):
            p = try_parse(fixed)
            if isinstance(p, dict):
                if not array_key or isinstance(p.get(array_key), list) or len(ordered) == 1:
                    return {"data": p, "salvaged": False}

    # Cứu các phần tử hoàn chỉnh của array_key khi JSON bị cắt cụt giữa chừng
    if array_key:
        for st in ordered:
            tail = t[st:]
            if f'"{array_key}"' not in tail:
                continue
            items = salvage_array(tail, array_key)
            if items:
                data: dict[str, Any] = {array_key: items}
                m = re.search(r'"(chunk_id|condition_id)"\s*:\s*"([^"]+)"', tail)
                if m:
                    data[m.group(1)] = m.group(2)
                return {"data": data, "salvaged": True}

    return None


def parse_requirements(raw: str | None) -> dict[str, Any]:
    """
    Parser chuyên biệt cho bước trích xuất Requirement từ các chunk tài liệu.
    Trả về {"data": dict, "salvaged": bool} hoặc {"fail": reason}.
    """
    t = strip_ai_wrappers(raw)
    if not t:
        return {"fail": "empty"}

    def has_real(o: Any) -> bool:
        if not isinstance(o, dict):
            return False
        if o.get("out_of_scope") is True:
            return True
        reqs = o.get("requirements")
        return isinstance(reqs, list) and any(
            isinstance(r, dict) and str(r.get("requirement") or "").strip() for r in reqs
        )

    starts = [m.start() for m in re.finditer(r'\{\s*"(?:features|requirements|out_of_scope)"', t)]
    if not starts:
        return {"fail": "no_json"}
    rev = list(reversed(starts))

    for st in rev:
        end = balanced_end(t, st)
        if end < 0:
            continue
        s = t[st : end + 1]
        for fixed in _candidate_fixes(s):
            p = try_parse(fixed)
            if has_real(p):
                return {"data": p, "salvaged": False}

    for st in rev:
        for cand in repair_candidates(t[st:]):
            for fixed in _candidate_fixes(cand):
                p = try_parse(fixed)
                if has_real(p):
                    return {"data": p, "salvaged": True}

    for st in rev:
        tail = t[st:]
        reqs = [
            r
            for r in salvage_array(tail, "requirements")
            if isinstance(r, dict) and str(r.get("requirement") or "").strip()
        ]
        if not reqs:
            continue
        data: dict[str, Any] = {"requirements": reqs}
        for k in (
            "features",
            "business_rules",
            "decision_tables",
            "inputs",
            "flows",
            "apis",
            "integrations",
            "data_objects",
            "states",
            "exceptions",
            "ambiguities",
        ):
            data[k] = salvage_array(tail, k)
        return {"data": data, "salvaged": True}

    return {"fail": "no_requirement"}


def _unescape_loose(s: str) -> str:
    p = try_parse('"' + s.replace("\n", "\\n") + '"')
    if isinstance(p, str):
        return p
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _read_loose_string(t: str, i: int) -> tuple[str, int, bool]:
    s: list[str] = []
    esc = False
    n = len(t)
    while i < n:
        c = t[i]
        if esc:
            s.append("\\" + c)
            esc = False
            i += 1
            continue
        if c == "\\":
            esc = True
            i += 1
            continue
        if c == '"':
            rest = t[i + 1 :]
            if re.match(r"^\s*(?:,|\]|\}|$)", rest):
                return _unescape_loose("".join(s)), i + 1, True
            s.append('"')
            i += 1
            continue
        s.append(c)
        i += 1
    return _unescape_loose("".join(s)), n, False


def _read_loose_array(t: str, open_bracket_idx: int, next_key_positions: list[int]) -> tuple[list[str], bool]:
    limit = len(t)
    for pos in next_key_positions:
        if open_bracket_idx < pos < limit:
            limit = pos
    sub = t[open_bracket_idx + 1 : limit]
    items: list[str] = []
    closed = False
    i = 0
    n = len(sub)
    while i < n:
        while i < n and sub[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if sub[i] == "]":
            closed = True
            break
        if sub[i] == '"':
            val, next_idx, str_closed = _read_loose_string(sub, i + 1)
            val_clean = re.sub(r"^[-*•]\s*", "", val.strip())
            if val_clean:
                items.append(f"- {val_clean}")
            i = next_idx
            if not str_closed:
                closed = False
                break
        elif sub[i] == "{":
            end_obj = balanced_end(sub, i)
            if end_obj > i:
                obj_str = sub[i : end_obj + 1]
                parsed_obj = try_parse(obj_str)
                if isinstance(parsed_obj, dict):
                    joined = ": ".join(str(v) for v in parsed_obj.values() if v)
                    items.append(f"- {joined}")
                else:
                    items.append(f"- {obj_str}")
                i = end_obj + 1
            else:
                break
        else:
            i += 1
    return items, closed


def _as_text(v: Any) -> str:
    if isinstance(v, list):
        lines: list[str] = []
        for x in v:
            line = x.strip() if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
            if not line:
                continue
            lines.append(line if line.startswith(("-", "*")) else f"- {line}")
        return "\n".join(lines)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, indent=1)
    return str(v or "")


def parse_analysis_report(raw: str | None) -> str:
    """
    Chuyển output JSON của AI_phan_tich_bai_toan thành văn bản báo cáo 6 mục chuẩn để đẩy vào Google Docs.
    Hỗ trợ cứu dữ liệu khi AI quên escape dấu " hoặc bị cắt cụt token.
    """
    t = strip_ai_wrappers(raw)
    if not t:
        return "Nội dung phân tích trống."

    section_keys_pattern = "|".join(k for k, _ in ANALYSIS_SECTIONS)
    starts = [m.start() for m in re.finditer(rf'\{{\s*"(?:{section_keys_pattern})"', t)]

    data: dict[str, Any] | None = None
    truncated = False

    for st in reversed(starts):
        end = balanced_end(t, st)
        if end < 0:
            continue
        s = t[st : end + 1]
        for fixed in _candidate_fixes(s):
            p = try_parse(fixed)
            if isinstance(p, dict):
                data = p
                break
        if data:
            break

    if not data:
        working_text = t[starts[-1] :] if starts else t
        key_positions: list[int] = []
        for k, _ in ANALYSIS_SECTIONS:
            matches = list(re.finditer(rf'"{k}"\s*:', working_text))
            if matches:
                key_positions.append(matches[-1].start())

        salvaged_data: dict[str, Any] = {}
        for k, _ in ANALYSIS_SECTIONS:
            matches = list(re.finditer(rf'"{k}"\s*:\s*([\[""])', working_text))
            if not matches:
                continue
            km = matches[-1]
            open_char = km.group(1)
            open_idx = km.end() - 1
            if open_char == '"':
                val, _, closed = _read_loose_string(working_text, open_idx + 1)
                if val.strip():
                    suffix = "" if closed else "\n[... nội dung bị cắt cụt do hết giới hạn token]"
                    salvaged_data[k] = val.strip() + suffix
                    if not closed:
                        truncated = True
            elif open_char == "[":
                items, closed = _read_loose_array(working_text, open_idx, key_positions)
                if items:
                    suffix = "" if closed else "\n[... danh sách bị cắt cụt do hết giới hạn token]"
                    salvaged_data[k] = "\n".join(items) + suffix
                    if not closed:
                        truncated = True
        if salvaged_data:
            data = salvaged_data

    if data:
        blocks: list[str] = []
        for key, title in ANALYSIS_SECTIONS:
            val = data.get(key)
            if val is not None and str(val).strip():
                blocks.append(f"{title}\n{_as_text(val).strip()}")
        combined = "\n\n".join(blocks)
        if truncated:
            combined += "\n\n(Lưu ý: kết quả AI dài vượt giới hạn token nên một số ý cuối cùng có thể bị lược bớt.)"
        if not combined.strip():
            combined = "\n\n".join(f"{k.upper()}:\n{_as_text(v)}" for k, v in data.items())
        return combined.strip()

    return f"Nội dung phân tích (AI không trả JSON hợp lệ):\n\n{t.strip()}"
