import cv2
import json

debug_mode = True

def analyze_frame(video_path):
    video = cv2.VideoCapture(video_path)
    
    if not video.isOpened():
        print(f"Error opening video file {video_path}")
        return


    video_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    frame_count = 0

    time_on_border_north = 0
    time_on_border_south = 0
    time_on_border_east = 0
    time_on_border_west = 0

    success, frame = video.read()
    data = {'route': []}

    treashold = 250

    darkest_pixel_value = 0
    darkest_pixel_location = (0, 0)

    while True:
         
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if not debug_mode or cv2.waitKey(10) == 27: #esc
            success, frame = video.read()

            if not success:
                break


            (darkest_pixel_value, maxVal, darkest_pixel_location, maxLoc) = cv2.minMaxLoc(gray_frame)

            insect_position_x = darkest_pixel_location[0]
            insect_position_y = darkest_pixel_location[1]

            data['route'].append({
                'x': insect_position_x,
                'y': insect_position_y
            })

            if(treashold >= insect_position_x):
                time_on_border_west += 1

            if(video_width - treashold <= insect_position_x):
                time_on_border_east += 1

            if(treashold >= insect_position_y):
                time_on_border_north += 1

            if(video_height - treashold <= insect_position_y):
                time_on_border_south += 1

            frame_count += 1

        if debug_mode:
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

    print(data)
    output_path = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"
    
    with open(output_path, "a") as file:
        json.dump(data, file)
        print("Arquivo salvo")

    video.release()
    cv2.destroyAllWindows()



def draw_number(number, frame_color, frame_grays_scale, point, place_holder):
    text = place_holder + "  " + str(number)
    
    cv2.putText(frame_color, text, point, 
        fontFace=cv2.FONT_HERSHEY_SIMPLEX, 
        fontScale=1, 
        color=(0, 0, 255), 
        thickness=5)
    
    cv2.putText(frame_grays_scale, text, point, 
        fontFace=cv2.FONT_HERSHEY_SIMPLEX, 
        fontScale=1, 
        color=(0, 0, 255), 
        thickness=5)