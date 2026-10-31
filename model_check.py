import os
from openai import OpenAI

api_key = os.getenv("NVIDIA_API_KEY")

if not api_key:
    raise ValueError(
        "NVIDIA_API_KEY is not set. "
        "Set it as an environment variable first."
    )

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key,
)

completion = client.chat.completions.create(
    model="nvidia/nemotron-3-super-120b-a12b",
    messages=[
        {
            "role": "user",
            "content": '''You are an advanced AI reasoning model.

Perform the following tests:

1. Explain how a GPU executes parallel computations.
2. Solve this problem: A ship travels 120 km in 4 hours.
   Calculate its average speed and show the calculation.
3. Write a Python function to check whether a number is prime.
4. Analyze this hypothetical ocean observation:
   Sea surface temperature = 31.5°C,
   wave height = 2.8 m,
   wind speed = 28 km/h.
   Explain potential risks without claiming access to live data.
5. Return a final summary of your results.

Be accurate, follow every instruction, and clearly state any uncertainty.'''
        }
    ],
    temperature=1,
    top_p=0.95,
    max_tokens=4096,
    extra_body={
        "chat_template_kwargs": {
            "enable_thinking": True
        }
    },
    stream=True,
)

for chunk in completion:
    if not chunk.choices:
        continue

    delta = chunk.choices[0].delta

    reasoning = getattr(delta, "reasoning_content", None)
    if reasoning:
        print(reasoning, end="", flush=True)

    if delta.content is not None:
        print(delta.content, end="", flush=True)

print()
