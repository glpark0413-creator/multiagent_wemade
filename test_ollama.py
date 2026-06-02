from openai import OpenAI
import json

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

print("Ollama qwen2.5:7b 연결 테스트 중...")
resp = client.chat.completions.create(
    model="qwen2.5:7b",
    messages=[
        {"role": "system", "content": "항상 순수 JSON으로만 응답하라."},
        {"role": "user",   "content": '{"ok":true,"msg":"연결 성공"} 형식으로 응답해줘'},
    ],
    temperature=0.1,
)
print("응답:", resp.choices[0].message.content)
print("\n✅ 연결 성공! PM에서 사용 가능합니다.")
