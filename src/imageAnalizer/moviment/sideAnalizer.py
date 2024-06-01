
import cv2

def analyze_frame_side(video_top):
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

    darkest_pixel_location = (0, 0)

    while True:
         
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        success, frame = video_top.read()

        if not success:
            break


        (darkest_pixel_value, maxVal, darkest_pixel_location, maxLoc) = cv2.minMaxLoc(gray_frame)

        insect_position_y = darkest_pixel_location[1]

        data['route'].append({
            'z': insect_position_y,
            'z2': darkest_pixel_location[0]
        })

        if(treashold >= insect_position_y):
            time_on_border_north += 1

        if(video_height - treashold <= insect_position_y):
            time_on_border_south += 1

        frame_count += 1

    data['time_on_border_north'] = time_on_border_north
    data['time_on_border_south'] = time_on_border_south
    data['time_on_border_east'] = time_on_border_east
    data['time_on_border_west'] = time_on_border_west

    video_top.release()
    cv2.destroyAllWindows()

    print("Fim da analise lado")
    return data