from __future__ import annotations

import json
from typing import Any


def build_analysis_prompt(doc_data: str, user_scope_prompt: str) -> str:
    scope = user_scope_prompt.strip() if user_scope_prompt and user_scope_prompt.strip() else "Toàn bộ tài liệu"
    scope_for_footer = (
        user_scope_prompt.strip()
        if user_scope_prompt and user_scope_prompt.strip()
        else "No additional requirements."
    )
    return f"""You are a Senior Technical Business Analyst and QA Lead.
Your task is to thoroughly analyze the provided specifications, design documents, or raw text, and extract all technical and business details to produce a comprehensive, deep, and production-ready Technical Analysis Report.

CRITICAL SCOPE FILTERING RULE (HIGHEST PRIORITY):
- User Scope Request: {scope}
- If the "User Scope Request" specifies a specific function, screen, API, or module (e.g. "kiểm tra danh sách hồ sơ", "lấy OTP", "quên mật khẩu", etc.):
  1. You MUST FOCUS 100% of your analysis ONLY on that specific requested scope!
  2. Do NOT summarize or extract other unrelated modules, APIs, or screens from the document!
  3. Every section (APIs, business flows, data tables, test scenarios, risks) MUST revolve strictly around this requested scope.
- Only if the User Scope Request is "No additional requirements." or empty or explicitly asks for everything, then you analyze the entire document.

CORE PRINCIPLES & RULES:
1. Depth and Comprehensiveness (EXTREMELY IMPORTANT):
   - Provide an in-depth, thorough, and technically exhaustive analysis. Extract all technical parameters, flows, fields, and constraints.
   - DO NOT provide brief high-level summaries. DO NOT write vague 1-2 line descriptions. DO NOT omit critical technical specifications.
   - Each section must supply rich, concrete details (data types, endpoints, payload parameters, validations, sequential steps, status codes) so developers and QA engineers can directly work from this report.
2. Tone & Style: Professional, technical, structured, and rigorous, adhering to enterprise software design and architecture documentation standards.
3. Missing Information: Base your analysis strictly on the provided input within the target scope. If a critical detail is not specified in the document, explicitly state: "[Tài liệu chưa đặc tả chi tiết: ...] - Đề xuất: ..." and list it in section 6 (RỦI RO / ĐIỂM CHƯA RÕ).
4. Output Format: PURE JSON for automated parsing (no Markdown code block fences like ```json, no text outside the JSON object).
5. Output Language: ALL generated descriptive text and values inside the JSON MUST be written in VIETNAMESE (preserve technical names verbatim: API methods, endpoints, database table names, column/field names, status codes, error codes, and variable names).

JSON STRUCTURE (Return exactly 1 JSON object):
{{
  "muc_tieu_tai_lieu": "A comprehensive narrative in Vietnamese covering: (1) Business background and overview of the feature/system within the analyzed scope; (2) Core objectives and expected outcomes for end-users and the system; (3) Participating actors/roles and prerequisite conditions; (4) Specific functional boundary and business impact.",
  "he_thong_va_api": [
    "Detailed list of all participating systems, components, and every relevant API / Job / Queue in the scope. Follow this structure:",
    "- [System/Component] <System Name> - Architectural role, processing responsibility in the flow, interactions with other components.",
    "- [Method] <Endpoint URL> - <Detailed purpose> | Request Parameters: <detailed description of headers, query parameters, request body with required/optional flags and formats> | Response Data: <success payload structure, response codes> | Error Codes & Handling: <HTTP 200, 400, 401, 403, 500, business error codes> | Technical Notes: <authentication, token encryption, checksum if applicable>."
  ],
  "luong_nghiep_vu": [
    "Step-by-step detailed breakdown of all business flows and business rules in Vietnamese:",
    "- [Happy Path / Luồng chính]: Detailed sequential steps (Bước 1: Actor action -> Bước 2: System validation & checks -> Bước 3: API call & backend processing -> Bước 4: Database persistence / table updates -> Bước 5: UI response and user notification).",
    "- [Alternative Flows / Luồng rẽ nhánh]: User branch choices (e.g. different verification methods, payment types, supplementary document uploads).",
    "- [Exception Flows / Luồng ngoại lệ]: Specific handling for network failures, invalid/expired OTP, session timeout, duplicate records, backend service errors.",
    "- [Business Rules & Validations / Quy tắc nghiệp vụ]: Specific input validation conditions (field lengths, regex patterns, phone/ID formats, checksum algorithms, cross-field dependency validations).",
    "- Add '(CHÚ Ý): <note content>' at critical business logic points, security-sensitive steps, or high-risk areas."
  ],
  "bang_du_lieu": [
    "Detailed specification of every database table, collection, or data entity affected. Follow this structure:",
    "- [Tên Bảng/Table Name] - <Business meaning & role> | Core Columns/Fields: <field_name (data_type) - meaning, e.g. ID (PK), CUST_NAME (VARCHAR), STATUS (INT)...> | Keys & Relations (PK/FK): <foreign keys and relationships with other tables> | Status Lifecycle: <State transition diagram/flow with codes, e.g. CHO_DUYET (0) -> DA_DUYET (1) / TU_CHOI (2)>."
  ],
  "test_scenarios": [
    "Comprehensive test matrix covering deep testing angles in Vietnamese:",
    "- [Happy Path] End-to-end successful flows with complete valid data, verifying response data and database state updates.",
    "- [Validation & Data Constraints] Mandatory fields, empty inputs, boundary lengths, special characters, regex format (email, phone, dates, identity numbers), checksum checks.",
    "- [Business Logic & Branching] Branch conditions, entity state checks, duplicate prevention, retry limits, expiration behavior.",
    "- [Exceptions & Edge Cases] Boundary values, timeout, dropped network connection mid-flow, multiple invalid OTP attempts, cancellation mid-journey.",
    "- [Security & Authorization] Unauthorized access, missing/expired auth tokens, request payload tampering.",
    "- [Performance & Concurrency] Concurrent submissions (double-clicking, race conditions), high-load handling."
  ],
  "rui_ro_va_cau_hoi": [
    "Deep analysis of technical risks, business gaps, and clarification items:",
    "- [Technical & Security Risks]: Risks regarding security, performance, OTP/API spam, lack of rate-limiting, PII leakage, or missing idempotency/rollback mechanisms.",
    "- [Unspecified / Ambiguous Areas]: Edge cases or operational scenarios not clearly specified in the input document.",
    "- [Q&A Xác nhận BA]: <Specific clarification question for BA/SA> -> Đề xuất phương án: <Recommended solution or handling strategy>."
  ]
}}

STRICT OUTPUT RULES (mandatory):
- Do NOT think out loud. Do NOT write any analysis, plan, preamble, or explanation. Perform all reasoning silently.
- The FIRST character of your reply MUST be {{ and the LAST character MUST be }}.
- Output exactly ONE JSON object, parseable by JSON.parse(). No ```json code fences, no text outside the JSON, no trailing commas.
- Ensure all string values are properly escaped.

INPUT DATA TO ANALYZE:

Source Document:
{doc_data}

User Scope Request:
{scope_for_footer}"""


def build_requirement_extraction_prompt(
    *,
    task_name: str,
    chunk_data: str,
    chunk_index: int,
    total_chunks: int,
    is_last_chunk: bool,
    previous_feature_names: list[str] | None,
    user_prompt: str,
) -> str:
    req_prompt = user_prompt.strip() if user_prompt and user_prompt.strip() else "No additional requirements."
    prev_feats = ", ".join(previous_feature_names) if previous_feature_names else "none"
    last_flag = "true" if is_last_chunk else "false"
    return f"""You are a Senior Business Analyst and QA Architect.

USER SCOPE & ADDITIONAL REQUIREMENTS (HIGHEST PRIORITY OVERRIDE):
- User Request: {req_prompt}

CRITICAL SCOPE FILTERING RULE (MANDATORY):
- If the "User Request" above specifies a particular Use Case, feature, screen, API, or module (e.g. "kiểm tra danh sách hồ sơ", "lấy OTP", "quên mật khẩu"):
  1. You MUST extract ONLY the features, requirements, business_rules, inputs, flows, integrations, data_objects, states, and exceptions that belong directly to that requested scope!
  2. If the current document part contains ONLY unrelated features/modules, return an empty extraction immediately:
     {{"features": [], "requirements": [], "business_rules": [], "decision_tables": [], "inputs": [], "flows": [], "apis": [], "integrations": [], "data_objects": [], "states": [], "exceptions": [], "change_scope": {{"changed": [], "unchanged_but_impacted": []}}, "dependencies": [], "ambiguities": [], "out_of_scope": true}}
- Only if the "User Request" is "No additional requirements." or empty, you extract all requirements in this document part.

CONTEXT
Problem: {task_name}
Document part: {chunk_index} of {total_chunks}
This is the last part: {last_flag}
ID prefix for this part: P{chunk_index}-
Feature names already used in previous parts: {prev_feats}

TASK
Extract structured requirements at a DETAILED level for the target scope, sufficient for later steps to generate test cases using: Equivalence Partitioning, Boundary Value Analysis, Decision Table, State Transition, Negative testing, Regression.
- Do NOT generate Test Cases, Test Scenarios or Test Steps.
- Be COMPLETE but COMPACT within the requested scope: every string at most ~30 words and the SAME content must NOT be repeated under several keys. Leave "context" as an empty string.

DOCUMENT PARTS
- Extract ONLY what is stated in this part and strictly within the requested scope.
- ID NUMBERING: every ID starts with the ID prefix above and numbers from 001, e.g. "P2-FEAT001", "P2-REQ001".
- FEATURE NAMES: reuse exact feature_name from previous parts if continuing a flow; otherwise create a new one.

AMBIGUITIES
- If a detail is missing in this part, write exactly "Tài liệu hiện tại chưa đặc tả phần này." in the relevant field.
- Add to "ambiguities" ONLY contradictions, unclear wording, or unread images within the target scope.

IMAGES
- Markers like [HÌNH n: ...]: keep labels, button names, field names VERBATIM.
- If unread: do not guess, add to ambiguities as "Hình chưa đọc".

EXTRACTION RULES (applied only to the requested scope):
1. INPUT FIELDS: data type, required/optional, min/max length, format, valid values -> "inputs" and "requirements[].validation".
2. BRANCHING RULES: every IF/ELSE branch -> "business_rules". Multi-condition rules -> "decision_tables".
3. STATES: valid and invalid states for operations -> "states".
4. INTEGRATIONS: system, endpoint, trigger, payload, response, error codes, timeout -> "integrations".
5. DATA CHANGES: "table.column: value before -> value after" -> "data_objects[].data_change".
6. MESSAGES/LABELS: keep VERBATIM in "expected_behavior" or "error_handling".
7. EXCEPTIONS: reject, cancel, timeout, error -> "exceptions".
8. CHANGE SCOPE: "changed" vs "unchanged_but_impacted" flows -> "change_scope".
9. SPLIT FEATURES: 1 feature = 1 step/screen/flow. Max 8 requirements per feature.

JSON OUTPUT STRUCTURE:
{{
  "features": [
    {{ "feature_id": "P1-FEAT001", "feature_name": "", "description": "", "flow_order": 1 }}
  ],
  "requirements": [
    {{
      "requirement_id": "P1-REQ001",
      "feature_id": "P1-FEAT001",
      "type": "Screen name or business flow",
      "requirement": "",
      "context": "",
      "preconditions": [],
      "expected_behavior": "",
      "related_api": [],
      "related_fields": [],
      "related_state": [],
      "validation": [],
      "error_handling": []
    }}
  ],
  "business_rules": [
    {{ "rule_id": "P1-BR001", "requirement_id": "P1-REQ001", "condition": "", "expected_behavior": "" }}
  ],
  "decision_tables": [
    {{
      "table_id": "P1-DT001",
      "requirement_id": "P1-REQ001",
      "conditions": ["Condition name 1", "Condition name 2"],
      "rules": [
        {{ "rule_no": 1, "condition_values": ["Có", "Không"], "expected_action": "" }}
      ]
    }}
  ],
  "inputs": [
    {{
      "name": "",
      "required": null,
      "data_type": "",
      "min_length": null,
      "max_length": null,
      "format": "",
      "default_value": "",
      "valid_values": [],
      "constraints": []
    }}
  ],
  "flows": [
    {{
      "flow_id": "P1-FLOW001",
      "feature_id": "P1-FEAT001",
      "flow_name": "",
      "flow_order": 1,
      "preconditions": [],
      "steps": [ {{ "step": 1, "action": "", "system_behavior": "" }} ]
    }}
  ],
  "apis": [
    {{ "name": "", "method": "", "purpose": "", "input": "", "output": "" }}
  ],
  "integrations": [
    {{
      "integration_id": "P1-INT001",
      "requirement_id": "P1-REQ001",
      "system": "",
      "endpoint": "",
      "trigger_condition": "",
      "not_called_when": "",
      "request_payload": [],
      "response_success": "",
      "response_errors": [],
      "timeout_or_error_handling": "",
      "log_or_audit_location": ""
    }}
  ],
  "data_objects": [
    {{ "table_or_object": "", "field": "", "meaning": "", "allowed_values": [], "data_change": "" }}
  ],
  "states": [
    {{ "entity": "", "state": "", "meaning": "", "valid_for_processing": null, "transition_condition": "" }}
  ],
  "exceptions": [
    {{ "exception_id": "P1-EXC001", "requirement_id": "P1-REQ001", "scenario": "", "expected_behavior": "" }}
  ],
  "change_scope": {{
    "changed": [],
    "unchanged_but_impacted": []
  }},
  "dependencies": [
    {{ "source": "", "target": "", "dependency": "" }}
  ],
  "ambiguities": [
    {{ "related_requirement_id": "", "type": "", "description": "" }}
  ]
}}

STRICT OUTPUT RULES (mandatory):
- ESCAPE ALL QUOTES: if a string contains quotes, you MUST escape them (e.g., "Nút \\"Đăng nhập\\"").
- Do NOT think out loud. Do NOT write any analysis, plan, preamble or explanation.
- The FIRST character of your reply MUST be {{ and the LAST character MUST be }}.
- Output exactly ONE JSON object, parseable by JSON.parse(). No ```json fences, no text outside the JSON, no trailing commas.
- Keep every string short so the JSON is never cut off.

INPUT DATA:
{chunk_data}"""


def build_condition_generator_prompt(chunk: dict[str, Any], user_prompt: str) -> str:
    req_prompt = user_prompt.strip() if user_prompt and user_prompt.strip() else "No additional requirements."
    memory_text = str(chunk.get("memory_text") or "").strip() or "No reference samples yet."
    clean_chunk = {k: v for k, v in chunk.items() if k != "memory_text"}
    input_chunk_json = json.dumps(clean_chunk, ensure_ascii=False)

    return f"""You are a Senior QA Coverage Analyst and Test Designer.

TASK
Receive ONE GROUP of requirements (a chunk) belonging to one Test Suite (`context`) and expand it DIRECTLY into DETAILED Test Conditions, applying all testing techniques thoroughly, with enough data for the next step to generate immediately executable test cases. Do NOT generate Test Cases or Test Steps.

SINGLE SOURCE OF INFORMATION
Use only the data in "INPUT CHUNK" and "ADDITIONAL USER REQUIREMENTS". If the additional requirements conflict with the source document, the source document wins. Do NOT invent features, fields, Business Rules, APIs, tables/columns, statuses, messages or numeric limits. If something needs testing but the document does not state the result/limit: still create the Test Condition and put the missing detail in "requirement_gap" (do NOT guess behavior, do NOT invent boundary numbers).

MANDATORY TECHNIQUE SET (review every requirement/rule/field/state/integration in the chunk). The technique names below are exact Vietnamese labels that MUST be copied verbatim into `test_technique`:
A. EQUIVALENCE PARTITIONING (test_technique = "Phân vùng tương đương") for EVERY input field:
   - Valid classes: each valid value group stated in the document.
   - Invalid classes: empty string, null/not sent, whitespace only, wrong data type, wrong format, special characters, value outside allowed list, over-length (only when stated).
   - Optional fields: with value / without value.
B. BOUNDARY VALUES (test_technique = "Phân tích giá trị biên") for EVERY numeric/length/date/quantity constraint with stated limits: min-1, min, max, max+1 (skip values that do not exist). If no limit is stated: create 1 condition with "requirement_gap: Tài liệu chưa đặc tả giới hạn".
C. DECISION TABLE (test_technique = "Bảng quyết định") for EVERY rule depending on 2 or more conditions: list True/False combinations and every IF/ELSE branch (including the NOT-satisfied branch).
D. STATE TRANSITION (test_technique = "Chuyển trạng thái") for EVERY stateful entity: valid transitions, each INVALID state being rejected, repeated actions (submit twice, re-approve), actions on a final state.
E. NEGATIVE TESTING (test_technique = "Negative testing"): for EVERY successful action there must be a counterpart failure/reject/cancel condition; for EVERY system call: business error, stated error codes, timeout/system error, and the case where the system must NOT be called.
F. DATA & INTEGRATION (test_technique = "Kiểm tra dữ liệu/tích hợp"): verify table.column before/after for data changes; verify "no data change and no external system call" for reject/cancel/error scenarios; verify endpoint, payload fields, and call condition.
G. REGRESSION (test_technique = "Hồi quy"): verify remaining old flows are not affected based on "change_scope".
H. UI & FUNCTIONAL FLOWS (test_technique = "Use case" or "Phân vùng tương đương"): main flow (Happy path), alternative flows, UI display/default values/enable-disable/verbatim error messages.

RULES & GRANULARITY
1. NO OMISSIONS: every `requirement_id` in the chunk MUST appear in `requirement_ids` of AT LEAST 1 condition.
2. MERGING & GRANULARITY: 1 condition = 1 test object + 1 technique + 1 expected behavior (may group up to 6 specific classes/values/partitions that share the same technique/object into `test_data_hint`; each element of `test_data_hint` will become 1 separate test case in the next step). Do NOT merge classes whose expected behavior differs. Budget: at most 25 conditions for the whole chunk.
3. COUNTERPART PAIRS: Every Positive condition (approve/success, change triggered, valid state, found/duplicate, condition satisfied) MUST have its Negative/counterpart condition in the same list.
4. test_suite: keep the chunk's `suite_name` VERBATIM.
5. PRECONDITIONS (`preconditions`): describe SPECIFICALLY the data/configuration state required BEFORE testing (table, column, value, status, Mock Server setup for external timeout/error). Logging in / opening a screen is NOT a precondition.
6. TEST DATA (`test_data_hint`): list SPECIFIC data/partitions to use (max 6 elements per condition). Each element = 1 different class/value/combination = 1 test case in the next step.
7. EXPECTED RESULT (`expected_behavior_hint`): measurable/verifiable, keep messages, error codes, endpoints, table.column and values VERBATIM. Where the document says nothing: write "N/A (Tài liệu chưa đặc tả)" and record it in `requirement_gap`.
8. VERIFY POINTS (`verify_points`): state where to verify, ONLY the relevant items. All 4 sub-keys (`ui`, `network_api`, `log`, `database`) must always be present as arrays (use [] if empty).
9. ORDER: main flow -> alternative flows -> validation/boundaries -> exceptions/negative -> regression.

OUTPUT FORMAT
Return exactly ONE JSON object. All strings are natural Vietnamese (keep technical names unchanged). BE CONCISE: every string at most 25 words; fill `verify_points` only for relevant items, at most 2 points each. Empty arrays MUST be [], never use null or "None".
{{
  "chunk_id": "<keep the chunk_id from the input data>",
  "conditions": [
    {{
      "condition_id": "COND001",
      "requirement_ids": ["REQ001"],
      "test_suite": "<suite_name of the chunk>",
      "condition": "Clear description of what to verify",
      "context": "Context of this test condition",
      "condition_type": "Positive | Negative | Boundary | Regression",
      "test_technique": "Phân vùng tương đương | Phân tích giá trị biên | Bảng quyết định | Chuyển trạng thái | Negative testing | Kiểm tra dữ liệu/tích hợp | Hồi quy | Use case",
      "preconditions": [],
      "test_data_hint": [],
      "expected_behavior_hint": [],
      "verify_points": {{ "ui": [], "network_api": [], "log": [], "database": [] }},
      "related_api": [],
      "related_fields": [],
      "related_state": [],
      "requirement_gap": null
    }}
  ]
}}

STRICT OUTPUT RULES (mandatory):
- ESCAPE ALL QUOTES: If any string contains double quotes, you MUST escape them (e.g., "Thông báo \\"Thành công\\"").
- Do NOT think out loud. Do NOT write any analysis, plan, preamble or explanation. Do the reasoning silently.
- The FIRST character of your reply MUST be {{ and the LAST character MUST be }}.
- Output exactly ONE JSON object, parseable by JSON.parse(). No ```json fences, no text outside the JSON, no trailing commas.
- If you are running out of output length, close the JSON structure properly and shorten the content instead of writing at length.

ADDITIONAL USER REQUIREMENTS (MANDATORY QA INSTRUCTIONS - prioritize requested Use Case scope, test scenarios, template style, and preserve/expand any unclear business points or Q&A for BA in "requirement_gap" as "[Q&A confirm BA: ...]"):
- User prompt: {req_prompt}

EXPERIENCE FROM PREVIOUS PROBLEMS (QA-approved test cases; REFERENCE ONLY for coverage level and techniques applied to similar features). Do NOT copy values, messages, APIs or field names from here; ignore any sample unrelated to the INPUT CHUNK; if it conflicts with the current document, the current document is always right:
{memory_text}

INPUT CHUNK:
{input_chunk_json}"""


def build_testcase_generator_prompt(conditions: list[dict[str, Any]], user_prompt: str) -> str:
    req_prompt = user_prompt.strip() if user_prompt and user_prompt.strip() else "No additional requirements."
    conds_json = json.dumps(conditions, ensure_ascii=False)

    return f"""You are a Senior QA Engineer.

TASK
Generate Test Cases in the style of the team's manual checklist (columns: Mục đích kiểm thử / Các bước thực hiện (Pre + Step) / Kết quả mong muốn), based ONLY on the provided list of Test Conditions (each handled INDEPENDENTLY, with requirement_context when present) and the "ADDITIONAL USER REQUIREMENTS".

ANTI-FABRICATION (HIGHEST PRIORITY)
- Every test case MUST be traceable to the condition / requirement_context / test_data_hint / expected_behavior_hint / verify_points. NEVER invent screens, buttons, fields, menu paths, API endpoints, tables/columns, statuses, values, messages, error codes or business rules that are not in the input.
- If a detail needed by a step or an expected result is not in the input, write exactly "N/A (Tài liệu chưa đặc tả)" instead of guessing. Messages, labels, endpoints, table.column and values are copied VERBATIM from the input.
- Do NOT create a test case for something no condition asks for. Do NOT drop a partition the condition asks for (coverage must stay complete).

TEST CASE SPLITTING RULES
1 Test Condition IS NOT 1 Test Case. For EACH condition, first LIST THE SPLIT PLAN in "phan_vung_ap_dung" (each element = 1 class/value/combination/state transition/response = 1 test case). Then "testcases" MUST contain EXACTLY as many elements as the plan (do not merge, do not skip). At most 6 partitions per condition: if there are more, pick 6 representative ones (prefer boundaries and invalid classes that differ in behavior).
By condition.test_technique:
- "Phân vùng tương đương": 1 TC per class (each element of test_data_hint). Empty, null/not sent, whitespace only, wrong type/format, special characters, outside allowed list = DIFFERENT TCs. One error per TC: other fields stay valid.
- "Phân tích giá trị biên": 1 TC per boundary value (min-1, min, max, max+1 - only those that exist), exact value stated in the step.
- "Bảng quyết định": 1 TC per combination; state the value of EVERY condition in Pre.
- "Chuyển trạng thái": 1 TC per valid transition; 1 per invalid state; 1 for repeated action.
- "Negative testing": 1 TC per error response/code/timeout/system error; reject/cancel TCs verify NO database update and NO external call.
- "Hồi quy": 1 TC per affected old flow, verifying the old behavior is unchanged.
- "Kiểm tra dữ liệu/tích hợp": 1 TC per table/column or endpoint/payload (or merged into the same success TC if same scenario, but list EVERY table.column / payload field).
- "Use case": main flow and each alternative flow = 1 TC each.
If the document lacks data to split, still write 1 TC and put "N/A (Tài liệu chưa đặc tả)" where the result is missing.

DATA FIELDS (all text values in Vietnamese)
- "test_suite": keep verbatim from the condition.
- "muc_dich": MUST START with "Kiểm tra", "Xác minh" or "Validate". Like the checklist: short and specific, naming the object + the scenario/value/state, e.g. "Check trùng vé - Trường hợp tồn tại vé đang ACTIVE còn hiệu lực". Each TC has a DIFFERENT purpose; never generic.
- "dieu_kien_tien_quyet" (array) = the "Pre:" block. ANALYSE FULLY every data/config/permission state needed BEFORE the first step, so the tester can prepare data without guessing. Walk through this checklist and include each item that applies AND is present in the input: (1) account/customer/contract/vehicle state and the specific data used (plate, id, balance...); (2) table.column = value for every record that must exist or must NOT exist (include comparison like EXP_DATE >= SYSDATE if the input has it); (3) system/config switches (e.g. FUND_ID/STATUS) and their on/off state; (4) the specific test data of THIS partition; (5) for error/exception TCs: Mock Server setup (which endpoint returns which response/timeout); (6) for multi-object TCs (e.g. xe A and xe B): the state of EACH object. One fact per element, no numbering. Do NOT put login / opening a screen / clicking in Pre. If truly nothing is needed, return [].
- "cac_buoc" (array) = the "Step:" block. One tester action per element, no numbering inside the string. Normally start with "Đăng nhập thành công" (only if the operation is on the UI), then navigate (only screens/menus named in the input), then enter/select data with SPECIFIC VALUES (field/button names from the input), then the VERIFICATION step(s) per verify_points:
    + UI: observe message/label/button state.
    + Network: open F12 -> Network, filter the endpoint, perform the action, check request payload and response.
    + Log: check the server log / audit table (name it only if the input names it).
    + Database: query exactly the table/column named in the input before and after the action.
  Add verification steps ONLY for the types present in verify_points.
- "ket_qua_mong_muon" (array): each element is the result of ONE verification step and MUST START with that step's number in "cac_buoc" (e.g. "6. - Hiển thị ..."). Use "- " bullets for several outcomes of the same step, separated by line break. Must be MEASURABLE: verbatim message; endpoint called / NOT called, payload fields, response code; "table.column = value (before -> after)" or "keeps the previous value, no new record". Generic phrases ("xử lý thành công", "đồng bộ thành công") are FORBIDDEN.

OUTPUT FORMAT
Return exactly ONE JSON object. All strings Vietnamese and CONCISE: each step at most 20 words, each result item at most 30 words (keep messages/codes verbatim). Array fields MUST be [], never null or "None". Each test case has EXACTLY 5 keys: test_suite, muc_dich, dieu_kien_tien_quyet, cac_buoc, ket_qua_mong_muon. Structure: {{"results": [ {{"condition_id", "phan_vung_ap_dung", "testcases"}}, ... ]}}. Each input condition has EXACTLY 1 element in "results" (same order, none skipped). Keep "condition_id" verbatim.
The example ONLY illustrates format and splitting (do NOT copy content):
{{
  "results": [
    {{
      "condition_id": "<condition_id from the input>",
      "phan_vung_ap_dung": [
        "Số lượng = 0 (dưới biên min = 1)",
        "Số lượng = 1 (biên min)"
      ],
      "testcases": [
        {{
          "test_suite": "Màn hình Đặt hàng",
          "muc_dich": "Validate hệ thống từ chối khi nhập Số lượng = 0 (dưới biên min = 1)",
          "dieu_kien_tien_quyet": ["Tồn tại sản phẩm mã SP01 trong bảng PRODUCT với cột STATUS = 1"],
          "cac_buoc": [
            "Đăng nhập thành công",
            "Vào màn hình Đặt hàng",
            "Chọn sản phẩm SP01",
            "Nhập trường Số lượng = 0",
            "Nhấn nút Đặt hàng",
            "Quan sát thông báo trên giao diện",
            "Truy vấn bảng ORDERS theo mã SP01"
          ],
          "ket_qua_mong_muon": [
            "6. - Hiển thị thông báo \\"Số lượng phải từ 1 đến 99\\"\\n- Không gọi API tạo đơn hàng (tab Network không có request tới endpoint tạo đơn)",
            "7. - Bảng ORDERS không phát sinh bản ghi mới cho SP01"
          ]
        }},
        {{
          "test_suite": "Màn hình Đặt hàng",
          "muc_dich": "Xác minh hệ thống cho phép đặt hàng khi Số lượng = 1 (biên min)",
          "dieu_kien_tien_quyet": ["Tồn tại sản phẩm mã SP01 trong bảng PRODUCT với cột STATUS = 1"],
          "cac_buoc": [
            "Đăng nhập thành công",
            "Vào màn hình Đặt hàng",
            "Chọn sản phẩm SP01",
            "Nhập trường Số lượng = 1",
            "Nhấn nút Đặt hàng",
            "Quan sát thông báo trên giao diện",
            "Truy vấn bảng ORDERS theo mã SP01"
          ],
          "ket_qua_mong_muon": [
            "6. - Hiển thị thông báo \\"Đặt hàng thành công\\"",
            "7. - Bảng ORDERS phát sinh 1 bản ghi mới với cột QUANTITY = 1"
          ]
        }}
      ]
    }}
  ]
}}

STRICT OUTPUT RULES (mandatory):
- Do NOT think out loud. Do NOT write any analysis, plan, preamble or explanation. Do the reasoning silently.
- The FIRST character of your reply MUST be {{ and the LAST character MUST be }}.
- Output exactly ONE JSON object, parseable by JSON.parse(). No ```json fences, no text outside the JSON, no trailing commas.
- If you are running out of output length, close the JSON structure properly and shorten the content instead of writing at length.

ADDITIONAL USER REQUIREMENTS (a second valid source besides the document; if they conflict with the source document, the source document wins):
- User prompt: {req_prompt}

INPUT LIST OF TEST CONDITIONS (array, each element handled independently):
{conds_json}"""
