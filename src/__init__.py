from imageAnalizer.movimentAnalizer import analyze_frame_top, analyze_frame_side
from VelocityAnalizer.LocalVelocityAnalizer import localVelocityAnalizer
from imageAnalizer.frameAnalizer import get_frame_params
from Ui.PerspectiveUi import run_loop, show_ui
from utils.jsonUtils import exportDataToFile, importDataFromFile
import concurrent.futures
import threading


steps = ["route", "border-analises", "local-velocity", "trajectory-velocity"]

sideVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/lado-v4.mp4"
topVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/cima-v4.mp4"
routeJson = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"

frameVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect.avi"
_frameVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/Frame.mp4"

# STEPS => ["route", "border-analises", "local-velocity", "trajectory-velocity"]

def startUp():
    print("iniciando...")
    isDebugMode = True

    if "route" in steps:
        route(isDebugMode)

    #if "local-velocity" in steps:
     #   velocityAnalisis(isDebugMode)


def velocityAnalisis(isDebugMode):
    print("local-velocity")

    data = importDataFromFile(routeJson)

    analizedData = localVelocityAnalizer(data["route"])
    print(analizedData)


def route(isDebugMode):

    get_frame_params(frameVideo, isDebugMode)

    return

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_top = executor.submit(analyze_frame_top, topVideo, isDebugMode)
        future_side = executor.submit(analyze_frame_side, sideVideo, isDebugMode)

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

    exportDataToFile(data, routeJson)


def run_background_tasks():
    background_thread = threading.Thread(target=startUp)
    background_thread.daemon = True
    background_thread.start()

if __name__ == "__main__":
    
    show_ui()
    run_background_tasks()
    run_loop()




