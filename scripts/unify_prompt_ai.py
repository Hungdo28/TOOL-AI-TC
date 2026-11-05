import json
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8", newline="") as f:
    text = f.read()

node = r"\$\('When Executed by Another Workflow'\)\.first\(\)\.json\.body"

# Hai dòng "Document-analysis prompt" / "Test-design prompt" -> một dòng Prompt AI
text = re.sub(
    r"- Document-analysis prompt: \{\{[^}]*\}\}\\n- Test-design prompt: (\{\{[^}]*\}\})",
    r"- User prompt: \1",
    text,
)

# body.promptAIx || body.promptAIy -> body.promptAI
text = re.sub(
    node + r"\.promptAI[12] \|\| " + node + r"\.promptAI[12]",
    "$('When Executed by Another Workflow').first().json.body.promptAI",
    text,
)

# Code node truyền tiếp
text = text.replace(
    "promptAI1: body.promptAI1,\\n        promptAI2: body.promptAI2",
    "promptAI: body.promptAI",
)
text = text.replace(
    "promptAI1: body.promptAI1,\\n      promptAI2: body.promptAI2",
    "promptAI: body.promptAI",
)
text = text.replace('"promptAI2": ""', '"promptAI": ""')

json.loads(text)  # đảm bảo JSON vẫn hợp lệ
with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("remaining:", len(re.findall(r"promptAI[12]", text)))
