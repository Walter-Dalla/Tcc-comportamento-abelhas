import concurrent.futures

from imageAnalizer.moviment.sideAnalizer import analyze_frame_side
from imageAnalizer.moviment.topAnalizer import analyze_frame_top
from utils.jsonUtils import exportDataToFile

def route(isDebugMode, topVideoInput, sideVideoInput, outputLocation):

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_top = executor.submit(analyze_frame_top, topVideoInput, isDebugMode)
        future_side = executor.submit(analyze_frame_side, sideVideoInput, isDebugMode)

        dataTop = future_top.result()
        dataSide = future_side.result()

    topRouteCount = len(dataTop["route"])
    sideRouteCount = len(dataSide["route"])

    print(topRouteCount, sideRouteCount)
    
    frameCount = sideRouteCount
    if(topRouteCount > sideRouteCount):
        frameCount = topRouteCount

    data = {"route": {}, "frameCount": frameCount }
    
    for index in range(frameCount):
        y = dataSide["route"][index]["y"]
        #x2 = dataSide["route"][index]["x"]

        x = dataTop["route"][index]["x"]
        z = dataTop["route"][index]["z"]

        #print(index, x, y, z)
        #print(index, x2, y, z)

        data["route"][index] = {
            "x": x, 
            "y": y,
            "z": z,
            #"x2": x2
        }

    print(data)

    exportDataToFile(data, outputLocation)