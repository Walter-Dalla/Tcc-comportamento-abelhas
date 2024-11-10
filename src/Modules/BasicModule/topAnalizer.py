import cv2

def analyze_frame_top(top_frames):
    top_height, top_width = top_frames[0].shape
    
    frame_count = 0

    time_on_border_north = 0
    time_on_border_south = 0
    time_on_border_east = 0
    time_on_border_west = 0
    data = {'route': []}

    treashold = 250

    for frame in top_frames:
        
        
        frame = cv2.flip(frame, 0)
        gray_frame = frame
        
        (dark_est_pixel_value, maxVal, darkest_pixel_location, brigthest_pixel_location) = cv2.minMaxLoc(gray_frame)

        insect_position_x = brigthest_pixel_location[0]
        insect_position_y = brigthest_pixel_location[1]

        data['route'].append({
            'x': insect_position_x,
            'y': insect_position_y
        })

        if(treashold >= insect_position_x):
            time_on_border_west += 1

        if(top_width - treashold <= insect_position_x):
            time_on_border_east += 1

        if(treashold >= insect_position_y):
            time_on_border_north += 1

        if(top_height - treashold <= insect_position_y):
            time_on_border_south += 1

        frame_count += 1

    data['time_on_border_north'] = time_on_border_north
    data['time_on_border_south'] = time_on_border_south
    data['time_on_border_east'] = time_on_border_east
    data['time_on_border_west'] = time_on_border_west

    print("Fim da analise topo")
    return data