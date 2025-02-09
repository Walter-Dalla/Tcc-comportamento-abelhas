import threading
from tkinter import ttk
from PIL import Image, ImageTk

from src.Modules.InterfaceModule.recodWebCamVideo.recordWebcamController import get_image_from_frame_queue, prepare_recording, stop_recording
from src.Modules.ExportModule.folderUtils import assert_dir_exists
from src.Modules.ExportModule.recordVideo import start_webcams
from src.utils.interfaceUtils import show_frame

class RecordWebcamVideoUI:
    def __init__(self, root, main_frame):
        self.root = root
        
        self.main_frame = main_frame
        self.finished = False
        self.kill_all_threads = threading.Event()
        
        self.buttons = {}
        self.labels = {}
        self.entry = {}
        self.cache = {
            "image":{
                "top": None,
                "side": None
            }
        }

    
    def prepare_recording(self):
        prepare_recording(self.cache, self.entry)
        
        self.init_waiting_for_webcams_screen_state()
        
        while(not (self.cache["sync_event"].is_set() 
                and (self.cache["started_event_side"].is_set() or self.cache["error_event_side"].is_set())
                and (self.cache["started_event_top"].is_set() or self.cache["error_event_top"].is_set())
            )
        ):
            count = 1
        
        self.cache["thread_show_recoding_video"] = threading.Thread(target=self.show_recoding_video)
        self.cache["thread_show_recoding_video"].start()
        
        self.prepare_recording_screen_state()

    def init_recording(self):
        self.cache["start_recording_event_side"].set()
        self.cache["start_recording_event_top"].set()
        
        self.init_recording_screen_state()

    def show_recoding_video(self):
        image_size = (400, 400)
        first = True
        
        queueSide = self.cache["queue_side"]
        queueTop = self.cache["queue_top"]
        error_event_side = self.cache["error_event_side"]
        error_event_top = self.cache["error_event_top"]
        
        try:
            while(not self.cache["stop_event"].is_set()):
                
                if(not error_event_side.is_set()):
                    imageTkSide = get_image_from_frame_queue(queueSide, image_size)
                    self.labels["side_image"].config(image=imageTkSide)
                    self.cache["image"]["side"] = imageTkSide
                else:
                    image = Image.new("RGB", image_size, "black")
                    imageTkSide = ImageTk.PhotoImage(image)
        
                    self.labels["side_image"].config(image=imageTkSide)
                    self.cache["image"]["side"] = imageTkSide
                
                if(not error_event_top.is_set()):
                    imageTkTop = get_image_from_frame_queue(queueTop, image_size)
                    self.labels["top_image"].config(image=imageTkTop)
                    self.cache["image"]["top"] = imageTkTop
                else:
                    image = Image.new("RGB", image_size, "black")
                    imageTkTop = ImageTk.PhotoImage(image)
                    
                    self.labels["top_image"].config(image=imageTkTop)
                    self.cache["image"]["top"] = imageTkTop
                    
                if(first):
                    if(error_event_side.is_set()):
                        image_size = (imageTkTop.width(), imageTkTop.height())
                        first = False
                        
                    if(error_event_top.is_set()):
                        image_size = (imageTkSide.width(), imageTkSide.height())
                        first = False
        except:
            print("erro esperado")
        
    def stop_recording(self):
        stop_recording(self.cache)
        self.close_screen()
        
    def run_loop(self):
        self.root.mainloop()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
            
    # SCREEN STATES
    def initial_screen_state(self):
        self.labels["fps"] = ttk.Label(self.root, text="FPS")
        self.labels["fps"].grid(row=1, column=2, padx=10, pady=10)
        
        self.entry["fps"] = ttk.Entry(self.root)
        self.entry["fps"].grid(row=2, column=2, padx=10, pady=10)
        self.entry["fps"].insert(0, "30")
        
        self.buttons["PrepareRecording"] = ttk.Button(self.root, text="Preparar para gravar", command=self.prepare_recording)
        self.buttons["PrepareRecording"].grid(row=3, column=2, padx=10, pady=10)
        
        self.buttons["CloseScreen"] = ttk.Button(self.root, text="Voltar", command=self.close_screen)
        self.buttons["CloseScreen"].grid(row=4, column=2, padx=10, pady=10)
    
    
    def init_recording_screen_state(self):
        self.recoding_screen_state()
        
        self.buttons["StopRecording"] = ttk.Button(self.root, text="Parar gravação", command=self.stop_recording)
        self.buttons["StopRecording"].grid(row=1, column=1, padx=10, pady=10)
        
    def recoding_screen_state(self):
        self.clear_screen()
        
        self.labels["side_text"] = ttk.Label(self.root, text="Lado")
        self.labels["side_text"].grid(row=2, column=1)
        
        self.labels["side_image"] = ttk.Label(self.root)
        self.labels["side_image"].grid(row=3, column=1)
        
        
        
        self.labels["top_text"] = ttk.Label(self.root, text="Superior")
        self.labels["top_text"].grid(row=2, column=2)
        
        self.labels["top_image"] = ttk.Label(self.root)
        self.labels["top_image"].grid(row=3, column=2)
        
        self.root.update_idletasks()
        self.root.grid_propagate(True)
        
    def prepare_recording_screen_state(self):
        self.recoding_screen_state()
        
        self.buttons["StopRecording"] = ttk.Button(self.root, text="Iniciar gravação", command=self.init_recording)
        self.buttons["StopRecording"].grid(row=1, column=1, padx=10, pady=10)
        
    def init_waiting_for_webcams_screen_state(self):
        self.clear_screen()
        
        self.labels["waiting_to_sync"] = ttk.Label(self.root, text="Esperando sincronização")
        self.labels["waiting_to_sync"].grid(row=1, column=2)
        
        self.root.update_idletasks()
        self.root.grid_propagate(True)
        
    def close_screen(self):
        self.clear_screen()
        
        show_frame(self.main_frame)