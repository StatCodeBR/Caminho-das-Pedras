"""Põe a raiz do pipeline no sys.path para os testes importarem `coleta`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
