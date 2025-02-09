from queue import Queue
import time
from src.Modules.ExportModule.recordVideo import start_webcams
from src.Modules.ExportModule.folderUtils import assert_dir_exists
from PIL import Image, ImageTk

def prepare_recording(cache, entry):
        output_dir = "./records/"
        
        assert_dir_exists(output_dir)
        
        date_time = time.strftime("%Y%m%d_%H%M%S")
        
        output_file_side = output_dir+date_time+"_side.avi"
        output_file_top = output_dir+date_time+"_top.avi"
        
        frame_rate = int(entry["fps"].get())
        
        queue_side = Queue()
        queue_top = Queue()
        
        sync_event, stop_event, thread_side, thread_top, frame_rate, started_event_side, started_event_top, error_event_side, error_event_top, start_recording_event_side, start_recording_event_top = start_webcams(queue_side, queue_top, output_file_side, output_file_top, frame_rate)
        
        cache["stop_event"] = stop_event
        cache["thread_side"] = thread_side
        cache["thread_top"] = thread_top
        cache["start_recording_event_side"] = start_recording_event_side
        cache["start_recording_event_top"] = start_recording_event_top
        cache["sync_event"] = sync_event
        cache["started_event_side"] = started_event_side
        cache["started_event_top"] = started_event_top
        cache["error_event_side"] = error_event_side
        cache["error_event_top"] = error_event_top
        
        cache["queue_side"] = queue_side
        cache["queue_top"] = queue_top
        
def get_image_from_frame_queue(self, queue, image_size):
    try:
        frame = queue.get(timeout=1)
        image = Image.fromarray(frame)
    except:
        image = Image.new("RGB", image_size, "black")
    
    imageTk = ImageTk.PhotoImage(image)
    return imageTk

def stop_recording(cache):
    cache["stop_event"].set()
    
    cache["thread_side"].join()
    cache["thread_top"].join()
           
        