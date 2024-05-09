# Tcc-comportamento-abelhas

Objetivo

-> Posição (x, y, z)
-> Velocidade
-> Aceleração (positiva ou negativa)
-> Direção
-> Orientação do inceto
-> Deteção de curvas fechadas
-> Recriar o movimento do inceto em um ambiente 3D
-> Detectar multiplos incetos ao mesmo tempo e distinguir individuos entre eles
-> Tempo de repouso no vidro

Objetivos já alcansados na prova de conceito:
-> Posição (x, y)
-> "Tempo" de repouso no vidro
-> Extração da rota do inceto


Problemas já identificados:

Video é somente um mokup para um teste de conseito
-> perspectiva da camera
-> não está contido dentro de um vidro
  L-> versão não tem interferia que o vidro pode gerar no resultado


Roadmap de melhorias:

1. Identificação do inceto
-> Meio da media pixels escuros na imagem
-> Introdução da perspectiva 3D do eixo da altura
-> Calculos de px -> cm
-> Calculo de frame -> tempo (s)
-> Crop da imagem ao redor do inceto 
  L-> Analise de imagem para mais detalhes
-> Detectar multiplos incetos ao mesmo tempo e distinguir individuos entre eles

2. Analise dos dados coletos para obter:
-> Velocidade
-> Aceleração (positiva ou negativa)
-> Direção
-> Orientação do inceto
-> Deteção de curvas fechadas

3. Integrações:
-> Recriar o movimento do inceto em um ambiente 3D