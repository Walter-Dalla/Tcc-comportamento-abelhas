
import cv2

from imageAnalizer.videoHelper import OpenVideo
from imageAnalizer.movimentAnalizer import draw_number


def analyze_frame_top(video_top, isDebugMode):
    
    video_width = int(video_top.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(video_top.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    frame_count = 0

    time_on_border_north = 0
    time_on_border_south = 0
    time_on_border_east = 0
    time_on_border_west = 0

    success, frame = video_top.read()
    data = {'route': []}

    treashold = 250

    darkest_pixel_value = 0
    darkest_pixel_location = (0, 0)

    while True:
         
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if not isDebugMode or cv2.waitKey(10) == 27: #esc
            success, frame = video_top.read()

            #set_next_frame(False)

            if not success:
                break


            (darkest_pixel_value, maxVal, darkest_pixel_location, maxLoc) = cv2.minMaxLoc(gray_frame)

            insect_position_x = darkest_pixel_location[0]
            insect_position_z = darkest_pixel_location[1]

            data['route'].append({
                'x': insect_position_x,
                'z': insect_position_z
            })

            if(treashold >= insect_position_x):
                time_on_border_west += 1

            if(video_width - treashold <= insect_position_x):
                time_on_border_east += 1

            if(treashold >= insect_position_z):
                time_on_border_north += 1

            if(video_height - treashold <= insect_position_z):
                time_on_border_south += 1

            frame_count += 1

        if isDebugMode:
            #load_image_on_ui(frame)
            
            print(f"Darkest pixel value: {darkest_pixel_value} at location {darkest_pixel_location}")

            cv2.circle(gray_frame, darkest_pixel_location, 5, (0, 0, 255), 1)
            cv2.circle(frame, darkest_pixel_location, 5, (0, 0, 255), 1)

            draw_number(time_on_border_north, frame, gray_frame, (100, 100), "N")
            draw_number(time_on_border_south, frame, gray_frame, (100, 140), "S")
            draw_number(time_on_border_east, frame, gray_frame, (100, 180), "L")
            draw_number(time_on_border_west, frame, gray_frame, (100, 220), "O")

            cv2.imshow('Frame', frame)
            cv2.imshow('Gray Scale', gray_frame)

    data['time_on_border_north'] = time_on_border_north
    data['time_on_border_south'] = time_on_border_south
    data['time_on_border_east'] = time_on_border_east
    data['time_on_border_west'] = time_on_border_west

    video_top.release()
    cv2.destroyAllWindows()
    
    print("Fim da analise topo")
    return data