"""Modelos Pydantic v2 do core (Fase 1).

Cada saída de estágio da arquitetura alvo é um modelo tipado aqui; a pipeline
passa `AnalysisContext` tipado em vez de um dict cru (substitui o
"dict-god-object" legado).
"""
