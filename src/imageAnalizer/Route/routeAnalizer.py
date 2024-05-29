import concurrent.futures

from imageAnalizer.moviment.sideAnalizer import analyze_frame_side
from imageAnalizer.moviment.topAnalizer import analyze_frame_top
from utils.jsonUtils import exportDataToFile

def route(topVideoInput, sideVideoInput, outputLocation):

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_top = executor.submit(analyze_frame_top, topVideoInput)
        future_side = executor.submit(analyze_frame_side, sideVideoInput)

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

        x = dataTop["route"][index]["x"]
        z = dataTop["route"][index]["z"]

        data["route"][index] = {
            "x": x, 
            "y": y,
            "z": z,
        }

    exportDataToFile(data, outputLocation)