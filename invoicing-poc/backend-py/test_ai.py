# Quick check: what does Groq say for this key and model? (Prints no secrets.)
from app.config import settings as s
import openai

c = openai.OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key)

try:
    print("Models your key can use:")
    print(sorted(m.id for m in c.models.list().data))
except openai.APIStatusError as e:
    print("Listing models failed:", e.status_code, e.message)

try:
    r = c.chat.completions.create(
        model=s.llm_model,
        messages=[{"role": "user", "content": "Reply with the single word OK"}],
        max_tokens=5,
    )
    print("Chat call worked:", r.choices[0].message.content)
except openai.APIStatusError as e:
    print("Chat call failed:", e.status_code, e.message)