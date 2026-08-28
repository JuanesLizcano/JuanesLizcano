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

def construir(ruta_img, salida, recorte=(0.10, 0.04, 0.92, 0.86), contraste=1.5, piso=PISO,
              corte=(1, 12), gamma=1.0):
    im = Image.open(ruta_img)
    if im.mode in ("RGBA", "LA"):
        # Viene con el fondo ya recortado (rembg). Se compone sobre NEGRO: asi
        # todo lo que no es el sujeto cae por debajo del piso y sale como
        # espacio. Es el paso que mas mejora el resultado — sin el, el fondo
        # (plantas, luces, reflejos) compite con el rostro por los caracteres
        # densos y el retrato no se lee.
        alfa = im.split()[-1]
        fondo = Image.new("RGB", im.size, (0, 0, 0))
        fondo.paste(im.convert("RGB"), mask=alfa)
        im = fondo
    im = im.convert("L")

    # 0) Quitar el relleno blanco. Al guardar una imagen desde un chat suele
    #    quedar pegada en una esquina con el resto en blanco; si no se recorta,
    #    las fracciones de abajo apuntan a la nada. Se busca el rectangulo de
    #    lo que NO es casi-blanco y se trabaja solo sobre eso.
    umbral = im.point(lambda p: 255 if p < 245 else 0)
    caja = umbral.getbbox()
    if caja and (caja[2] - caja[0]) > 40 and (caja[3] - caja[1]) > 40:
        im = im.crop(caja)

    # 1) Recortar al sujeto. A 76 columnas cada pixel de aire sobrante se come
    #    resolucion util, asi que el encuadre importa mas que cualquier ajuste
    #    posterior. `recorte` va en fracciones (izq, arriba, der, abajo) y se
    #    aplican YA sobre la foto limpia, no sobre el relleno.
    w, h = im.size
    x0, y0, x1, y1 = recorte
    im = im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))

    # 2) Suavizar ANTES de reducir. Cada caracter resume ~6x6 pixeles; sin este
    #    paso un pixel suelto del fondo decide el caracter de toda la celda y
    #    el resultado sale con pelusa.
    im = im.filter(ImageFilter.GaussianBlur(0.8))

    # 3) Contraste. La imagen viene oscura (media ~62), asi que sin estirar el
    #    histograma casi todo cae en los dos caracteres mas vacios.
    # El recorte del extremo CLARO es el parametro delicado con una foto: si se
    # recorta mucho, el rostro (que es lo mas brillante) se satura entero y
    # queda un bloque solido sin facciones.
    im = ImageOps.autocontrast(im, cutoff=corte)
    if gamma != 1.0:
        # Gamma > 1 comprime los altos: reparte el rostro entre varios
        # caracteres en vez de mandarlo todo al mas denso.
        tabla = [min(255, int(255 * ((i / 255.0) ** gamma) + 0.5)) for i in range(256)]
        im = im.point(tabla)
    im = ImageEnhance.Contrast(im).enhance(contraste)

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
            if g < piso:
                fila.append(" ")
                continue
            v = (g - piso) / (255.0 - piso)   # 0 = fondo, 1 = lo mas claro
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
    import os, sys
    # Fuente por defecto: `recorte.png`, la foto CON EL FONDO YA QUITADO.
    #
    # El recorte de fondo es el paso que mas cambia el resultado y el que mas
    # tardo en aparecer aqui. Con la foto cruda, las plantas y las luces del
    # restaurante competian con el rostro por los caracteres densos y el
    # retrato no se leia por mucho que se ajustara el contraste. Con el fondo
    # en negro puro todo lo que no es el sujeto cae bajo el piso y sale como
    # espacio. Se genero asi (una sola vez, no hace falta repetirlo):
    #
    #     from rembg import remove
    #     remove(Image.open("foto.jpg")).save("recorte.png")
    #
    # De paso quito los vasos de la mesa: rembg los considera fondo.
    #
    # NOTA: la foto original NO esta en el repo a proposito. Aqui solo vive el
    # retrato ya convertido, que es lo unico que se publica.
    fuente = sys.argv[1] if len(sys.argv) > 1 else "recorte.png"
    if not os.path.exists(fuente):
        sys.exit(f"No encuentro {fuente} — ver la nota de arriba.")
    construir(fuente, "retrato.svg",
              recorte=(0.28, 0.02, 0.82, 0.58),
              corte=(1, 2), gamma=1.0, contraste=1.2, piso=22)
