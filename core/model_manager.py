from openai import OpenAI
from config import MODELS, NVIDIA_NIM_BASE_URL


class NIMModel:
    def __init__(self, name, model, api_key, roles=None):
        self.name = name
        self.model = model
        self.roles = roles or ["general"]

        self.client = OpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=api_key,
            timeout=45.0,
            max_retries=0
)


class ModelManager:
    def __init__(self):
        self.models = [
            NIMModel(
                x["name"],
                x["model"],
                x["api_key"],
                x.get("roles")
            )
            for x in MODELS
        ]

        if not self.models:
            raise RuntimeError(
                "No NVIDIA NIM APIs configured. "
                "Create .env from .env.example."
            )

        self.current = 0

    def get_model(self):
        return self.models[self.current]

    def call(self, messages, max_tokens=2048, temperature=1):
        last_error = None

        for _ in range(len(self.models)):
            model = self.get_model()

            try:
                print(f"[NIM REQUEST] Calling {model.model}...",
                flush=True
                )
                response = model.client.chat.completions.create(
                    model=model.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False
                )

                return response.choices[0].message.content

            except Exception as exc:
                last_error = exc
                print(f"[NIM ERROR] {model.model}: "f"{type(exc).__name__}: {exc}",
                flush=True
                )
                self.current = (self.current + 1) % len(self.models)

        raise RuntimeError(
            f"All NVIDIA NIM APIs failed. Last error: {last_error}"
        )
