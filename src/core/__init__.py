"""Core transversal da rearquitetura: schema, workspace e persistência.

Fase 1 — primitivas core. Sem lógica de domínio de estágio (Capture/Rectify/
Detect/Track/Fuse é Fase 3). Contém apenas os tipos de dado (Pydantic v2), a
abstração de `Workspace` e as stores atômicas.
"""
