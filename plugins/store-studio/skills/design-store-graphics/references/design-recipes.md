# Recetas para IA Referencias

Resuelve las rutas `shared/`, `stores/` y `docs/` desde la raíz del proyecto de la tienda.

Leer solo la ruta que corresponda al brief. Estas recetas son adaptaciones
propias para la tienda. Los IDs remiten a las
[notas de los videos](dgh-video-notes.md); no son fórmulas de calidad garantizada.

## A. Frase dominante — `vector-icon-text`

**Útil cuando:** la frase lleva el chiste y un símbolo puede aclararlo.
Referencias: DGH-01 y DGH-02 para jerarquía; DGH-08 para un acento con función.

1. Identifica la palabra o relación que cambia el sentido. Escribe el texto
   exacto antes de dibujar y decide dónde debe caer el remate.
2. Construye una composición apilada sin marco: ajusta saltos, anchura óptica,
   interlineado y contraste de pesos. Usa márgenes derivados del soporte.
3. Prueba un emblema compacto que agrupe la frase. Si el contorno la obliga a
   encogerse, abre el emblema o elimina el contorno.
4. Prueba un símbolo o fragmento de interfaz que complete la contradicción.
   Conserva solo el control o estado relevante. El símbolo puede integrarse con
   una letra si no dificulta reconocerla.
5. Compara las tres rutas sobre la misma superficie. Añade color al elemento
   semántico elegido y comprueba que la lectura siga funcionando sin ese color.

**Ejemplo de exploración, sin aprobación de producto:** `HUMAN OVERRIDE` con
`DENIED` como respuesta. A puede destacar la respuesta debajo del titular;
B puede usar un sello; C puede mostrar un único control de anulación bloqueado.
La comparación decide si el símbolo añade significado o repite el texto.

**Revisar:** espaciado de pares de letras, contraformas abiertas, puntuación,
saltos que no cambien el sentido, texto exacto y balance del icono. La miniatura
debe permitir leer el remate; si solo queda legible la primera palabra, corregir
la jerarquía antes de añadir efectos.

## B. Colisión de imágenes — `segmented-photo-collage`

**Útil cuando:** dos objetos o escenas hacen visible una contradicción.
Referencias: DGH-04 y DGH-05 para integración y encuadre; DGH-03 para textura.

1. Expresa la relación visual: por ejemplo, una promesa digital junto a una
   consecuencia material. Elige una imagen protagonista y los apoyos mínimos.
2. Revisa alternativas de recorte y orientación antes de comprometerte con una
   fotografía. Comprueba resolución útil a la escala final y procedencia.
3. Crea máscaras editables. Inspecciona pelo, huecos, objetos finos y bordes sobre
   fondo claro y oscuro. Conserva el archivo original para reparar la máscara.
4. Prueba variaciones de escala, solapamiento y espacio libre con los mismos
   recursos. Haz que cada variante contraste una decisión, por ejemplo objeto
   dominante frente a imagen dominante, en lugar de cambiar solo el tinte.
5. Iguala valores tonales y dirección de luz cuando busques continuidad. Si la
   contradicción exige un corte visible, conserva ese borde deliberadamente.
6. Compón la frase fuera del área más ruidosa. Aplica una paleta común si une
   las imágenes; conserva un acento para el remate. Compara con el control limpio.

**Revisar:** la forma de los objetos debe reconocerse reducida y la relación
entre ellos debe entenderse sin el caption. Si parecen recortes independientes,
cambia escala, dirección o solapamiento. Añadir grano no resuelve una relación
visual débil. En prendas, comprueba que los bordes y el fondo no formen un
rectángulo involuntario.

## C. Una intervención — `targeted-accent-intervention`

**Útil cuando:** un detalle puede revelar todo el chiste.
Referencias: DGH-05 para relación entre frase e imagen; DGH-08 para acento.

1. Nombra la zona que contiene la contradicción: casilla, firma, ojo, etiqueta,
   resultado o cifra. Simplifica el resto de la imagen para que la sostenga.
2. Compara tres maneras de intervenir la misma zona: un recorte que la agrande,
   una marca o franja que la señale y una extracción que la convierta en símbolo.
   Mantén la misma frase para juzgar el efecto de la intervención.
3. Conserva el contexto imprescindible para reconocer qué se intervino. Ajusta
   contraste y espacio alrededor; coloca el apoyo donde se lea después del foco.
4. Oculta temporalmente el acento. Al recuperarlo debe cambiar la interpretación
   o localizar el remate. Si solo adorna, revisa la intervención.

**Revisar:** un resaltado no debe borrar la evidencia que hace comprensible la
sátira. Evita sustituir una mascota o símbolo seleccionado por otro recurso
solo porque permita un efecto parecido al del tutorial.

## Acabado editorial o vintage, si el brief lo justifica

Esta sección complementa la familia elegida. Pósters, portadas y piezas
editoriales pueden admitir más densidad que una polera de lectura inmediata.

### Retícula y detalle secundario

Usa la cantidad real de contenido para decidir filas, columnas y excepciones.
Comprueba dónde cae el foco respecto de bordes, zonas tapadas y lomo. Un gesto
manual propio puede romper la regularidad en la palabra que lleva el sentido;
digitalízalo y conserva su forma, en lugar de deformar todo el texto.

Introduce detalle secundario solo si aporta contenido. Las cifras y citas que
se presenten como reales necesitan fuente; para sátira, escribe contenido
original que se reconozca como tal. Evita copiar letras de canciones o créditos
de un póster de referencia para rellenar espacio.

### Textura reproducible

Una estructura útil de capas, adaptable a la herramienta:

```text
arte-editable/
  texto-exacto
  simbolo-o-recortes
acabado-de-impresion/
  mascaras-por-elemento
  ajustes-tonales
presentacion/
  fondo-y-mockup
```

1. Define qué representa el tratamiento: tinta gastada, papel, marca manual o
   fotocopia. Conserva una salida con el acabado apagado.
2. Trabaja el borde o la máscara del elemento afectado. Usa menos intensidad
   sobre letras pequeñas; restaura trazos que alteren palabras o siluetas.
3. Integra texturas generales solo si ayudan a que el conjunto se perciba unido.
   Examina zonas claras y oscuras: una puede perder contraste antes que la otra.
4. Guarda escala, semilla si hay aleatoriedad, máscaras, fuente y parámetros.
   Comprueba que el patrón no produzca uniones visibles o halos después de reducir.
5. Exporta el arte y su presentación por separado. En un print transparente,
   comprueba el alfa sobre el color real del producto.

Los generadores de texturas del repositorio (`shared/scripts/generate_product_textures.py`)
y la máscara de sustracción (`shared/scripts/apply_subtraction_mask.py`)
pueden servir si sus entradas y salidas encajan. Revisa su ayuda y contrato antes
de ejecutarlos; no regeneres una biblioteca completa para una sola composición.

### Paleta limitada

Conserva colores semánticos editables para probar combinaciones con el mismo
arte. Si el resultado necesita masas tonales planas, separa rangos con máscaras
y ajusta sus límites visualmente. Mantén detalles esenciales y evita huecos
inesperados. DGH-06 inspira esta edición por capas; la preparación industrial,
incluidos solapamientos y registro, depende del proceso y proveedor.

## Brief para un generador de imágenes

Cuando un modelo sea la herramienta adecuada, traduce el brief a decisiones
observables. No basta pedir «más profesional» o nombrar al diseñador.

```text
Destino y proporción: [producto y área de trabajo].
Idea y contradicción: [relación que el espectador debe reconocer].
Familia: [una familia de la tienda].
Composición: [foco, tamaño relativo, dirección, aire y lugar reservado al texto].
Imagen: [objetos/figuras necesarios y su relación].
Paleta: [base, acento y función del acento sobre la superficie elegida].
Acabado: [limpio o tratamiento localizado, con intensidad relativa].
Texto: reservar su espacio; se compondrá exactamente en la fase determinista.
Referencias: [función concreta de cada imagen autorizada].
Variación: [la única decisión principal que debe cambiar respecto al control].
```

Después de generar, abre el resultado y compón el texto final con herramientas
deterministas. Aplica las reglas de etiquetado de la tienda al archivo que se
entregará. La salida de un modelo no acredita escala ni fidelidad de un producto
existente: para campaña, sigue los requisitos de referencias reales.
