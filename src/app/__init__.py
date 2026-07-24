"""Camada de interface (Fase 4): CLI headless e GUI Tk sobre a MESMA orquestração.

`src/app/cli.py` (Typer) e `src/app/gui/` (Tkinter) são os dois pontos de entrada.
Ambos convergem para `src/app/runner.py`, que monta e roda a pipeline via
`src.stages.orchestration.run_cpu_analysis` — caminho idêntico, sem lógica
duplicada. A GUI nunca entra na pipeline; o CLI nunca importa Tkinter.
"""
