"""Preview de frame de webcam (Fase 4) — porta `recordWebcamController.get_image_from_frame_queue`
corrigindo o bug #4.

Bug #4 (ARCHITECTURE.md): o legado declarava `get_image_from_frame_queue(self, queue,
image_size)` — o `self` sobrando fazia todo chamador (que passava só 2 args) estourar
`TypeError`, mascarado por um `except:` nu EXTERNO em `show_recoding_video`, que matava
a thread de preview silenciosamente após o 1º frame. Aqui: função livre (sem `self`),
e `except Empty` (único caso esperado — fila vazia por timeout); qualquer outra exceção
(ex. frame corrompido em `Image.fromarray`) propaga em vez de ser engolida.
"""

from __future__ import annotations

from queue import Empty, Queue

from PIL import Image, ImageTk


def get_image_from_frame_queue(queue: Queue, image_size: tuple[int, int]) -> ImageTk.PhotoImage:
    try:
        frame = queue.get(timeout=1)
    except Empty:
        image = Image.new("RGB", image_size, "black")
    else:
        image = Image.fromarray(frame)
    return ImageTk.PhotoImage(image)
