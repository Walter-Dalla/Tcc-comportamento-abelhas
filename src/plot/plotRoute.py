import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from utils.jsonUtils import importDataFromFile


def getInsectPositionFromFile(jsonFilePath):
    data = importDataFromFile(jsonFilePath)
    frame_count = data['frameCount']
    route = data['route']
    positionsForInsectOnFrame = []
    for i in range(frame_count):
        ponto = route[str(i)]
        positionsForInsectOnFrame.append([ponto['x'], ponto['y'], ponto['z']])
    return pd.DataFrame(positionsForInsectOnFrame, columns=['x', 'y', 'z'])

def updateAnimation(frame, points, pointAnimationObj, lineAnimationObj):
    pointAnimationObj.set_data(points.iloc[frame, 0], points.iloc[frame, 1])
    pointAnimationObj.set_3d_properties(points.iloc[frame, 2])
    
    # Atualizar a linha da rota até o ponto atual
    lineAnimationObj.set_data(points.iloc[:frame+1, 0], points.iloc[:frame+1, 1])
    lineAnimationObj.set_3d_properties(points.iloc[:frame+1, 2])
    
    return pointAnimationObj, lineAnimationObj

# Essa função limita o angulo da elevação e do Azimuth por pura estetica.
# Não há motivos para fazer essa limitação
# Fiz porque acho estranho o comportamento do grafico 
# Com elev e azim menor que 0 e maior que 89
def limitAngleAzimuthAndElevation(event):
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

def plotInsectRouteOnGraph(jsonFilePath, xlim, ylim, zlim):
    
    positionsForInsectOnFrame = getInsectPositionFromFile(jsonFilePath)
    
    global fig
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    
    ax.set_box_aspect([1,1,1])
    
    pointAnimationObj, = ax.plot([], [], [], 'ko') # ko é o ponto
    
    lineAnimationObj, = ax.plot([], [], [], 'b-')  # 'b-' é a linha azul
    
    ani = FuncAnimation(fig, updateAnimation, frames=len(positionsForInsectOnFrame), fargs=(positionsForInsectOnFrame, pointAnimationObj, lineAnimationObj), interval=100)
    
    fig.canvas.mpl_connect('motion_notify_event', limitAngleAzimuthAndElevation)
    
    plt.show()
