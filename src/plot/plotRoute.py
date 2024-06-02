import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from src.utils.jsonUtils import import_data_from_file

def getInsectPositionFromFile(jsonFilePath):
    data = import_data_from_file(jsonFilePath)
    frame_count = data['frame_count']
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

# az -180 até -90
# ele 0 até 180

def limitAngleAzimuthAndElevation(event):
    return
    ax = event.inaxes
    if ax and ax.name == '3d':
        elev = ax.elev
        azim = ax.azim
        if elev > 89:
            ax.elev = 89
        elif elev < 0:
            ax.elev = 0
        if azim > -90:
            ax.azim = -89
        elif azim < -180:
            ax.azim = -179
        fig.canvas.draw_idle()

def plot_insect_route_on_graph(jsonFilePath, xlim, ylim, zlim):
    
    positionsForInsectOnFrame = getInsectPositionFromFile(jsonFilePath)
    
    global fig
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    ax.set_title('Gráfico 3D do movimento do inceto')
    
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    
    ax.set_box_aspect([1,1,1])
    
    pointAnimationObj, = ax.plot([], [], [], 'ko') # ko é o ponto
    
    lineAnimationObj, = ax.plot([], [], [], 'b-')  # 'b-' é a linha azul
    
    
    ani = FuncAnimation(fig, updateAnimation, frames=len(positionsForInsectOnFrame), fargs=(positionsForInsectOnFrame, pointAnimationObj, lineAnimationObj), interval=100)
    
    fig.canvas.mpl_connect('motion_notify_event', limitAngleAzimuthAndElevation)
    
    plt.show()
