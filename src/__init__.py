from VelocityAnalizer.LocalVelocityAnalizer import localVelocityAnalizer
from imageAnalizer.frameAnalizer import get_frame_params
from Ui.PerspectiveUi import run_loop, show_ui
from utils.jsonUtils import exportDataToFile, importDataFromFile

import threading

sideVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/lado-v4.mp4"
topVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/cima-v4.mp4"
routeJson = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"

frameVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect.avi"
_frameVideo = "C:/Projetos/Tcc-comportamento-abelhas/resource/Frame.mp4"

# STEPS => ["route", "border-analises", "local-velocity", "trajectory-velocity"]

def startUp(screen):
    print("iniciando...")
    isDebugMode = True

    get_frame_params(frameVideo, isDebugMode, screen)



def velocityAnalisis(isDebugMode):
    print("local-velocity")

    data = importDataFromFile(routeJson)

    analizedData = localVelocityAnalizer(data["route"])
    print(analizedData)


def run_background_tasks(screen):
    background_thread = threading.Thread(target=startUp, args=[screen])
    background_thread.daemon = True
    background_thread.start()

if __name__ == "__main__":
    
    screen = show_ui()
    run_background_tasks(screen)
    run_loop(screen)




