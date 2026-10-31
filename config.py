import os
from dotenv import load_dotenv

load_dotenv()

NVIDIA_NIM_BASE_URL = os.getenv(
    "NVIDIA_NIM_BASE_URL",
    "https://integrate.api.nvidia.com/v1"
)

MODELS = []

for i in range(1, 11):
    key = os.getenv(f"NVIDIA_NIM_{i}_KEY")
    model = os.getenv(f"MODEL_{i}")

    if key and model:
        MODELS.append({
            "name": f"nim_{i}",
            "model": model,
            "api_key": key,
            "roles": ["general"]
        })
