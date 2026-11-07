"""Original child-oriented sources and sentence-aligned accessible restatements.

Fiction is explicitly labelled. Reference URLs identify factual sources, not an
assertion that these independently authored Spanish passages are quotations.
"""

# title, category, reference, ((source sentence, accessible sentences), ...)
TOPICS = {
    "bosque encantado": (
        "El Bosque Encantado y el puente de raíces",
        "cuentos_aventuras",
        "",
        (
            (
                "En este cuento original de ficción, la exploradora Inés descubre un puente de raíces dentro de un bosque encantado.",
                "Este cuento es inventado. Inés explora un bosque encantado. Allí descubre un puente de raíces.",
            ),
            (
                "Un pequeño zorro llamado Bruno permanece junto al arroyo porque la corriente le impide cruzar hacia su madriguera.",
                "El zorro Bruno está junto al arroyo. No puede cruzar porque el agua corre con fuerza. Su madriguera está al otro lado.",
            ),
            (
                "Inés solicita ayuda a la guardiana del bosque y entre ambas colocan una tabla sobre el puente para facilitar el paso del zorro.",
                "Inés pide ayuda a la guardiana del bosque. Las dos ponen una tabla sobre el puente. Así Bruno puede pasar.",
            ),
            (
                "Después de alcanzar la otra orilla, Bruno agradece la colaboración y los tres regresan por el sendero señalado con piedras blancas.",
                "Bruno llega a la otra orilla y da las gracias. Los tres vuelven por el sendero de piedras blancas.",
            ),
            (
                "La aventura muestra que pedir ayuda y trabajar en equipo permite resolver dificultades sin ponerse en peligro.",
                "La aventura enseña a pedir ayuda. El trabajo en equipo sirve para resolver problemas sin riesgos.",
            ),
        ),
    ),
    "bosque encantado semillas": (
        "El Bosque Encantado y las semillas del viento",
        "cuentos_aventuras",
        "",
        (
            (
                "En este cuento original de ficción, Leo y la lechuza Alba encuentran una bolsa de semillas junto a un roble del bosque encantado.",
                "Este cuento es inventado. Leo pasea con Alba, una lechuza. Junto a un roble encuentran una bolsa de semillas.",
            ),
            (
                "La guardiana explica que las semillas deben plantarse en el claro porque allí reciben la luz que necesitan para crecer.",
                "La guardiana les pide plantar las semillas en el claro. Allí llega luz para que las plantas crezcan.",
            ),
            (
                "Leo prepara pequeños agujeros mientras Alba señala los espacios libres para no dañar las raíces de los árboles.",
                "Leo hace pequeños hoyos. Alba señala los espacios libres. Así cuidan las raíces de los árboles.",
            ),
            (
                "Al terminar, ambos riegan la tierra con agua del arroyo y colocan piedras para recordar dónde sembraron.",
                "Los dos riegan la tierra con agua del arroyo. Ponen piedras para marcar dónde sembraron.",
            ),
            (
                "Los amigos comprenden que cuidar un bosque requiere paciencia y acciones pequeñas realizadas entre todos.",
                "Los amigos aprenden a cuidar el bosque. Hacen falta paciencia y pequeñas tareas en equipo.",
            ),
        ),
    ),
    "dragones": (
        "La dragona Lía y el horno del pueblo",
        "cuentos_aventuras",
        "",
        (
            (
                "En este cuento original de ficción, la dragona Lía vive cerca de un pueblo cuyo horno deja de funcionar durante el invierno.",
                "Este cuento es inventado. La dragona Lía vive cerca de un pueblo. En invierno se estropea el horno del pueblo.",
            ),
            (
                "La panadera Mara pide ayuda a Lía para calentar los ladrillos y poder preparar pan para las familias.",
                "Mara es la panadera del pueblo. Pide a Lía que caliente los ladrillos del horno. Así Mara puede hacer pan para las familias.",
            ),
            (
                "Lía controla cuidadosamente su fuego mientras Mara mantiene una distancia segura y comprueba la temperatura del horno.",
                "Lía echa fuego con cuidado. Mara se mantiene lejos para estar segura. También revisa el calor del horno.",
            ),
            (
                "Cuando el pan está listo, los vecinos comparten la comida y reparan el horno para que vuelva a funcionar.",
                "El pan ya está listo. Los vecinos comparten la comida. Después reparan el horno.",
            ),
            (
                "Lía comprende que su fuerza resulta útil cuando escucha las necesidades de los demás y actúa con responsabilidad.",
                "Lía escucha lo que otros necesitan. Usa su fuerza con cuidado para ayudar.",
            ),
        ),
    ),
    "tesoros piratas": (
        "El mapa de la capitana Sol",
        "cuentos_aventuras",
        "",
        (
            (
                "En este cuento original de ficción, la capitana Sol descubre un mapa dentro de una botella que llega a la playa.",
                "Este cuento es inventado. La capitana Sol encuentra una botella en la playa. Dentro hay un mapa.",
            ),
            (
                "El mapa señala una cueva situada al norte de la isla y la tripulación utiliza una brújula para orientarse.",
                "El mapa señala una cueva al norte de la isla. La tripulación usa una brújula para encontrar el camino.",
            ),
            (
                "Durante el recorrido, Sol ayuda a reparar la barca de un pescador antes de continuar la búsqueda del cofre.",
                "Sol ve a un pescador con su barca rota. Le ayuda a repararla antes de seguir hacia el cofre.",
            ),
            (
                "En la cueva encuentran un cofre que contiene semillas y una carta que invita a cultivar un huerto para compartir alimentos.",
                "En la cueva encuentran un cofre con semillas. También hay una carta. La carta les pide plantar un huerto y compartir comida.",
            ),
            (
                "La tripulación decide plantar las semillas y descubre que el verdadero tesoro del relato consiste en colaborar con la comunidad.",
                "La tripulación planta las semillas para ayudar al pueblo. Ese es el tesoro de esta aventura.",
            ),
        ),
    ),
    "viaje al espacio": (
        "Nora y el viaje a la Luna",
        "cuentos_aventuras",
        "https://science.nasa.gov/moon/facts/",
        (
            (
                "En este cuento original de ficción, Nora y el robot Teo realizan un viaje imaginario a la Luna para estudiar sus cráteres.",
                "Este cuento es inventado. Nora y el robot Teo viajan a la Luna. Quieren estudiar sus cráteres.",
            ),
            (
                "Antes de salir, ambos revisan sus trajes porque necesitan llevar aire para respirar durante la exploración lunar.",
                "Los dos revisan sus trajes antes de salir. Necesitan llevar aire para respirar en la Luna.",
            ),
            (
                "Nora observa que la Luna refleja la luz del Sol y Teo anota este dato real en su cuaderno de viaje.",
                "Nora ve que la Luna refleja luz del Sol. Teo anota este dato real en su cuaderno.",
            ),
            (
                "Al regresar a la nave, los exploradores guardan sus muestras de roca y siguen las marcas del camino para no perderse.",
                "Los dos guardan sus muestras de roca. Siguen las marcas del camino para volver a la nave.",
            ),
            (
                "La misión termina con un regreso seguro y una enseñanza sobre la importancia de prepararse antes de explorar.",
                "Los dos vuelven a salvo. Aprenden a prepararse antes de explorar.",
            ),
        ),
    ),
    "nasa": (
        "La NASA y la exploración del espacio",
        "ciencia_espacio",
        "https://www.nasa.gov/history/65-years-ago-nasa-begins-operations/",
        (
            (
                "La NASA es la agencia espacial de Estados Unidos y comenzó oficialmente sus operaciones el 1 de octubre de 1958.",
                "La NASA es la agencia espacial de Estados Unidos. Empezó a trabajar el 1 de octubre de 1958.",
            ),
            (
                "Sus científicos e ingenieros diseñan naves y realizan investigaciones para conocer la Tierra, el sistema solar y el universo.",
                "Sus equipos crean naves para estudiar el espacio. También estudian la Tierra y el sistema solar.",
            ),
            (
                "La misión Apolo 11 llevó a los primeros seres humanos a la superficie de la Luna en 1969.",
                "La misión Apolo 11 llegó a la Luna en 1969. Llevó a las primeras personas que pisaron la Luna.",
            ),
            (
                "Las sondas y los robots pueden explorar lugares lejanos sin transportar una tripulación humana, enviando información mediante señales de radio.",
                "Las sondas y los robots exploran sitios lejanos. Pueden viajar sin personas a bordo. Envían datos por señales de radio.",
            ),
            (
                "Los satélites que observan nuestro planeta proporcionan datos sobre las nubes, los océanos y los cambios del hielo terrestre.",
                "Otros satélites miran nuestro planeta desde el espacio. Dan datos sobre las nubes, los mares y el hielo.",
            ),
        ),
    ),
    "marte": (
        "Marte, el planeta rojo",
        "ciencia_espacio",
        "https://science.nasa.gov/mars/facts/",
        (
            (
                "Marte es el cuarto planeta desde el Sol y su superficie adquiere una tonalidad rojiza por los minerales de hierro oxidados.",
                "Marte es el cuarto planeta desde el Sol. Su suelo parece rojo por el hierro oxidado.",
            ),
            (
                "Sus dos pequeños satélites naturales reciben los nombres de Fobos y Deimos y presentan formas irregulares.",
                "Marte tiene dos lunas pequeñas: Fobos y Deimos. Sus formas no son redondas.",
            ),
            (
                "El monte Olimpo es un enorme volcán marciano considerado el mayor volcán del sistema solar.",
                "El monte Olimpo es un volcán de Marte. Es el mayor volcán del sistema solar.",
            ),
            (
                "La atmósfera marciana es muy tenue y está compuesta principalmente por dióxido de carbono, por lo que no permite respirar sin equipos especiales.",
                "Marte tiene muy poco aire. Su aire es sobre todo dióxido de carbono. Una persona necesita equipo especial para respirar allí.",
            ),
            (
                "Los vehículos robóticos estudian las rocas y buscan huellas de agua antigua para conocer la historia del planeta.",
                "Los robots estudian las rocas de Marte. Buscan rastros de agua de otros tiempos. Así conocen la historia del planeta.",
            ),
        ),
    ),
    "selva amazonica": (
        "La selva amazónica y sus ríos",
        "animales_naturaleza",
        "https://www.worldwildlife.org/places/amazon/",
        (
            (
                "La selva amazónica es un extenso bosque tropical de América del Sur que se distribuye por varios países y la Guayana Francesa.",
                "La selva amazónica está en América del Sur. Ocupa varios países y la Guayana Francesa.",
            ),
            (
                "El río Amazonas y sus afluentes transportan enormes cantidades de agua y conectan hábitats donde viven peces y delfines de río.",
                "El río Amazonas lleva mucha agua. Sus afluentes son ríos que se unen a él. Allí viven peces y delfines de río.",
            ),
            (
                "Los jaguares, las guacamayas y numerosos insectos encuentran alimento y refugio entre los árboles de este ecosistema.",
                "Los jaguares y las guacamayas viven en esta selva. También hay muchos insectos. Los árboles les dan comida y refugio.",
            ),
            (
                "Las plantas liberan vapor de agua por sus hojas, contribuyendo a la humedad del aire y a la formación de lluvias.",
                "Las hojas de las plantas sueltan vapor de agua. Ese vapor ayuda a formar la lluvia.",
            ),
            (
                "Los pueblos indígenas poseen conocimientos sobre la selva y participan en su cuidado, mientras la deforestación destruye hábitats.",
                "Los pueblos indígenas conocen y cuidan la selva. La tala de árboles destruye lugares donde viven los animales.",
            ),
        ),
    ),
    "estrellas": (
        "Las estrellas y la luz del Sol",
        "ciencia_espacio",
        "https://science.nasa.gov/universe/stars/",
        (
            (
                "Una estrella es una enorme esfera de gas caliente que produce energía mediante reacciones nucleares en su interior.",
                "Una estrella es una gran bola de gas caliente. Dentro se producen reacciones que dan energía.",
            ),
            (
                "El Sol es la estrella más cercana a la Tierra y su luz proporciona la energía que necesitan muchas formas de vida.",
                "El Sol es la estrella más cercana a la Tierra. Su luz da energía a muchos seres vivos.",
            ),
            (
                "Las estrellas presentan colores diferentes según su temperatura, siendo las azules más calientes que las rojas.",
                "Las estrellas tienen distintos colores según su calor. Las azules están más calientes que las rojas.",
            ),
            (
                "Su enorme distancia hace que muchas parezcan pequeños puntos luminosos cuando observamos el cielo nocturno.",
                "Muchas estrellas parecen puntos de luz por estar muy lejos. Podemos verlas en el cielo de noche.",
            ),
        ),
    ),
    "vikingos": (
        "Los vikingos y sus barcos",
        "historia_misterios",
        "https://www.rmg.co.uk/stories/maritime-history/viking-ships",
        (
            (
                "Los vikingos procedían de Escandinavia, una región del norte de Europa, y realizaron viajes marítimos durante la Edad Media.",
                "Los vikingos venían de Escandinavia, al norte de Europa. Viajaron por mar durante la Edad Media.",
            ),
            (
                "Sus barcos de madera podían avanzar mediante velas o remos y permitían recorrer costas y remontar ríos.",
                "Sus barcos eran de madera y usaban velas o remos. Podían navegar por costas y ríos.",
            ),
            (
                "Además de participar en incursiones, numerosos viajeros vikingos comerciaban con otras comunidades e intercambiaban productos.",
                "Algunos vikingos atacaban otros lugares. Muchos también vendían y cambiaban productos con otros pueblos.",
            ),
            (
                "Algunas proas llevaban tallas de animales, como dragones o serpientes, que hoy conocemos gracias a restos y representaciones.",
                "Algunos barcos tenían figuras de animales en la proa. Podían ser dragones o serpientes tallados en madera.",
            ),
        ),
    ),
    "castillos": (
        "Los castillos medievales",
        "historia_misterios",
        "https://www.english-heritage.org.uk/castles/life-in-a-castle/",
        (
            (
                "Los castillos medievales eran construcciones fortificadas que servían como residencia y lugar de defensa de sus habitantes.",
                "Los castillos eran casas fuertes de la Edad Media. La gente vivía en ellos y podía defenderse.",
            ),
            (
                "Sus murallas y torres permitían vigilar el entorno y dificultaban la entrada de posibles atacantes.",
                "Las murallas y las torres protegían el castillo. Desde las torres se podía ver a lo lejos.",
            ),
            (
                "Algunos castillos poseían fosos y puentes levadizos que ayudaban a controlar el acceso a la puerta principal.",
                "Algunos castillos tenían un foso junto a sus muros. Un puente que subía permitía controlar la entrada.",
            ),
            (
                "Dentro del recinto trabajaban cocineros, artesanos y otras personas encargadas de tareas esenciales para la vida cotidiana.",
                "Dentro trabajaban cocineros y artesanos. Cada persona hacía tareas para la vida del castillo.",
            ),
        ),
    ),
    "piratas caribe": (
        "Los piratas del Caribe en la historia",
        "historia_misterios",
        "https://www.rmg.co.uk/stories/maritime-history/pirates-history-golden-age-piracy",
        (
            (
                "Los piratas atacaban embarcaciones para apropiarse de sus cargamentos y actuaron en rutas comerciales del mar Caribe.",
                "Los piratas atacaban barcos para robar su carga. Algunos actuaban en las rutas del mar Caribe.",
            ),
            (
                "Los barcos mercantes transportaban mercancías valiosas como telas, alimentos y metales entre puertos separados por el océano.",
                "Los barcos de comercio llevaban telas, comida y metales. Iban de un puerto a otro por el mar.",
            ),
            (
                "La navegación requería conocer los vientos y las costas, así como coordinar el trabajo de la tripulación.",
                "Para navegar había que conocer los vientos y las costas. La tripulación debía trabajar en equipo.",
            ),
            (
                "Las historias de cofres enterrados forman parte de muchas aventuras de ficción, pero no describen una costumbre general de los piratas reales.",
                "Muchos cuentos hablan de cofres enterrados. Los piratas reales no solían guardar así sus tesoros.",
            ),
        ),
    ),
    "natacion": (
        "La natación y sus cuatro estilos",
        "deportes",
        "https://www.worldaquatics.com/swimming",
        (
            (
                "La natación es una actividad física que permite desplazarse en el agua coordinando los movimientos del cuerpo y la respiración.",
                "La natación sirve para moverse en el agua. Hay que coordinar el cuerpo y la respiración.",
            ),
            (
                "En la natación competitiva se utilizan cuatro estilos principales: libre, espalda, braza y mariposa.",
                "En las pruebas hay cuatro estilos principales. Son libre, espalda, braza y mariposa.",
            ),
            (
                "En las pruebas de espalda, los nadadores avanzan boca arriba, mientras en la braza realizan movimientos simétricos de brazos y piernas.",
                "En espalda se nada boca arriba. En braza, los dos brazos se mueven a la vez. Las piernas también se mueven a la vez.",
            ),
            (
                "Aprender a nadar requiere práctica supervisada y respetar las normas de seguridad, sin entrar al agua sin acompañamiento adecuado.",
                "Para aprender hace falta practicar con alguien que sepa enseñar. Hay que seguir las reglas de seguridad del agua.",
            ),
        ),
    ),
    "videojuegos": (
        "Cómo funciona un videojuego",
        "tecnologia",
        "https://scratch.mit.edu/ideas",
        (
            (
                "Un videojuego es un programa informático que responde a las acciones del jugador mediante imágenes, sonidos y reglas.",
                "Un videojuego es un programa que sigue reglas. Responde con imágenes y sonidos a quien juega.",
            ),
            (
                "Los programadores escriben instrucciones para controlar los personajes, detectar movimientos y comprobar si se alcanza un objetivo.",
                "Quienes crean el programa escriben sus pasos. Esos pasos controlan personajes y comprueban las metas.",
            ),
            (
                "Los diseñadores organizan escenarios y desafíos, mientras los artistas preparan imágenes y los músicos crean sonidos.",
                "Unas personas crean los escenarios y los retos. Otras dibujan las imágenes o hacen la música.",
            ),
            (
                "Probar el juego permite encontrar errores y ajustar sus reglas antes de compartirlo con otros jugadores.",
                "Probar el juego ayuda a encontrar fallos. Sus creadores pueden corregirlos antes de compartir el juego.",
            ),
        ),
    ),
    "inventos": (
        "Inventos que amplían nuestros sentidos",
        "tecnologia",
        "https://science.nasa.gov/mission/hubble/observatory/design/",
        (
            (
                "El telescopio permite observar objetos lejanos al recoger y concentrar la luz mediante lentes o espejos.",
                "El telescopio recoge luz con lentes o espejos. Así podemos ver mejor lo que está lejos.",
            ),
            (
                "El microscopio permite examinar detalles demasiado pequeños para distinguirlos a simple vista, como algunas células.",
                "El microscopio deja ver detalles muy pequeños. Algunos no se ven solo con los ojos.",
            ),
            (
                "Los inventores mejoran sus instrumentos mediante pruebas y comparaciones para comprobar qué diseños funcionan mejor.",
                "Quienes inventan prueban varias formas de hacer sus aparatos. Comparan los resultados para elegir lo que funciona mejor.",
            ),
            (
                "Estos inventos no sustituyen las preguntas de los científicos, sino que proporcionan nuevas maneras de buscar evidencias.",
                "Estos aparatos ayudan a buscar pruebas. Las personas siguen haciendo preguntas para entender el mundo.",
            ),
        ),
    ),
}

TOPICS.update(
    {
        "dragones huerto": (
            "El dragón Milo y el huerto seco",
            "cuentos_aventuras",
            "",
            (
                (
                    "En este cuento original de ficción, el dragón Milo descubre que el huerto de su amiga Vera necesita agua después de varios días sin lluvia.",
                    "Este cuento es inventado. El dragón Milo visita a su amiga Vera. Su huerto necesita agua porque lleva días sin llover.",
                ),
                (
                    "Vera propone recoger agua del pozo mediante cubos, mientras Milo transporta cada carga sin pisar las plantas recién sembradas.",
                    "Vera saca agua del pozo con cubos. Milo lleva los cubos al huerto. Tiene cuidado para no pisar las plantas nuevas.",
                ),
                (
                    "Al terminar, los amigos colocan paja sobre la tierra húmeda para reducir la pérdida de agua y proteger las raíces.",
                    "Los dos ponen paja sobre la tierra húmeda. Así se pierde menos agua. También protegen las raíces de las plantas.",
                ),
                (
                    "Milo comprende que observar las necesidades de las plantas y colaborar resulta más útil que intentar resolverlo todo con fuego.",
                    "Milo aprende a mirar lo que las plantas necesitan. Colaborar es mejor que usar fuego para todo.",
                ),
            ),
        ),
        "tesoros piratas campana": (
            "El tesoro de la campana del puerto",
            "cuentos_aventuras",
            "",
            (
                (
                    "En este cuento original de ficción, la capitana Ada encuentra una campana de bronce dentro de un cofre abandonado en una isla.",
                    "Este cuento es inventado. La capitana Ada encuentra un cofre en una isla. Dentro hay una campana de bronce.",
                ),
                (
                    "Una carta explica que la campana pertenecía al puerto del pueblo y servía para avisar de la llegada de barcos.",
                    "Una carta cuenta que la campana era del puerto. Su sonido avisaba de que llegaban barcos.",
                ),
                (
                    "Ada decide devolverla en lugar de venderla y su tripulación utiliza cuerdas para levantarla sin que nadie resulte herido.",
                    "Ada decide devolver la campana al pueblo. Su tripulación la levanta con cuerdas. Todos trabajan con cuidado para evitar daños.",
                ),
                (
                    "Cuando la campana vuelve a sonar en el puerto, Ada comprende que un tesoro puede tener valor por la ayuda que presta a una comunidad.",
                    "La campana vuelve a sonar en el puerto. Ada aprende que un tesoro puede servir a todo un pueblo.",
                ),
            ),
        ),
        "viaje al espacio semillas": (
            "Iris y las semillas de la nave",
            "cuentos_aventuras",
            "",
            (
                (
                    "En este cuento original de ficción, Iris y el robot Kiro cuidan un pequeño huerto dentro de una nave que realiza un viaje espacial imaginario.",
                    "Este cuento es inventado. Iris viaja con el robot Kiro en una nave. Dentro cuidan un pequeño huerto.",
                ),
                (
                    "Cuando una luz del huerto deja de funcionar, ambos revisan el panel para descubrir por qué las plantas reciben menos iluminación.",
                    "Una luz del huerto se apaga. Los dos revisan el panel para buscar el fallo. Las plantas reciben menos luz.",
                ),
                (
                    "Kiro señala un cable suelto e Iris pide permiso a la capitana antes de reparar la conexión siguiendo las instrucciones de seguridad.",
                    "Kiro encuentra un cable suelto. Iris pide permiso a la capitana para repararlo. Sigue los pasos de seguridad de la nave.",
                ),
                (
                    "La luz vuelve a encenderse y el equipo aprende que comprobar las causas de un problema es mejor que cambiar piezas sin entenderlo.",
                    "La luz vuelve a encenderse. El equipo aprende a buscar la causa de un fallo. Es mejor que cambiar piezas sin saber por qué.",
                ),
            ),
        ),
    }
)

VARIANTS = {
    "bosque encantado": ("bosque encantado", "bosque encantado semillas"),
    "dragones": ("dragones", "dragones huerto"),
    "tesoros piratas": ("tesoros piratas", "tesoros piratas campana"),
    "viaje al espacio": ("viaje al espacio", "viaje al espacio semillas"),
}
