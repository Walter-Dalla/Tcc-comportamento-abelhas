import cv2
import numpy as np


def contoursAnalizer(mask_red):
        
    kernel = np.ones((5, 5), np.uint8)
    mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel)
    mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_CLOSE, kernel)

    
    contours, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    image_contours = mask_red.copy()
    
    return contours, image_contours


def contoursAnalizerHsv(image):

    def click_event(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:  # Verifica se o botão esquerdo do mouse foi pressionado
            # Acessa os valores HSV no ponto clicado
            hsv_value = hsv[y, x]
            print(f"HSV Values at ({x}, {y}): {hsv_value}")

            # Acessa os valores RGB no ponto clicado
            rgb_value = image[y, x]
            print(f"RGB Values at ({x}, {y}): {rgb_value[::-1]}")  # Converte de BGR para RGB


    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Define os limites da cor vermelha no espaço HSV
    # Nota: O vermelho pode ter duas partes devido à sua posição no espectro de cores HSV
    red_lower1 = np.array([0, 120, 70])
    red_upper1 = np.array([10, 255, 255])

    red_lower2 = np.array([150, 30, 70])
    red_upper2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
    mask2 = cv2.inRange(hsv, red_lower2, red_upper2)

    # Cria as máscaras para a cor vermelha e combina-as
    mask_red = cv2.bitwise_or(mask1, mask2)
    
    result = cv2.bitwise_and(image, image, mask=mask_red)

    cv2.imshow('mask1', mask1)
    cv2.imshow('mask2', mask2)

    contours, image_contours = contoursAnalizer(mask_red)
    cv2.drawContours(image, contours, -1, (0, 255, 0), 1)

    # Mostra a imagem resultante com contornos
    cv2.imshow('Contornos Vermelhos', image)
    cv2.setMouseCallback('Contornos Vermelhos', click_event)
    return contours, image_contours


   