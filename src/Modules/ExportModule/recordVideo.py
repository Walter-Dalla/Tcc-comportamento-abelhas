import cv2
import threading

def record_video(camera_index, output_file, frame_rate, sync_event, stop_event, queue, started_event, error_event):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Erro ao acessar a câmera {camera_index+1}")
        error_event.set()
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_file, fourcc, frame_rate, (width, height))

    while not stop_event.is_set():
        sync_event.wait()
        
        ret, frame = cap.read()
        if not ret:
            print(f"Erro ao capturar quadro da câmera {camera_index}.")
            break
        
        started_event.set()
        queue.put(frame)
        out.write(frame) 

    # Liberando recursos
    cap.release()
    out.release()
    print(f"Gravação finalizada para a câmera {camera_index}.")

def start_webcams(queue_side, queue_top, output_file_side, output_file_top, frame_rate):
    sync_event = threading.Event()
    stop_event = threading.Event()
    
    started_event_side = threading.Event()
    started_event_top = threading.Event()
    
    error_event_side = threading.Event()
    error_event_top = threading.Event()
    
    thread_side = threading.Thread(target=record_video, args=(0, output_file_side, frame_rate, sync_event, stop_event, queue_side, started_event_side, error_event_side))
    thread_top = threading.Thread(target=record_video, args=(1, output_file_top, frame_rate, sync_event, stop_event, queue_top, started_event_top, error_event_top))
    
    thread_side.start()
    thread_top.start()
    
    sync_event.set()
    
    return sync_event, stop_event, thread_side, thread_top, frame_rate, started_event_side, started_event_top, error_event_side, error_event_top