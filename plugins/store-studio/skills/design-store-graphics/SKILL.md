---
name: design-store-graphics
description: Create or improve product artwork for IA Referencias using reference-led composition, typography, image integration, and restrained texture. Use for new graphic concepts, editorial merch, posters, collage, or revisions with weak hierarchy or visual coherence. Applies practical lessons from Dan George Hill while preserving the store's style and product requirements; pair with the product-family skill for production.
---

# Diseño gráfico para la tienda

Las rutas que empiezan por `stores/` o `docs/` se resuelven desde la raíz del proyecto de la tienda. Para otra tienda, usa su identidad y catálogo vigentes.

Convierte una idea en una composición que funcione sobre el producto. Usa las
referencias para tomar decisiones sobre jerarquía, encuadre, contraste y textura.
Produce los diseños solicitados, inspecciónalos y corrige los fallos visibles;
un prompt o una lista de consejos solo bastan si eso es lo que pidió el usuario.

Esta skill adapta un estudio de ocho videos de **Dan George Hill / DGH Graphic
Design**. [Fuentes, minutos y límites de la revisión](references/dgh-video-notes.md).
Sus técnicas son referencias de trabajo; las reglas de la tienda y del producto
se consultan en sus documentos vigentes.

## 1. Fijar el mensaje y el soporte

- Lee la solicitud, el `AGENTS.md` aplicable y, para IA Referencias, la
  identidad (`stores/ia-referencias/IDENTITY.md`),
  dirección gráfica (`stores/ia-referencias/GRAPHIC_STYLE.md`),
  familias de diseño (`stores/ia-referencias/DESIGN_STYLES.md`) y
  catálogo (`stores/ia-referencias/products/index.md`).
- En una revisión, abre el arte exacto y las decisiones más recientes del
  producto. Conserva el original como control. Una exclusión del usuario
  prevalece sobre una etiqueta histórica de aceptación. Consulta la
  selección corregida (`stores/ia-referencias/spikes/2026-09-26-fox-rockett-approved-products/README.md`)
  cuando trabajes sobre las propuestas Fox Rockett.
- Escribe un brief corto: público, frase exacta, contradicción, primer elemento
  que debe verse, soporte, superficie/color y etapa solicitada. Separa el texto
  obligatorio del detalle opcional. Usa la
  [plantilla de brief y revisión](references/brief-and-review.md) si facilita
  conservar estas decisiones en el spike.
- Elige una familia existente: `vector-icon-text`, `segmented-photo-collage` o
  `targeted-accent-intervention`. Para un eslogan corto, empieza por la primera.
  Si el destino es Dibujos Infantiles, lee su identidad y preserva el dibujo y
  el trazo del autor; adapta solo los principios que ayuden a ese encargo.

## 2. Escoger referencias por su función

Consulta la [receta de la familia elegida](references/design-recipes.md). Selecciona
solo referencias que resuelvan una decisión concreta: escala tipográfica,
distribución de masas, recorte, unión entre imágenes o tratamiento de tinta.
Anota qué extraes y qué cambias para el producto. Las referencias orientan;
el motivo, las palabras y la composición deben responder a nuestro concepto.

Consulta la guía Fox Rockett (`docs/operations/fox-rockett-assets.md`) y su
revisión por producto (`stores/ia-referencias/spikes/2026-09-26-fox-rockett-product-review/README.md`)
antes de elegir recursos comprados. Usa un asset si aclara la metáfora; registra
su ID, adaptación y licencia. Conserva los motivos ya elegidos por el usuario.
Los tutoriales no acreditan derechos comerciales sobre las fotos, fuentes,
personajes o packs que muestran. Usa material propio o con permiso documentado.

## 3. Resolver la composición antes del acabado

1. Construye una versión limpia y editable. Fija el orden de lectura entre
   frase, imagen y apoyo. Prueba primero el balance de claros y oscuros.
2. Deriva una retícula sencilla del contenido y del soporte. Alinea por bordes
   y ejes útiles; ajusta ópticamente después. El espacio vacío debe permitir
   respirar a la frase y reconocer la silueta.
3. Haz que la tipografía organice el mensaje: contraste de tamaño o peso,
   cortes de línea con sentido y separación entre niveles. La proporción 1.618
   que aparece en DGH puede iniciar una prueba; el texto y la vista del producto
   deciden el tamaño final.
4. Si usas imágenes, comprueba recorte, orientación, luz, valores tonales y
   solapamiento. Cambia su escala o máscara para integrarlas. Al reflejar una
   imagen, revisa letras, logotipos y detalles cuya orientación tenga significado.
5. En un spike serio de IA Referencias, compara al menos tres hipótesis dentro
   de la familia escogida. Para frases en poleras: composición apilada directa,
   emblema compacto y UI/icono contenido. Explica qué decisión prueba cada una.
   Si el usuario delimita una corrección o pide una sola salida, respeta ese alcance.

Para un lema breve, el cuerpo de texto denso de algunos pósters del canal se
traduce en **jerarquía y alineación**. Mantén una frase principal y, como máximo,
una secundaria conforme al estilo de la tienda.

## 4. Aplicar color y textura con una función

- Asigna al acento una tarea: señalar el remate, distinguir un estado o unir
  elementos. Examina también la composición en escala de grises.
- Si la textura ayuda al concepto, conserva el control limpio. Trabaja primero
  los elementos o sus máscaras y después la integración general. Ajusta la
  intensidad a su escala: un titular grande tolera un tratamiento que podría
  borrar una línea secundaria. Revisa bordes, contraformas y costuras de patrones.
- Para collage, prueba un ajuste tonal común y corrige cada recorte antes de
  añadir ruido global. Retira el efecto si pierde contraste o hace desaparecer
  la metáfora sobre la superficie real.
- Mantén separadas las capas de arte, textura de impresión y presentación.
  Un fondo de papel o una sombra de mockup no deben terminar accidentalmente en
  el PNG transparente. Conserva texto editable y una exportación reproducible.

## 5. Ejecutar con la herramienta adecuada

| Trabajo | Recurso |
| --- | --- |
| Tipografía, símbolos, retícula y exportación precisa | SVG/código o editor vectorial disponible; usa la guía de herramientas (`docs/operations/product-design-toolchain.md`). |
| Recortes, luz, máscaras, desgaste o textura | Editor raster o scripts adecuados al tratamiento; conservar capas y parámetros. |
| Ilustración o fotografía nueva mediante un modelo | Skill de generación disponible. Especifica composición, superficie y función visual; compón el texto final de forma determinista. |
| Polera/camiseta, sus PNG y previews | [create-shirt-product](../create-shirt-product/SKILL.md), incluida su referencia de composición. |
| Especificación, variante, proveedor, precio, upload o mockup real | [create-printify-product](../create-printify-product/SKILL.md). |
| Campaña o modelos llevando un producto | [marketing](../marketing/SKILL.md), con referencias actuales del producto. |
| Crítica detallada o comparación difícil | [product-design-critic](../product-design-critic/SKILL.md). |

Photoshop y los packs de DGH son opcionales. Traduce la operación a herramientas
disponibles y assets autorizados. Una solicitud de arte se resuelve hasta esa
etapa; las operaciones externas dependen del alcance ya autorizado. Sigue la
política vigente de la tienda para la etiqueta visible `AI Generated Image`.

## 6. Revisar el resultado y cerrar la iteración

- Abre las imágenes reales. Compara arte completo y producto completo a 300 y
  600 px, con igual encuadre por tipo de evidencia; inspecciona detalles aparte.
  Usa el [generador de evidencia existente](../product-design-critic/references/review-contract.md)
  para preparar láminas repetibles cuando sea útil. OCR y medidas ayudan a
  detectar riesgos; la lectura visual decide.
- Comprueba frase exacta, remate, contraste, espacio, recortes, bordes y textura
  después de reducir. En producto, inspecciona las zonas que puedan tapar o
  deformar el mensaje: asa, lomo, costura o curvatura según corresponda.
- Elige por claridad del concepto y ejecución visible. Un diseño limpio puede
  ganar. Corrige el fallo de mayor impacto y repite la comparación de la zona
  afectada. Detente cuando cumpla el brief y los controles de la etapa; si falta
  evidencia, entrega el resultado verificable y especifica la limitación.
- Para aceptar un producto Printify, usa sus mockups reales y los controles de
  su skill. El título «print ready» de un tutorial, una simulación o un archivo
  aplanado no acreditan la calidad física ni sustituyen la especificación.
- Guarda fuentes, ruta elegida, archivo/versiones, parámetros, evidencia y
  motivos de descarte en `RESOURCES.md`. Mantén las iteraciones en las carpetas
  ignoradas y entrega los artes y láminas finales en los destinos del spike.
  Actualiza su índice cuando corresponda. En la respuesta, muestra el resultado,
  explica el cambio útil y distingue revisión propia de pruebas con compradores.
