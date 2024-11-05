def GeneratePdf(data, output_location, title):
    from xhtml2pdf import pisa
    html_content = f"""
            <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dados do processamento: {title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                table {{
                    width: 50%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th, td {{
                    padding: 10px;
                    border: 1px solid #ccc;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>

            <h1>Dados do processamento: {title}</h1>

            <table>
                <tr>
                    <th>Propriedade</th>
                    <th>Valor</th>
                </tr>
                <tr>
                    <td>Quantidade de frames</td>
                    <td>{data['frame_count']}</td>
                </tr>
                <tr>
                    <td>Largura da Caixa (cm)</td>
                    <td>{data['width_box_cm']}</td>
                </tr>
                <tr>
                    <td>Altura da Caixa (cm)</td>
                    <td>{data['height_box_cm']}</td>
                </tr>
                <tr>
                    <td>Profundidade da Caixa (cm)</td>
                    <td>{data['depth_box_cm']}</td>
                </tr>
                <tr>
                    <td>Razão Pixel para cm</td>
                    <td>{data['pixel_to_cm_ratio']}</td>
                </tr>
                <tr>
                    <td>FPS</td>
                    <td>{data['fps']}</td>
                </tr>
                <tr>
                    <td>Tempo Borda X</td>
                    <td>{data['time_border_x']}</td>
                </tr>
                <tr>
                    <td>Tempo Borda Y</td>
                    <td>{data['time_border_y']}</td>
                </tr>
                <tr>
                    <td>Tempo Borda Z</td>
                    <td>{data['time_border_z']}</td>
                </tr>
            </table>

        </body>
        </html>
    """
    
    with open(output_location, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)
        
    return not pisa_status.err