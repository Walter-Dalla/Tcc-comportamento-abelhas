import cv2

def analyze_frame_side(side_video):
    side_height, side_width = side_video[0].shape
    
    frame_count = 0

    time_on_border_north = 0
    time_on_border_south = 0
    time_on_border_east = 0
    time_on_border_west = 0

    data = {'route': []}

    treashold = 250

    darkest_pixel_location = (0, 0)

    for frame in side_video:
        frame = cv2.flip(frame, 0)
        gray_frame = frame

        #frame = cv2.rotate(frame, cv2.ROTATE_180)

        (darkest_pixel_value, maxVal, darkest_pixel_location, maxLoc) = cv2.minMaxLoc(gray_frame)

        insect_position_y = darkest_pixel_location[0]
        insect_position_z = darkest_pixel_location[1]
        
        data['route'].append({
            'y': insect_position_y,
            'z': insect_position_z
        })

        if(treashold >= insect_position_z):
            time_on_border_north += 1

        if(side_height - treashold <= insect_position_z):
            time_on_border_south += 1

        frame_count += 1

    data['time_on_border_north'] = time_on_border_north
    data['time_on_border_south'] = time_on_border_south
    data['time_on_border_east'] = time_on_border_east
    data['time_on_border_west'] = time_on_border_west

    print("Fim da analise lado")
    return data