import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from src.Modules.ExportModule.jsonUtils import import_data_from_file

def getInsectPositionFromFile(data):
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

def plot_insect_route_on_graph_animated(data, xlim, ylim, zlim):

    positionsForInsectOnFrame = getInsectPositionFromFile(data)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    ax.set_title('Gráfico 3D do movimento do inseto')
    
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    
    ax.set_box_aspect([1,1,1])
    
    pointAnimationObj, = ax.plot([], [], [], 'ko') # ko é o ponto
    
    lineAnimationObj, = ax.plot([], [], [], 'b-')  # 'b-' é a linha azul
    
    
    ani = FuncAnimation(fig, updateAnimation, frames=len(positionsForInsectOnFrame), fargs=(positionsForInsectOnFrame, pointAnimationObj, lineAnimationObj), interval=0.1)

    plt.show()



def plot_insect_route_on_graph_without_animation(jsonFilePath, xlim, ylim, zlim):
    positionsForInsectOnFrame = getInsectPositionFromFile(jsonFilePath)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    ax.set_title('Gráfico 3D do movimento do inseto')
    
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    
    ax.set_box_aspect([1, 1, 1])
    
    x_data = positionsForInsectOnFrame['x'].tolist()
    y_data = positionsForInsectOnFrame['y'].tolist()
    z_data = positionsForInsectOnFrame['z'].tolist()
    
    
    segments = []
    current_segment = []
    
    for x, y, z in zip(x_data, y_data, z_data):
        if x == -1 or y == -1 or z == -1:
            if current_segment:
                segments.append(current_segment)
                current_segment = [] 
        else:
            current_segment.append((x, y, z))
    
    if current_segment:
        segments.append(current_segment)
    
    for segment in segments:
        if segment:
            x_segment, y_segment, z_segment = zip(*segment)
            ax.plot(x_segment, y_segment, z_segment, 'b-')
    
    
    
    # visão de cima elev=90, azim=-90
    
    
    ax.view_init(elev=45, azim=-135)
    
    plt.show()
