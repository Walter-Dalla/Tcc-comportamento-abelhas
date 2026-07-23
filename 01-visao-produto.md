# 01 — Visão de Produto (alto nível)

## O que é
Ferramenta de **software livre** para **análise comportamental de insetos** (abelhas, moscas, baratas) filmados em um ambiente controlado. A partir de dois vídeos do mesmo experimento, o sistema reconstrói a **trajetória do inseto em 3D** e deriva métricas de comportamento.

## Objetivo central
Extrair dados e metadados de rastreamento de insetos em vídeo — trajetória (x, y, z), tempo de voo, tempo de pouso e velocidade — para permitir a análise detalhada do comportamento dos insetos, em especial quando expostos a inseticidas e agrotóxicos.

## Motivação
Grupos de pesquisa da área dependem de softwares proprietários (ex.: Ethoflow), que cobram por análise e impedem a criação de novas funcionalidades. A proposta é uma alternativa aberta e **extensível pelo próprio pesquisador**.

## Requisitos que guiam o design
- Permitir adicionar **novos módulos de funcionalidade** ao código-fonte sem alterar o núcleo.
- Levantar dados de rastreio com precisão a partir dos vídeos.
- Exportar em formato **legível para humano** (relatório PDF + gráfico 3D interativo).
- Exportar em formato **padronizado para outras ferramentas** (JSON).
- Rodar **localmente**, sem internet, sem GPU e sem hardware específico (CPU apenas).
- Multiplataforma (Windows, Linux, macOS).

## Arquitetura em 4 grupos de módulos
| Sigla | Grupo | Responsabilidade |
|---|---|---|
| **IM** | Módulos de Interface | Interação com o usuário: perfis de análise, importação de vídeo, corte de bordas/perspectiva |
| **BM** | Módulos Básicos | Visão computacional: ROI, correção de perspectiva, remoção de fundo, detecção do inseto, rota, FPS |
| **MM** | Módulos de Metadados | Derivam informação a partir da rota (velocidade, tempo em borda). **Ponto de extensão do usuário** |
| **EM** | Módulos de Exportação | Persistência em disco, gráfico 3D, geração de PDF |

Os módulos são independentes entre si; a única junção é a camada de interface/visualização. Nenhum módulo executa sem ação explícita do usuário.

## Stack
Python + Tkinter (GUI), OpenCV (`opencv-python`, apenas CPU), NumPy, Matplotlib (gráfico 3D), Pisa (HTML → PDF), JSON como formato de dados.

## Estado atual (o que está feito)
- Ambiente controlado definido e validado em 3 cenários de teste.
- Pipeline completo funcionando: importação → configuração de perspectiva → processamento de vídeo → rota 3D → metadados → exportação.
- **MMs implementados:** `BorderModule` (tempo de voo/pouso e tempo por borda) e `SpeedModule` (velocidade).
- Perfis de análise persistidos e reutilizáveis/compartilháveis.
- Relatório PDF e gráfico 3D interativo funcionando.
- BMs ainda **não** são públicos/extensíveis (apenas os MMs são).

## Melhorias previstas para trabalhos futuros
- Melhorar a exportação/compartilhamento de perfis de análise.
- Testes automatizados padronizados.
- Padronizar IM, BM e EM para serem tão extensíveis quanto os MMs.
- Permitir configurar a **ordem de execução** dos MMs.
- Otimizar o BM dividindo o frame em sub-regiões com base na movimentação do inseto.
- Otimizar a análise do vídeo lateral para uma única coluna de altura em vez de matriz.
- Substituir partes críticas por bibliotecas em C ou Rust por desempenho.
