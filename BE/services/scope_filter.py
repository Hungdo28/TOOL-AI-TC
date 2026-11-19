from __future__ import annotations

import logging
import re
from typing import Any

LOGGER = logging.getLogger("autotc-backend")

SCOPE_STOPWORDS = {
    "chỉ", "chi", "phân", "tích", "phan", "tich", "kiểm", "thử", "kiem", "thu",
    "viết", "viet", "sinh", "tạo", "tao", "làm", "lam", "xử", "lý", "xu", "ly",
    "testcase", "testcases", "test", "case", "cases", "tc", "tcs", "kịch", "bản", "kich", "ban",
    "cho", "phần", "mục", "muc", "hệ", "he", "chức", "năng", "chuc", "nang",
    "màn", "hình", "man", "hinh", "luồng", "luong", "bài", "toán", "bai", "toan",
    "tập", "trung", "tap", "vào", "vao", "của", "cua", "các", "cac", "những", "nhung",
    "trong", "tài", "liệu", "tai", "lieu", "srs", "giúp", "giup", "tôi", "toi", "mình", "minh",
    "hãy", "hay", "yêu", "cầu", "yeu", "cau", "bổ", "sung", "bo", "thêm", "them",
    "tiết", "tiet", "đầy", "đủ", "day", "du", "toàn", "bộ", "toan", "tất", "cả", "tat", "ca",
    "negative", "boundary", "biên", "bien", "exception", "lỗi", "loi", "quyền", "quyen",
    "expected", "result", "trùng", "lặp", "trung", "lap", "gộp", "gop", "rà", "soát", "ra", "soat",
    "với", "voi", "và", "va", "hoặc", "hoac", "theo", "đúng", "dung", "phạm", "vi", "pham",
    "trên", "tren", "dưới", "duoi", "này", "nay", "đó", "do", "cần", "can", "muốn", "muon", "thôi", "thoi",
}


def extract_scope_tokens(user_prompt: str) -> list[str]:
    """Trích xuất các từ khóa định danh phân hệ/chức năng/màn hình từ prompt người dùng."""
    if not user_prompt or not user_prompt.strip():
        return []

    candidate_lines: list[str] = []
    lines = [ln.strip() for ln in user_prompt.strip().splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if ln.startswith("- [") or ln.startswith("DANH SÁCH TESTCASE") or ln.startswith("Các yêu cầu điều chỉnh trên là BẮT BUỘC"):
            continue
        if ln.startswith("YÊU CẦU ĐIỀU CHỈNH"):
            if i + 1 < len(lines):
                candidate_lines.append(lines[i + 1])
            continue
        candidate_lines.append(ln)

    raw_scope = " ".join(candidate_lines[:3])
    words = re.findall(r"[0-9a-zA-ZÀ-ỹ_/-]+", raw_scope.lower())
    return [w for w in words if w not in SCOPE_STOPWORDS and len(w) >= 2]


def filter_doc_by_user_scope(title: str, doc_text: str, user_prompt: str) -> str:
    """
    Tự động khoanh vùng tài liệu theo đúng phân hệ / chức năng người dùng yêu cầu trong user_prompt
    (VD: 'phân tích phần app agency', 'phân hệ CRM', 'báo cáo 52') trước khi đưa vào AI.
    Giữ lại phần giới thiệu chung, đúng các mục khớp phạm vi và các API liên quan trực tiếp.
    """
    scope_tokens = extract_scope_tokens(user_prompt)
    if not scope_tokens or not doc_text or len(doc_text) < 4000:
        return doc_text

    scope_phrase = " ".join(scope_tokens)
    lines = doc_text.split("\n")
    sections: list[dict[str, Any]] = []
    h1 = h2 = h3 = ""
    cur_level = 0
    cur_heading = ""
    cur_lines: list[str] = []

    def flush_sec() -> None:
        if cur_lines or cur_heading:
            sections.append(
                {
                    "level": cur_level,
                    "heading": cur_heading,
                    "h1": h1,
                    "h2": h2,
                    "h3": h3,
                    "body": "\n".join(cur_lines).strip(),
                }
            )

    for line in lines:
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            flush_sec()
            h1, h2, h3 = s[2:].strip(), "", ""
            cur_level, cur_heading, cur_lines = 1, s, [line]
        elif s.startswith("## ") and not s.startswith("### "):
            flush_sec()
            h2, h3 = s[3:].strip(), ""
            cur_level, cur_heading, cur_lines = 2, s, [line]
        elif s.startswith("### ") and not s.startswith("#### "):
            flush_sec()
            h3 = s[4:].strip()
            cur_level, cur_heading, cur_lines = 3, s, [line]
        else:
            cur_lines.append(line)
    flush_sec()

    if len(sections) <= 3:
        return doc_text

    def heading_matches(sec: dict[str, Any]) -> bool:
        target = f"{sec['h2']} {sec['h3']}".lower()
        if not target.strip():
            return False
        if len(scope_phrase) >= 3 and scope_phrase in target:
            return True
        return all(tok in target for tok in scope_tokens)

    matched_indices = {i for i, sec in enumerate(sections) if heading_matches(sec)}

    # Nếu không khớp trực tiếp trên tiêu đề ## / ###, thử tìm các mục có chứa đầy đủ từ khóa trong nội dung
    if not matched_indices:
        body_matches = {
            i
            for i, sec in enumerate(sections)
            if sec["level"] in (2, 3)
            and (
                (len(scope_phrase) >= 4 and scope_phrase in sec["body"].lower())
                or all(tok in sec["body"].lower() for tok in scope_tokens)
            )
        }
        if body_matches and len(body_matches) < len(sections) * 0.6:
            matched_indices = body_matches

    if not matched_indices:
        return doc_text

    matched_body_lower = "\n".join(sections[i]["body"].lower() for i in sorted(matched_indices))

    # Tự động giữ thêm các mục giới thiệu ngắn và các đặc tả API được gọi trong phân hệ đã chọn
    api_noise = {"api", "lấy", "xem", "danh", "sách", "thông", "tin", "chi", "tiết", "của", "theo", "từng", "cho", "hàng", "ngày", "cuối", "tháng"}
    kept_pieces: list[str] = [
        f"[PHẠM VI NGƯỜI DÙNG YÊU CẦU: {user_prompt.strip()} — Tài liệu dưới đây đã được lọc theo đúng phân hệ/chức năng yêu cầu]"
    ]
    for i, sec in enumerate(sections):
        h1_low = sec["h1"].lower()
        h2_low = sec["h2"].lower()
        is_intro = any(k in h1_low for k in ("giới thiệu", "tổng quan", "thông tin chung")) or (
            "danh mục mã trạng thái" in h2_low
        )
        if i in matched_indices:
            breadcrumb = " > ".join(x for x in (sec["h1"], sec["h2"], sec["h3"]) if x)
            kept_pieces.append(f"[Thuộc mục: {breadcrumb}]\n{sec['body']}")
        elif is_intro and len(sec["body"]) <= 4000:
            kept_pieces.append(sec["body"])
        elif ("api" in h1_low or h2_low.startswith("api ")) and sec["h2"]:
            api_words = [
                w
                for w in re.findall(r"[0-9a-zA-ZÀ-ỹ]+", h2_low)
                if w not in api_noise and len(w) >= 3
            ]
            if len(api_words) >= 2 and all(w in matched_body_lower for w in api_words[:3]):
                kept_pieces.append(f"[API liên quan: {sec['h1']} > {sec['h2']}]\n{sec['body']}")

    filtered_text = "\n\n".join(kept_pieces).strip()
    if filtered_text and len(filtered_text) < len(doc_text) * 0.9:
        LOGGER.info(
            "[%s] Đã lọc phạm vi tài liệu theo Prompt (%s): giữ %d/%d ký tự thuộc đúng phân hệ yêu cầu.",
            title,
            scope_phrase,
            len(filtered_text),
            len(doc_text),
        )
        return filtered_text
    return doc_text
