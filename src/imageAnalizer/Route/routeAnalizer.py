import concurrent.futures
from imageAnalizer.movimentAnalizer import analyze_frame_side, analyze_frame_top
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
        x = dataSide["route"][index]["x"]
        y = dataSide["route"][index]["y"]

        x2 = dataTop["route"][index]["x"]
        z = dataTop["route"][index]["z"]

        #print(index, x, y, z)
        #print(index, x2, y, z)

        data["route"][index] = {
            "x":x, 
            "y": y,
            "z": z
        }

    print(data)

    exportDataToFile(data, outputLocation)