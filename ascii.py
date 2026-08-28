# Convierte el avatar en un retrato ASCII animado (SVG).
#
# Por que asi y no con una libreria: el SVG lo tiene que servir GitHub por su
# proxy, sin JavaScript y sin fuentes externas. Un <text> monoespaciado con
# animacion SMIL interna es lo unico que sobrevive a eso.
#
# La animacion es por FILA, de izquierda a derecha, con retardo escalonado: se
# lee como si la imagen se estuviera imprimiendo en una terminal. Todas las
# filas terminan con fill="freeze" para que quede quieta al final en vez de
# repetirse en bucle.

import io
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

# Rampa de densidad: del caracter mas "vacio" al mas "lleno".
RAMPA = " .`:-=+*csS#%@"

COLS       = 76      # columnas. Se probo con 104 a 6px: mas detalle, pero los
                     # caracteres dejan de leerse y queda un tramado borroso.
                     # El punto del retrato ASCII es que se VEAN las letras.
FUENTE     = 8.0     # font-size en px
ANCHO_CHAR = 4.8     # ancho real de un caracter mono a 8px
ALTO_LINEA = 8.4
PISO       = 70      # gris por debajo del cual todo es fondo (espacio)

def construir(ruta_img, salida):
    im = Image.open(ruta_img).convert("L")

    # 1) Recortar al sujeto. El avatar trae mucho aire alrededor y, a 76
    #    columnas, ese aire se come la mitad de la resolucion util.
    w, h = im.size
    im = im.crop((int(w * 0.10), int(h * 0.04), int(w * 0.92), int(h * 0.86)))

    # 2) Suavizar ANTES de reducir. Cada caracter resume ~6x6 pixeles; sin este
    #    paso un pixel suelto del fondo decide el caracter de toda la celda y
    #    el resultado sale con pelusa.
    im = im.filter(ImageFilter.GaussianBlur(0.8))

    # 3) Contraste. La imagen viene oscura (media ~62), asi que sin estirar el
    #    histograma casi todo cae en los dos caracteres mas vacios.
    im = ImageOps.autocontrast(im, cutoff=(1, 12))
    im = ImageEnhance.Contrast(im).enhance(1.5)

    # Los caracteres son mas altos que anchos (~0.57), asi que hay que
    # comprimir en vertical o el retrato sale estirado al doble de largo.
    prop = ANCHO_CHAR / ALTO_LINEA
    filas = max(1, int(COLS * (im.height / im.width) * prop))
    im = im.resize((COLS, filas), Image.LANCZOS)

    px = im.load()
    lineas = []
    for y in range(filas):
        fila = []
        for x in range(COLS):
            g = px[x, y]
            # Piso negro: por debajo de esto es fondo y va como espacio. Sin
            # este corte el fondo oscuro no queda vacio sino lleno de puntos,
            # y el retrato se lee como una mancha en vez de una silueta.
            if g < PISO:
                fila.append(" ")
                continue
            v = (g - PISO) / (255.0 - PISO)   # 0 = fondo, 1 = lo mas claro
            # Texto CLARO sobre fondo OSCURO: lo brillante de la foto tiene que
            # ser el caracter mas denso, no al reves. Con la rampa invertida el
            # retrato sale en negativo.
            i = int(v * (len(RAMPA) - 1) + 0.5)
            fila.append(RAMPA[i])
        lineas.append("".join(fila))

    ancho = int(COLS * ANCHO_CHAR) + 32
    alto  = int(filas * ALTO_LINEA) + 46

    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    clips, textos = [], []
    for y, linea in enumerate(lineas):
        # Retardo escalonado + una pizca segun la fila, para que la diagonal
        # se sienta y no entren todas a la vez.
        ini = 0.30 + y * 0.022
        clips.append(
            f'    <clipPath id="r{y}"><rect x="16" y="{34 + y*ALTO_LINEA:.1f}" width="0" height="{ALTO_LINEA:.1f}">'
            f'<animate attributeName="width" from="0" to="{COLS*ANCHO_CHAR:.0f}" '
            f'begin="{ini:.2f}s" dur="0.5s" calcMode="spline" '
            f'keySplines="0.22 1 0.36 1" fill="freeze"/></rect></clipPath>'
        )
        textos.append(
            f'  <text x="16" y="{42 + y*ALTO_LINEA:.1f}" clip-path="url(#r{y})">{esc(linea)}</text>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}" role="img" aria-label="Retrato en ASCII">
  <title>whoami</title>
  <defs>
{chr(10).join(clips)}
  </defs>
  <style>
    text {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
      font-size: {FUENTE}px;
      fill: #C9C9D1;
      white-space: pre;
      letter-spacing: 0;
    }}
  </style>
  <rect width="{ancho}" height="{alto}" rx="14" fill="#08080A"/>
  <rect x="0.5" y="0.5" width="{ancho-1}" height="{alto-1}" rx="14" fill="none" stroke="#1E1E23"/>
{chr(10).join(textos)}
</svg>
'''
    io.open(salida, "w", encoding="utf-8", newline="\n").write(svg)
    print(f"{salida}: {COLS}x{filas} caracteres, {ancho}x{alto}px")

if __name__ == "__main__":
    construir("avatar.png", "retrato.svg")
