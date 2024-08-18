import numpy as np
from PIL import Image
import cv2

def select_higher_pixel_intensities(frame1, frame2):
    """
    Função para selecionar as intensidades de pixel mais altas entre dois frames.
    """
    return np.maximum(frame1, frame2)

def process_image_sequence(image_sequence, n_blocks=21, block_size=500):
    """
    Função principal para processar uma sequência de imagens.
    
    Parameters:
    - image_sequence: lista de frames (imagens) da sequência
    - n_blocks: número de blocos de processamento
    - block_size: número de frames por bloco
    
    Returns:
    - frame final processado
    """
    # Inicialização do frame final processado
    final_frame = np.zeros_like(image_sequence[0])

    for block in range(n_blocks):
        # Extrair blocos de 500 frames
        block_frames = image_sequence[block*block_size:(block+1)*block_size]

        # Processar os frames do bloco
        for i in range(len(block_frames) - 1):
            frame1 = block_frames[i]
            frame2 = block_frames[i+1]

            # Seleciona as maiores intensidades de pixels
            processed_frame = select_higher_pixel_intensities(frame1, frame2)

            # Atualiza o frame final com as maiores intensidades
            final_frame = select_higher_pixel_intensities(final_frame, processed_frame)
    
    return final_frame

def open_video(video_path):
    video = cv2.VideoCapture(video_path)
    
    if not video.isOpened():
        print(f"Error opening video file {video_path}")
        return False, None
    
    return True, video

def getVideo(input_video_path):
    success, originalVideo = open_video(input_video_path)
    if not success:
        return
    
    frames = []
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,3))
        morphology_img = cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel,iterations=2)
        
        frames.append(morphology_img)
    
    originalVideo.release()  # Fechar o vídeo após leitura

    if not frames:
        print("No frames extracted from video.")
        return

    # Processar a sequência de frames
    final_image = process_image_sequence(frames)
    
    # Salvar a imagem final no disco
    final_image_pil = Image.fromarray(final_image)
    final_image_pil.save('result.png')
    print("Final image saved as 'result.png'.")

getVideo("C:/Projetos/Tcc-comportamento-abelhas/resource/cima/teste02.mp4")
