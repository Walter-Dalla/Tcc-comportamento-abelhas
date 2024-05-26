import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Função para ler o arquivo JSON de pontos
def ler_arquivo_json(arquivo):
    with open(arquivo, 'r') as f:
        data = json.load(f)
    frame_count = data['frameCount']
    route = data['route']
    pontos = []
    for i in range(frame_count):
        ponto = route[str(i)]
        pontos.append([ponto['x'], ponto['y'], ponto['z']])
    return pd.DataFrame(pontos, columns=['x', 'y', 'z'])

# Função para atualizar a animação
def atualizar(frame, pontos, ponto_ani, linha_ani):
    ponto_ani.set_data(pontos.iloc[frame, 0], pontos.iloc[frame, 1])
    ponto_ani.set_3d_properties(pontos.iloc[frame, 2])
    
    # Atualizar a linha da rota até o ponto atual
    linha_ani.set_data(pontos.iloc[:frame+1, 0], pontos.iloc[:frame+1, 1])
    linha_ani.set_3d_properties(pontos.iloc[:frame+1, 2])
    
    return ponto_ani, linha_ani
def limitar_angulo(event):
    ax = event.inaxes
    if ax and ax.name == '3d':
        elev = ax.elev
        azim = ax.azim
        if elev > 89:
            ax.elev = 89
        elif elev < 0:
            ax.elev = 0
        if azim > 89:
            ax.azim = 89
        elif azim < 0:
            ax.azim = 0
        fig.canvas.draw_idle()

# Função principal para criar e exibir a animação
def criar_animacao(arquivo, xlim, ylim, zlim):
    # Ler os pontos do arquivo JSON
    pontos = ler_arquivo_json(arquivo)
    
    # Criar a figura e o eixo 3D
    global fig
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    # Configurar os limites do gráfico
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    
    # Configurar a proporção igual dos eixos
    ax.set_box_aspect([1,1,1])  # Aspect ratio is 1:1:1
    
    # Inicializar o ponto de animação
    ponto_ani, = ax.plot([], [], [], 'ko')
    
    # Inicializar a linha da rota
    linha_ani, = ax.plot([], [], [], 'b-')  # 'b-' é uma linha azul
    
    # Criar a animação
    ani = FuncAnimation(fig, atualizar, frames=len(pontos), fargs=(pontos, ponto_ani, linha_ani), interval=100)
    
    # Conectar o evento de limitação de ângulo
    fig.canvas.mpl_connect('motion_notify_event', limitar_angulo)
    
    # Mostrar a animação
    plt.show()
