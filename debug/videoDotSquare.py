import cv2
import numpy as np

def add_moving_point_to_frame_top(frame, t, width, height, totalTime):
    parcelaTempo = totalTime / 8
    tempoCorteAtual = int(t // parcelaTempo) + 1  # Determine which segment the current time falls into
    
    pontos = [
        (30, 112),
        (441, 114),
        (30, 740),
        (460, 710)
    ]
    
    pontoAtual = pontos[0]
    
    if tempoCorteAtual == 1 or tempoCorteAtual == 4:
        pontoAtual = pontos[0]
    elif tempoCorteAtual == 2 or tempoCorteAtual == 3:
        pontoAtual = pontos[1]
    elif tempoCorteAtual == 5 or tempoCorteAtual == 6:
        pontoAtual = pontos[2]
    elif tempoCorteAtual == 7 or tempoCorteAtual == 8:
        pontoAtual = pontos[3]
    
    cv2.circle(frame, pontoAtual, 5, (0, 0, 0), -1)

    return frame


def add_moving_point_to_frame_side(frame, t, width, height, totalTime):
    parcelaTempo = totalTime / 8
    tempoCorteAtual = int(t // parcelaTempo) + 1  # Determine which segment the current time falls into
    
    pontos = [
        (30, 112),
        (441, 114),
        (30, 740),
        (460, 710)
    ]
    
    pontoAtual = pontos[0]
    
    if tempoCorteAtual == 4 or tempoCorteAtual == 5:
        pontoAtual = pontos[0]
    elif tempoCorteAtual == 3 or tempoCorteAtual == 8:
        pontoAtual = pontos[1]
    elif tempoCorteAtual == 1 or tempoCorteAtual == 6:
        pontoAtual = pontos[2]
    elif tempoCorteAtual == 2 or tempoCorteAtual == 7:
        pontoAtual = pontos[3]
    
    cv2.circle(frame, pontoAtual, 5, (0, 0, 0), -1)

    return frame

def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f'Clicked position: x={x}, y={y}')
        

def sla(frame):
    cv2.imshow("image", frame)
        
    cv2.setMouseCallback('image', click_event)
    cv2.waitKey(0)
        
        
def process_video(input_video_path, output_video_path):
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        return

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out_top = cv2.VideoWriter(output_video_path+"_top.avi", fourcc, fps, (width, height))
    out_side = cv2.VideoWriter(output_video_path+"_side.avi", fourcc, fps, (width, height))
    
    
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    totalTime = frame_count / fps

    for frame_idx in range(frame_count):
        ret, frame = cap.read()
        #sla(frame)
        if not ret:
            break

        t = frame_idx / fps
        
        frameTop = frame.copy()
        
        frame_top = add_moving_point_to_frame_top(frame, t, width, height, totalTime)
        frame_side = add_moving_point_to_frame_side(frameTop, t, width, height, totalTime)
        out_top.write(frame_top)
        out_side.write(frame_side)

    cap.release()
    out_top.release()
    out_side.release()

# Exemplo de uso
input_video_path = "C:/Projetos/Tcc-comportamento-abelhas/resource/Frame.mp4"  # Substitua pelo caminho do seu vídeo de entrada
output_video_path = 'C:/Projetos/Tcc-comportamento-abelhas/resource/square'  # Substitua pelo caminho do seu vídeo de saída
process_video(input_video_path, output_video_path)

