globalThis.LineWorldReferences = {
  "schema": 1,
  "study": {
    "channel": "Equifax",
    "window": [
      "2024-11-22",
      "2026-11-22"
    ],
    "source": "https://www.youtube.com/@equifax",
    "engine": "https://github.com/JuneYaooo/rea-video",
    "pin": "a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8"
  },
  "patterns": [
    {
      "id": "cut",
      "kind": "transition",
      "label": "Corte de cámara",
      "duration_s": 0.04,
      "mechanism": "Cambia de un plano al otro en un solo fotograma.",
      "sources": [
        {
          "video_id": "vb3k_OdYQs4",
          "video_title": "Accelerating Commercial Loan Decisions: Grasshopper Bank and Equifax",
          "start_s": 9.1667,
          "end_s": 9.25,
          "url": "https://www.youtube.com/watch?v=vb3k_OdYQs4&t=9s",
          "observation": "El encuadre cambia en el fotograma 221 a 24 fps. La identificación conserva su posición."
        }
      ]
    },
    {
      "id": "dissolve",
      "kind": "transition",
      "label": "Fundido entre planos",
      "duration_s": 0.5,
      "mechanism": "Superpone dos planos y aumenta la opacidad del entrante.",
      "sources": [
        {
          "video_id": "JJ97BC0hxXQ",
          "video_title": "VINE Explained",
          "start_s": 96.706,
          "end_s": 97.207,
          "url": "https://www.youtube.com/watch?v=JJ97BC0hxXQ&t=96s",
          "observation": "Se distinguen las dos imágenes a la vez en tres muestras intermedias."
        }
      ]
    },
    {
      "id": "tint-bridge",
      "kind": "transition",
      "label": "Fundido a través de un color",
      "duration_s": 0.65,
      "mechanism": "Usa un color intermedio para enlazar dos imágenes.",
      "sources": [
        {
          "video_id": "vb3k_OdYQs4",
          "video_title": "Accelerating Commercial Loan Decisions: Grasshopper Bank and Equifax",
          "start_s": 5.25,
          "end_s": 5.667,
          "url": "https://www.youtube.com/watch?v=vb3k_OdYQs4&t=5s",
          "observation": "La cartela burdeos se disuelve sobre la entrevista. El componente añade una entrada opcional al color para enlazar dos planos cualesquiera."
        }
      ]
    },
    {
      "id": "iris-fill",
      "kind": "transition",
      "label": "Apertura circular",
      "duration_s": 0.375,
      "mechanism": "Amplía una máscara central hasta descubrir el plano entrante.",
      "sources": [
        {
          "video_id": "vb3k_OdYQs4",
          "video_title": "Accelerating Commercial Loan Decisions: Grasshopper Bank and Equifax",
          "start_s": 3.5,
          "end_s": 3.875,
          "url": "https://www.youtube.com/watch?v=vb3k_OdYQs4&t=3s",
          "observation": "Tras un fotograma blanco, la elipse crece y deriva ligeramente a la izquierda. A los 3,875 s ocupa más del 99 % de la imagen."
        }
      ]
    },
    {
      "id": "iris-close",
      "kind": "transition",
      "label": "Cierre circular",
      "duration_s": 0.72,
      "mechanism": "Contrae el plano saliente dentro de una máscara hasta mostrar el fondo.",
      "sources": [
        {
          "video_id": "5tOPcX52B6s",
          "video_title": "Introducing Optimal Path™ From Equifax",
          "start_s": 87.533,
          "end_s": 88.466,
          "url": "https://www.youtube.com/watch?v=5tOPcX52B6s&t=87s",
          "observation": "El fondo burdeos aparece por las esquinas y reduce la escena anterior a un círculo central."
        }
      ]
    },
    {
      "id": "shutter-close",
      "kind": "transition",
      "label": "Cierre de dos franjas",
      "duration_s": 0.75,
      "mechanism": "Dos franjas de alturas independientes cierran la imagen por encima del centro.",
      "sources": [
        {
          "video_id": "vb3k_OdYQs4",
          "video_title": "Accelerating Commercial Loan Decisions: Grasshopper Bank and Equifax",
          "start_s": 74.625,
          "end_s": 75.375,
          "url": "https://www.youtube.com/watch?v=vb3k_OdYQs4&t=74s",
          "observation": "La franja inferior empieza cuatro fotogramas antes que la superior. Se reúnen en la fila 150 de 360."
        }
      ]
    },
    {
      "id": "step-blocks",
      "kind": "transition",
      "label": "Barrido escalonado",
      "duration_s": 0.67,
      "mechanism": "Tras un destello blanco, cinco franjas horizontales revelan la siguiente escena a destiempo.",
      "sources": [
        {
          "video_id": "wp8oli-fvTc",
          "video_title": "What Are Health Savings Accounts and How Do They Work?",
          "start_s": 15.066,
          "end_s": 15.732,
          "url": "https://www.youtube.com/watch?v=wp8oli-fvTc&t=15s",
          "observation": "A los 15,233 s se ven bordes en escalera. Después aparece el texto de la cartela."
        }
      ]
    },
    {
      "id": "band-pass",
      "kind": "transition",
      "label": "Banda de color descendente",
      "duration_s": 0.8,
      "mechanism": "Una franja de color cruza el cuadro y deja la siguiente composición a su paso.",
      "sources": [
        {
          "video_id": "wp8oli-fvTc",
          "video_title": "What Are Health Savings Accounts and How Do They Work?",
          "start_s": 42.997,
          "end_s": 43.797,
          "url": "https://www.youtube.com/watch?v=wp8oli-fvTc&t=42s",
          "observation": "La banda burdeos atraviesa la parte superior y luego la inferior. Tras ella aparecen trazos sobre blanco."
        }
      ]
    },
    {
      "id": "push-down",
      "kind": "transition",
      "label": "Empuje hacia abajo",
      "duration_s": 0.63,
      "mechanism": "Desplaza la escena anterior hacia abajo mientras entra la nueva por arriba.",
      "sources": [
        {
          "video_id": "pPladopITb4",
          "video_title": "Elevate Higher Education with Equifax Ignite for Graduate Outcomes",
          "start_s": 70.195,
          "end_s": 70.83,
          "url": "https://www.youtube.com/watch?v=pPladopITb4&t=70s",
          "observation": "La tarjeta con banda verde cede el cuadro a otra con banda naranja inferior."
        }
      ]
    },
    {
      "id": "push-left",
      "kind": "transition",
      "label": "Empuje hacia la izquierda",
      "duration_s": 0.56,
      "mechanism": "La página entrante avanza desde la derecha y desplaza la anterior.",
      "sources": [
        {
          "video_id": "p2y6xFqv35Y",
          "video_title": "How Can I Check Credit Scores?",
          "start_s": 29.667,
          "end_s": 30.23,
          "url": "https://www.youtube.com/watch?v=p2y6xFqv35Y&t=29s",
          "observation": "Se ve el borde de la página en tránsito antes de que la tarjeta numerada ocupe el cuadro."
        }
      ]
    },
    {
      "id": "speaker-id",
      "kind": "artifact",
      "label": "Identificación de entrevistado",
      "duration_s": 2.1,
      "mechanism": "Ancla una regla, el nombre y dos líneas de cargo a la pantalla.",
      "sources": [
        {
          "video_id": "vb3k_OdYQs4",
          "video_title": "Accelerating Commercial Loan Decisions: Grasshopper Bank and Equifax",
          "start_s": 5.5,
          "end_s": 13.75,
          "url": "https://www.youtube.com/watch?v=vb3k_OdYQs4&t=5s",
          "observation": "Regla a 5,50 s, nombre a 5,67 s y datos a 6,13 y 6,67 s. Persiste durante el corte de cámara a 9,21 s."
        }
      ]
    },
    {
      "id": "question-card",
      "kind": "artifact",
      "label": "Pregunta sobre la entrevista",
      "duration_s": 0.36,
      "mechanism": "Coloca la pregunta en un recuadro redondeado sobre el plano.",
      "sources": [
        {
          "video_id": "bvVlAHNS3NM",
          "video_title": "Day in the Life of a Sales Customer Success Manager",
          "start_s": 82.156,
          "end_s": 87.9,
          "url": "https://www.youtube.com/watch?v=bvVlAHNS3NM&t=82s",
          "observation": "La pregunta se hace visible en la esquina inferior izquierda después de pasar al encuadre medio."
        }
      ]
    },
    {
      "id": "caption-overlay",
      "kind": "artifact",
      "label": "Titular sobre imagen",
      "duration_s": 0.28,
      "mechanism": "Superpone un velo y un titular centrado a toda pantalla.",
      "sources": [
        {
          "video_id": "wp8oli-fvTc",
          "video_title": "What Are Health Savings Accounts and How Do They Work?",
          "start_s": 4.366,
          "end_s": 8.733,
          "url": "https://www.youtube.com/watch?v=wp8oli-fvTc&t=4s",
          "observation": "Texto blanco grueso en varias líneas sobre metraje oscurecido."
        }
      ]
    },
    {
      "id": "editorial-split",
      "kind": "artifact",
      "label": "Texto e imagen a dos columnas",
      "duration_s": 0.52,
      "mechanism": "Una imagen entra desde el borde derecho y comparte pantalla con un bloque de texto.",
      "sources": [
        {
          "video_id": "pPladopITb4",
          "video_title": "Elevate Higher Education with Equifax Ignite for Graduate Outcomes",
          "start_s": 3.3,
          "end_s": 3.8,
          "url": "https://www.youtube.com/watch?v=pPladopITb4&t=3s",
          "observation": "La imagen entrante crece hasta ocupar la mitad derecha. El titular queda sobre burdeos a la izquierda."
        }
      ]
    },
    {
      "id": "slide-pip",
      "kind": "artifact",
      "label": "Diapositiva con presentador",
      "duration_s": 3,
      "mechanism": "Sitúa al ponente en una ventana sobre una diapositiva a pantalla completa.",
      "sources": [
        {
          "video_id": "iGaqukBHo8s",
          "video_title": "October 2026 Credit Trends",
          "start_s": 48.56,
          "end_s": 48.56,
          "url": "https://www.youtube.com/watch?v=iGaqukBHo8s&t=48s",
          "observation": "Composición observada en una muestra. La diapositiva domina el cuadro y el ponente ocupa la esquina superior derecha."
        }
      ]
    },
    {
      "id": "insight-band",
      "kind": "artifact",
      "label": "Fotografía con banda informativa",
      "duration_s": 0.35,
      "mechanism": "Reserva una franja horizontal para antetítulo, titular y detalle.",
      "sources": [
        {
          "video_id": "pPladopITb4",
          "video_title": "Elevate Higher Education with Equifax Ignite for Graduate Outcomes",
          "start_s": 67.995,
          "end_s": 70.195,
          "url": "https://www.youtube.com/watch?v=pPladopITb4&t=67s",
          "observation": "La banda superior verde ocupa aproximadamente el 31 % de la altura. La siguiente cartela coloca la banda en la parte inferior."
        }
      ]
    },
    {
      "id": "dashboard-stack",
      "kind": "artifact",
      "label": "Gráficas que se reúnen",
      "duration_s": 6,
      "mechanism": "Presenta cada tarjeta en grande y luego la reduce a una celda del tablero.",
      "sources": [
        {
          "video_id": "pPladopITb4",
          "video_title": "Elevate Higher Education with Equifax Ignite for Graduate Outcomes",
          "start_s": 51.496,
          "end_s": 58.496,
          "url": "https://www.youtube.com/watch?v=pPladopITb4&t=51s",
          "observation": "La primera gráfica sube desde abajo y se repliega a la izquierda. Una segunda entra cerca de los 55,2 s."
        }
      ]
    },
    {
      "id": "icon-card",
      "kind": "artifact",
      "label": "Icono dibujado y texto",
      "duration_s": 0.84,
      "mechanism": "Dibuja un icono por longitud de trazo junto a una columna de texto.",
      "sources": [
        {
          "video_id": "wp8oli-fvTc",
          "video_title": "What Are Health Savings Accounts and How Do They Work?",
          "start_s": 43.797,
          "end_s": 44.85,
          "url": "https://www.youtube.com/watch?v=wp8oli-fvTc&t=43s",
          "observation": "Los trazos de una mano y una estrella se completan sobre fondo blanco con una banda inferior. El recorrido del icono es intercambiable."
        }
      ]
    },
    {
      "id": "disc-endcard",
      "kind": "artifact",
      "label": "Cierre con disco y enlace",
      "duration_s": 2.3,
      "mechanism": "Mantiene un sello en el centro y luego lo reduce y eleva para dejar sitio a la llamada a la acción.",
      "sources": [
        {
          "video_id": "bvVlAHNS3NM",
          "video_title": "Day in the Life of a Sales Customer Success Manager",
          "start_s": 118.563,
          "end_s": 124.109,
          "url": "https://www.youtube.com/watch?v=bvVlAHNS3NM&t=118s",
          "observation": "Aparece un disco blanco sobre burdeos. Tras una pausa se reduce, asciende y deja visible la dirección inferior."
        },
        {
          "video_id": "zCr72dcu7Do",
          "video_title": "How Equifax Empowers Talent in the Age of Applied AI",
          "start_s": 82.833,
          "end_s": 84.835,
          "url": "https://www.youtube.com/watch?v=zCr72dcu7Do&t=82s",
          "observation": "El disco pasa de un diámetro del 34 % del ancho al 22 %. Su centro sube del 50 % al 34 % de la altura."
        },
        {
          "video_id": "gd4xyHOOb2U",
          "video_title": "Sales Culture at Equifax",
          "start_s": 98.181,
          "end_s": 100.183,
          "url": "https://www.youtube.com/watch?v=gd4xyHOOb2U&t=98s",
          "observation": "El disco pasa de un diámetro del 34 % del ancho al 22 %. Su centro sube del 50 % al 34 % de la altura."
        }
      ]
    },
    {
      "id": "chart-focus",
      "kind": "artifact",
      "label": "Resalte de una zona de datos",
      "duration_s": 0.2,
      "mechanism": "Enmarca un intervalo de una tabla o gráfica con un contorno de acento.",
      "sources": [
        {
          "video_id": "iGaqukBHo8s",
          "video_title": "October 2026 Credit Trends",
          "start_s": 112,
          "end_s": 124,
          "url": "https://www.youtube.com/watch?v=iGaqukBHo8s&t=112s",
          "observation": "El marco rojo identifica una sección de la tabla comparativa. El tiempo de entrada del componente es configurable en el montaje."
        }
      ]
    },
    {
      "id": "corner-card",
      "kind": "artifact",
      "label": "Cartela con esquinas geométricas",
      "duration_s": 2,
      "mechanism": "Ordena un titular junto a una regla con bloques en los bordes.",
      "sources": [
        {
          "video_id": "wp8oli-fvTc",
          "video_title": "What Are Health Savings Accounts and How Do They Work?",
          "start_s": 15.566,
          "end_s": 17.6,
          "url": "https://www.youtube.com/watch?v=wp8oli-fvTc&t=15s",
          "observation": "Cartela roja con bloques oscuros en esquinas opuestas, pieza clara inferior y regla blanca al lado del texto."
        }
      ]
    },
    {
      "id": "orbital-caption",
      "kind": "artifact",
      "label": "Llamada circular con puntos",
      "duration_s": 2,
      "mechanism": "Hace pasar una estela de puntos por el plano y abre una llamada circular translúcida.",
      "sources": [
        {
          "video_id": "ULxWuSy7iMI",
          "video_title": "Transforming Data into Transparent Intelligence",
          "start_s": 21,
          "end_s": 24,
          "url": "https://www.youtube.com/watch?v=ULxWuSy7iMI&t=21s",
          "observation": "Los puntos claros se desplazan antes de aparecer el disco con texto por encima y a la derecha."
        }
      ]
    },
    {
      "id": "numbered-step",
      "kind": "artifact",
      "label": "Paso con número de contorno",
      "duration_s": 0.63,
      "mechanism": "Dibuja un arco abierto alrededor de un número delineado y muestra el texto a la derecha.",
      "sources": [
        {
          "video_id": "p2y6xFqv35Y",
          "video_title": "How Can I Check Credit Scores?",
          "start_s": 29.867,
          "end_s": 30.63,
          "url": "https://www.youtube.com/watch?v=p2y6xFqv35Y&t=29s",
          "observation": "La tarjeta blanca contiene una cifra hueca, un círculo incompleto y texto rojo a su derecha."
        }
      ]
    },
    {
      "id": "keypoint-list",
      "kind": "artifact",
      "label": "Lista por golpes de narración",
      "duration_s": 3,
      "mechanism": "Revela cada viñeta con tiempos independientes y permite destacar una entrada.",
      "sources": [
        {
          "video_id": "71DLJCPcM58",
          "video_title": "The Work Number Explained",
          "start_s": 37.6,
          "end_s": 46.535,
          "url": "https://www.youtube.com/watch?v=71DLJCPcM58&t=37s",
          "observation": "Las tres viñetas aparecen en momentos distintos, con una pausa más larga entre la primera y la segunda."
        }
      ]
    },
    {
      "id": "chart-ring",
      "kind": "artifact",
      "label": "Indicador anular con contador",
      "duration_s": 1.4,
      "mechanism": "Traza un anillo en sentido antihorario mientras el porcentaje llega a su valor final.",
      "sources": [
        {
          "video_id": "5tOPcX52B6s",
          "video_title": "Introducing Optimal Path™ From Equifax",
          "start_s": 88.466,
          "end_s": 89.699,
          "url": "https://www.youtube.com/watch?v=5tOPcX52B6s&t=88s",
          "observation": "El contador pasa por 10, 34, 55 y 72 hasta 79 %. El recorrido del círculo y el valor numérico son independientes."
        }
      ]
    },
    {
      "id": "guest-grid",
      "kind": "artifact",
      "label": "Mosaico de participantes",
      "duration_s": 3,
      "mechanism": "Cuatro participantes ocupan cuatro ventanas contiguas en dos filas. Las cartelas con sus nombres se alinean al pie de cada ventana.",
      "sources": [
        {
          "video_id": "dIUi2DnHh8I",
          "video_title": "Market Pulse: Regional Economies and the Outlook for Growth and Risk",
          "start_s": 3330,
          "end_s": 3330,
          "url": "https://www.youtube.com/watch?v=dIUi2DnHh8I&t=3330s",
          "observation": "Cuatro participantes ocupan cuatro ventanas contiguas en dos filas. Las cartelas con sus nombres se alinean al pie de cada ventana."
        },
        {
          "video_id": "VuvZKYl4jX0",
          "video_title": "Market Pulse: The Mortgage Market at a Crossroads: Affordability and Future Growth",
          "start_s": 380,
          "end_s": 380,
          "url": "https://www.youtube.com/watch?v=VuvZKYl4jX0&t=380s",
          "observation": "Dos ventanas de entrevista se ven en paralelo dentro de un campo blanco. Cada una lleva una identificación en la parte baja."
        }
      ],
      "geometry": {
        "marco_xywh": [
          0.06,
          0.08,
          0.88,
          0.84
        ],
        "distribucion": "Dos columnas. Con tres invitados, centrar la tercera ventana en la segunda fila."
      },
      "timing_note": "Mantener los retratos visibles desde el primer cuadro. Ofrecer una entrada de 0,25 s para los nombres.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "type-title",
      "kind": "artifact",
      "label": "Placa tipográfica",
      "duration_s": 3,
      "mechanism": "Un fragmento de lema de dos estilos tipográficos aparece en el centro sobre un campo casi blanco.",
      "sources": [
        {
          "video_id": "zCr72dcu7Do",
          "video_title": "How Equifax Empowers Talent in the Age of Applied AI",
          "start_s": 9,
          "end_s": 9,
          "url": "https://www.youtube.com/watch?v=zCr72dcu7Do&t=9s",
          "observation": "Un fragmento de lema de dos estilos tipográficos aparece en el centro sobre un campo casi blanco."
        },
        {
          "video_id": "NwPgUDYnOl4",
          "video_title": "The Two Sides of Trust: Inside Equifax Security",
          "start_s": 2,
          "end_s": 2,
          "url": "https://www.youtube.com/watch?v=NwPgUDYnOl4&t=2s",
          "observation": "El nombre de campaña y el subtítulo se concentran en el centro, con el texto principal en una línea y un segundo renglón menor."
        }
      ],
      "geometry": {
        "centro_x": 0.5,
        "titulo_y": 0.48,
        "subtitulo_y": 0.61,
        "ancho_maximo": 0.84
      },
      "timing_note": "Hacer aparecer el título en 0,38 s y retrasar el subtítulo 0,16 s.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "cta-card",
      "kind": "artifact",
      "label": "Placa de llamada a la acción",
      "duration_s": 3,
      "mechanism": "Una dirección web permanece centrada debajo del disco de la marca sobre un fondo uniforme granate.",
      "sources": [
        {
          "video_id": "zCr72dcu7Do",
          "video_title": "How Equifax Empowers Talent in the Age of Applied AI",
          "start_s": 87,
          "end_s": 87,
          "url": "https://www.youtube.com/watch?v=zCr72dcu7Do&t=87s",
          "observation": "Una dirección web permanece centrada debajo del disco de la marca sobre un fondo uniforme granate."
        },
        {
          "video_id": "j7soav2lPYc",
          "video_title": "Holiday Spending Outlook: Are Consumers Feeling the Pinch?",
          "start_s": 2180,
          "end_s": 2180,
          "url": "https://www.youtube.com/watch?v=j7soav2lPYc&t=2180s",
          "observation": "El cierre ordena verticalmente una portada, la invitación a suscribirse y una fila de símbolos de plataformas sobre blanco."
        }
      ],
      "geometry": {
        "centro_x": 0.5,
        "titulo_y": 0.33,
        "apoyo_y": 0.49,
        "accion_y": 0.68,
        "ancho_maximo": 0.84
      },
      "timing_note": "Reservar al menos 2 s de lectura después de la entrada de 0,35 s. El distintivo de acción puede contener una URL real.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "brand-slate",
      "kind": "artifact",
      "label": "Placa de marca",
      "duration_s": 3,
      "mechanism": "La primera imagen muestra un símbolo pequeño junto al nombre de la organización, centrados sobre fondo blanco.",
      "sources": [
        {
          "video_id": "vb3k_OdYQs4",
          "video_title": "Accelerating Commercial Loan Decisions: Grasshopper Bank and Equifax",
          "start_s": 0,
          "end_s": 0,
          "url": "https://www.youtube.com/watch?v=vb3k_OdYQs4&t=0s",
          "observation": "La primera imagen muestra un símbolo pequeño junto al nombre de la organización, centrados sobre fondo blanco."
        },
        {
          "video_id": "SiHYS0BQk0s",
          "video_title": "How Mastercard Open Finance & Equifax Are Delivering New Credit Signals",
          "start_s": 0,
          "end_s": 0,
          "url": "https://www.youtube.com/watch?v=SiHYS0BQk0s&t=0s",
          "observation": "El símbolo de dos discos, con el nombre debajo, ocupa el centro de una placa blanca."
        },
        {
          "video_id": "AJpOYlwae0c",
          "video_title": "June 2026 Credit Trends",
          "start_s": 415,
          "end_s": 415,
          "url": "https://www.youtube.com/watch?v=AJpOYlwae0c&t=415s",
          "observation": "Una firma clara se centra sobre granate y lleva una dirección web en un cuerpo menor abajo."
        }
      ],
      "geometry": {
        "centro_x": 0.5,
        "centro_y": 0.5,
        "limites_marca_xywh": [
          0.26,
          0.28,
          0.48,
          0.44
        ]
      },
      "timing_note": "Mantener la firma visible desde el primer cuadro. El editor decide la duración del plano.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "metric-callout",
      "kind": "artifact",
      "label": "Cifra destacada",
      "duration_s": 3,
      "mechanism": "Una cantidad en negro ocupa el lado derecho de un plano de presentador, aislada del cuerpo y del fondo desenfocado.",
      "sources": [
        {
          "video_id": "h5JFRBj4e6w",
          "video_title": "Tres consejos para quienes compran una vivienda por primera vez",
          "start_s": 80,
          "end_s": 80,
          "url": "https://www.youtube.com/watch?v=h5JFRBj4e6w&t=80s",
          "observation": "Una cantidad en negro ocupa el lado derecho de un plano de presentador, aislada del cuerpo y del fondo desenfocado."
        },
        {
          "video_id": "b3NjcYnZVLo",
          "video_title": "The Power of Direct Measured Data",
          "start_s": 2,
          "end_s": 2,
          "url": "https://www.youtube.com/watch?v=b3NjcYnZVLo&t=2s",
          "observation": "Cinco medidas aparecen en dos filas. Cada número es mayor y más oscuro que el texto aclaratorio cercano."
        }
      ],
      "geometry": {
        "centro_x": 0.5,
        "cifra_y": 0.44,
        "rotulo_y": 0.62,
        "detalle_y": 0.74,
        "centro_x_con_media": 0.73
      },
      "timing_note": "Mostrar un valor literal. Ofrecer 0,32 s de entrada y revelar la explicación 0,14 s después.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "concept-diagram",
      "kind": "artifact",
      "label": "Diagrama conceptual",
      "duration_s": 3,
      "mechanism": "Un núcleo central y varios sectores periféricos de color organizan un esquema circular en el lado izquierdo de una diapositiva.",
      "sources": [
        {
          "video_id": "onnbgz3JLhg",
          "video_title": "Smart Risk Decisioning Webinar: How to Bridge the Credit, Fraud, and Affordability Data Gap",
          "start_s": 3420,
          "end_s": 3420,
          "url": "https://www.youtube.com/watch?v=onnbgz3JLhg&t=3420s",
          "observation": "Un núcleo central y varios sectores periféricos de color organizan un esquema circular en el lado izquierdo de una diapositiva."
        },
        {
          "video_id": "HzNHRIDKgfw",
          "video_title": "Benefits of the Equifax Cloud",
          "start_s": 10,
          "end_s": 10,
          "url": "https://www.youtube.com/watch?v=HzNHRIDKgfw&t=10s",
          "observation": "Un dibujo lineal de un globo en el centro y pequeñas nubes alrededor forman un conjunto de entidades periféricas."
        }
      ],
      "geometry": {
        "centro_xy": [
          0.5,
          0.52
        ],
        "radio_x": 0.31,
        "radio_y": 0.31,
        "nodos": "Distribuir las etiquetas en una elipse alrededor del concepto principal."
      },
      "timing_note": "Revelar las conexiones desde el centro en 0,35 s, con un desfase de 0,08 s entre nodos.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "circle-window",
      "kind": "artifact",
      "label": "Fotografía en ventana circular",
      "duration_s": 3,
      "mechanism": "Una fotografía a color queda recortada por un círculo de borde limpio en un campo blanco. El centro del círculo coincide aproximadamente con el centro del cuadro.",
      "sources": [
        {
          "video_id": "kiDFzX3Z_0I",
          "video_title": "Alternative to Imperative: Deliver on Business Priorities with Data, Expertise, and AI",
          "start_s": 40,
          "end_s": 40,
          "url": "https://www.youtube.com/watch?v=kiDFzX3Z_0I&t=40s",
          "observation": "Una fotografía a color queda recortada por un círculo de borde limpio en un campo blanco. El centro del círculo coincide aproximadamente con el centro del cuadro."
        }
      ],
      "geometry": {
        "centro_xy": [
          0.5,
          0.5
        ],
        "radio_en_alturas": 0.32,
        "centro_x_con_titulo_derecha": 0.28,
        "centro_x_con_titulo_izquierda": 0.72
      },
      "timing_note": "Mantener el recorte estable o abrirlo en 0,45 s. El video de muestra confirma el recorte, no la curva de apertura.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    },
    {
      "id": "data-chart",
      "kind": "artifact",
      "label": "Gráfico de barras",
      "duration_s": 3,
      "mechanism": "Se ven dos gráficos de columnas con varios colores y alturas diferentes dentro de una diapositiva.",
      "sources": [
        {
          "video_id": "hkMgvWZtHHQ",
          "video_title": "September 2026 Credit Trends",
          "start_s": 375,
          "end_s": 375,
          "url": "https://www.youtube.com/watch?v=hkMgvWZtHHQ&t=375s",
          "observation": "Se ven dos gráficos de columnas con varios colores y alturas diferentes dentro de una diapositiva."
        },
        {
          "video_id": "pPladopITb4",
          "video_title": "Elevate Higher Education with Equifax Ignite for Graduate Outcomes",
          "start_s": 55,
          "end_s": 55,
          "url": "https://www.youtube.com/watch?v=pPladopITb4&t=55s",
          "observation": "Una matriz de vistas de producto incluye un gráfico con columnas verticales que ascienden hacia la derecha."
        }
      ],
      "geometry": {
        "grafico_xywh": [
          0.1,
          0.25,
          0.8,
          0.51
        ],
        "etiquetas_y": 0.84,
        "eje": "Anclar cada barra al cero y extenderla según el signo del valor."
      },
      "timing_note": "Interpolar las alturas desde cero durante 0,55 s y mantener visibles los valores definitivos.",
      "evidence": "Composición observada en imagen fija. La animación es una decisión de diseño."
    }
  ]
};
