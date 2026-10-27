"""Original Spanish reference articles with public sources and no study filler."""

from dataclasses import dataclass, replace

from app.services.local_plans import SOURCE_REVISIONS


@dataclass(frozen=True)
class Article:
    title: str
    text: str
    category: str
    url: str
    fact_hint: str = ""
    provider: str = "local"
    revision_id: int | None = None


ARTICLES = {
    "tierra": Article(
        "La Tierra y su órbita",
        "La Tierra gira alrededor del Sol y completa una órbita en aproximadamente un año. Su rotación sobre el propio eje produce la sucesión del día y la noche. La atmósfera contiene gases que rodean el planeta y los océanos cubren gran parte de su superficie. La luz solar proporciona energía que las plantas utilizan para producir alimento mediante la fotosíntesis.",
        "ciencia_espacio",
        "https://science.nasa.gov/earth/facts/",
        "rotación",
    ),
    "luna": Article(
        "La Luna y sus fases",
        "La Luna es el satélite natural de la Tierra y refleja la luz del Sol. Las fases lunares dependen de la parte iluminada que observamos desde nuestro planeta. Una vuelta completa de las fases tarda cerca de 29,5 días. La Luna posee numerosos cráteres producidos por impactos. Su gravedad contribuye a las mareas de los océanos terrestres.",
        "ciencia_espacio",
        "https://science.nasa.gov/moon/facts/",
        "29,5",
    ),
    "telescopio": Article(
        "El telescopio",
        "Un telescopio recoge luz para observar objetos lejanos con mayor detalle. Los telescopios refractores utilizan lentes, mientras que los reflectores emplean espejos. La astronomía utiliza estos instrumentos para estudiar estrellas, planetas y galaxias. Algunos telescopios observan desde la superficie terrestre y otros funcionan en el espacio, donde la atmósfera no altera las imágenes del mismo modo. Un telescopio no crea la luz que recoge.",
        "ciencia_espacio",
        "https://science.nasa.gov/mission/hubble/observatory/design/",
        "espejos",
    ),
    "abejas": Article(
        "Las abejas y la polinización",
        "Las abejas visitan flores para obtener néctar y polen. Al desplazarse entre flores pueden transportar polen y favorecer la reproducción de numerosas plantas. Las abejas de la miel viven en colonias y producen miel a partir del néctar. Algunas obreras comunican la dirección de una fuente de alimento mediante una danza. Los jardines con flores proporcionan recursos a estos insectos polinizadores.",
        "animales_naturaleza",
        "https://content.ces.ncsu.edu/honey-bee-dance-language",
        "danza",
    ),
    "bosques": Article(
        "Los árboles del bosque",
        "Los árboles poseen raíces que absorben agua del suelo y los mantienen sujetos. Sus hojas utilizan energía de la luz para producir alimento mediante la fotosíntesis. Los troncos contienen tejidos que transportan agua y otras sustancias. En un bosque conviven árboles, hongos, animales y numerosos microorganismos. La caída y descomposición de hojas devuelve nutrientes al suelo y contribuye al funcionamiento del ecosistema.",
        "animales_naturaleza",
        "https://www.fs.usda.gov/learn/trees",
        "nutrientes",
    ),
    "agua": Article(
        "El ciclo del agua",
        "El agua se evapora cuando pasa del estado líquido al gaseoso. En la atmósfera, el vapor puede enfriarse y formar gotas o cristales de hielo. Estos constituyen las nubes y pueden caer como precipitación. Parte del agua se infiltra en el suelo y posteriormente circula por acuíferos; otra parte circula por ríos hasta los mares. La energía solar y la gravedad impulsan distintos procesos de este ciclo.",
        "animales_naturaleza",
        "https://www.usgs.gov/special-topics/water-science-school/science/water-cycle",
        "gravedad",
    ),
    "arqueologia": Article(
        "La arqueología",
        "La arqueología estudia las sociedades del pasado mediante sus restos materiales. Los objetos, construcciones y huellas de actividad humana proporcionan información sobre formas de vida antiguas. Durante una excavación se registra la posición de cada hallazgo porque su contexto ayuda a interpretarlo. Una vasija puede aportar pistas sobre alimentos, técnicas de fabricación e intercambios. La arqueología compara evidencias antes de proponer explicaciones.",
        "historia_misterios",
        "https://www.britishmuseum.org/learn/schools",
        "contexto",
    ),
    "escritura": Article(
        "La historia de la escritura",
        "La escritura representa el lenguaje mediante signos y permite conservar mensajes. En Mesopotamia se desarrolló la escritura cuneiforme, cuyos signos se marcaban sobre tablillas de arcilla. En el antiguo Egipto se utilizaron jeroglíficos en distintos soportes. Los documentos escritos proporcionan información sobre comercio, leyes, relatos y administración. Los sistemas de escritura no son todos iguales: algunos representan sonidos y otros combinan diferentes clases de signos.",
        "historia_misterios",
        "https://www.britishmuseum.org/blog/how-write-cuneiform",
        "arcilla",
    ),
    "mapas": Article(
        "Los mapas y la cartografía",
        "Un mapa representa un territorio mediante símbolos y una escala. La escala relaciona las distancias del mapa con las del terreno. La leyenda proporciona una explicación del significado de colores y señales. Los mapas pueden mostrar relieve, ríos, ciudades o rutas de transporte. Un globo terráqueo representa la Tierra sobre una esfera, mientras que un mapa plano necesita una proyección y puede deformar formas o tamaños.",
        "historia_misterios",
        "https://education.nationalgeographic.org/resource/map/",
        "escala",
    ),
    "futbol": Article(
        "El fútbol",
        "El fútbol es un deporte entre dos equipos de once jugadores. El objetivo es introducir el balón en la portería contraria. Un partido reglamentario tiene dos tiempos de 45 minutos, además del tiempo añadido que corresponda. El guardameta posee reglas especiales para utilizar las manos dentro de su área. Las faltas, los saques y el fuera de juego se regulan en las Reglas de Juego.",
        "deportes",
        "https://theifab.com/laws/latest/the-players/",
        "45",
    ),
    "atletismo": Article(
        "Las carreras de relevos",
        "Una carrera de relevos distribuye el recorrido entre varios integrantes de un equipo que realizan tramos sucesivos. En las pruebas de pista se transporta un testigo y se entrega al siguiente corredor dentro de una zona señalada. Los relevos de cuatro por cien metros combinan velocidad y coordinación. Una entrega fuera de la zona puede causar la descalificación del equipo. El resultado depende del conjunto de corredores y de sus intercambios.",
        "deportes",
        "https://worldathletics.org/disciplines/relays/4x100-metres-relay",
        "testigo",
    ),
    "baloncesto": Article(
        "El baloncesto",
        "El baloncesto enfrenta a dos equipos que intentan introducir el balón en la canasta contraria. Cada equipo utiliza cinco jugadores en la cancha. Los jugadores pueden avanzar botando el balón o pasándolo a sus compañeros. Los lanzamientos pueden valer uno, dos o tres puntos según la situación. James Naismith ideó este deporte en 1891 y utilizó cestas para melocotones como primeras canastas.",
        "deportes",
        "https://springfield.edu/about/birthplace-of-basketball",
        "1891",
    ),
    "robots": Article(
        "Los robots",
        "Un robot es una máquina que ejecuta tareas mediante instrucciones. Puede utilizar sensores para obtener información del entorno y motores para producir movimientos. Los robots industriales realizan operaciones como ensamblar o transportar piezas. Otros robots exploran lugares difíciles de alcanzar. No todos tienen forma humana ni funcionan de manera autónoma: algunos siguen órdenes directas y otros toman decisiones dentro de un programa.",
        "tecnologia",
        "https://www.nasa.gov/learning-resources/for-kids-and-students/what-is-robotics-grades-5-8/",
        "sensores",
    ),
    "internet": Article(
        "Internet y sus redes",
        "Internet conecta redes de ordenadores que intercambian datos mediante protocolos compartidos. La información puede dividirse en paquetes que circulan hasta su destino. Una dirección de red permite identificar un destino dentro de ese intercambio. Internet y la Web no son lo mismo: la Web es uno de los servicios que utiliza Internet. El correo electrónico también utiliza la red para transportar mensajes.",
        "tecnologia",
        "https://www.internetsociety.org/internet/history-internet/brief-history-internet/",
        "Web",
    ),
    "energia solar": Article(
        "Los paneles solares",
        "Un panel fotovoltaico transforma luz en electricidad mediante materiales semiconductores. Las células solares producen corriente cuando reciben luz. Varios paneles pueden conectarse para proporcionar energía a una instalación. Los paneles solares térmicos funcionan de otra manera: utilizan el calor del Sol para calentar un fluido. La cantidad de energía obtenida depende de la luz recibida y de las características del sistema.",
        "tecnologia",
        "https://www.energy.gov/eere/solar/how-does-solar-work",
        "fotovoltaico",
    ),
    "julio verne": Article(
        "Julio Verne y sus aventuras",
        "Julio Verne fue un escritor francés nacido en 1828. Sus novelas de aventuras incorporan viajes, inventos y conocimientos científicos de su época. Entre sus obras están Viaje al centro de la Tierra y Veinte mil leguas de viaje submarino. El capitán Nemo es un personaje de esta última novela y dirige el submarino ficticio Nautilus. Numerosos relatos de Verne mezclan imaginación literaria y explicaciones sobre el mundo.",
        "cuentos_aventuras",
        "https://www.britannica.com/biography/Jules-Verne",
        "Nautilus",
    ),
    "vuelta mundo": Article(
        "La vuelta al mundo en ochenta días",
        "La vuelta al mundo en ochenta días es una novela de Julio Verne publicada en 1873. Su protagonista, Phileas Fogg, acepta una apuesta para completar un viaje alrededor del planeta. En la historia lo acompaña Passepartout y utilizan distintos medios de transporte. La novela organiza la aventura alrededor del tiempo, las rutas y los imprevistos. Sus personajes y su apuesta pertenecen a una obra de ficción.",
        "cuentos_aventuras",
        "https://www.gutenberg.org/ebooks/103",
        "1873",
    ),
    "isla tesoro": Article(
        "La isla del tesoro",
        "La isla del tesoro es una novela de aventuras de Robert Louis Stevenson publicada como libro en 1883. Jim Hawkins es el joven protagonista del relato. Un mapa inicia una expedición en busca de un tesoro y aparecen personajes como Long John Silver. El autor utiliza la navegación, las decisiones y los conflictos entre personajes para construir la historia. El mapa y los piratas forman parte de la ficción de esta novela.",
        "cuentos_aventuras",
        "https://www.gutenberg.org/ebooks/120",
        "1883",
    ),
    "real madrid": Article(
        "Real Madrid Club de Fútbol",
        "El Real Madrid Club de Fútbol es un club deportivo de Madrid, España. Fue fundado el 6 de marzo de 1902 con el nombre de Madrid Foot Ball Club. En 1920 recibió el título de Real. Su equipo de fútbol utiliza tradicionalmente camiseta blanca y juega en el estadio Santiago Bernabéu. Este estadio fue inaugurado en 1947. La FIFA eligió al Real Madrid como el mejor club del siglo XX. El club también cuenta con una sección de baloncesto. Sus competiciones, su estadio y su historia forman parte del deporte español.",
        "deportes",
        "https://www.realmadrid.com/es-ES/el-club/historia",
        "FIFA",
    ),
    "biologia marina": Article(
        "Biología marina y fauna oceánica",
        "La biología marina estudia los seres vivos que habitan los mares y océanos y sus relaciones con el ambiente. La fauna marina incluye peces, moluscos, crustáceos y mamíferos como las ballenas. Las algas y el fitoplancton utilizan luz para realizar fotosíntesis y sostienen numerosas cadenas alimentarias. Los arrecifes de coral proporcionan refugio a una gran diversidad de animales. La luz disminuye con la profundidad, por lo que los organismos de zonas profundas presentan adaptaciones a la oscuridad. Algunas especies producen luz mediante bioluminiscencia. La salinidad y la temperatura influyen en la distribución de los seres vivos marinos.",
        "animales_naturaleza",
        "https://oceanservice.noaa.gov/facts/",
        "bioluminiscencia",
    ),
    "tiburon": Article(
        "Los tiburones",
        "Los tiburones son peces cuyo esqueleto está formado principalmente por cartílago. Utilizan branquias para obtener oxígeno del agua. Sus dientes pueden renovarse durante la vida y sus formas varían entre especies. No todos comen presas grandes: el tiburón ballena se alimenta filtrando pequeños organismos. Los tiburones participan en las redes alimentarias marinas. Algunas especies ponen huevos y otras dan a luz crías vivas. Como otros peces, necesitan condiciones adecuadas en el océano para sobrevivir.",
        "animales_naturaleza",
        "https://oceanservice.noaa.gov/facts/sharks.html",
        "ballena",
    ),
    "dinosaurios": Article(
        "Dinosaurios",
        "Los dinosaurios forman un grupo de animales que apareció hace más de 230 millones de años. Los fósiles de huesos, huevos y huellas proporcionan información sobre su diversidad. Algunas especies comían plantas y otras se alimentaban de animales. Los dinosaurios no avianos desaparecieron hace unos 66 millones de años, al final del Cretácico. Las aves actuales pertenecen al grupo de los dinosaurios y conservan características heredadas de sus antepasados. No todos los dinosaurios tuvieron el mismo tamaño ni vivieron al mismo tiempo.",
        "animales_naturaleza",
        "https://www.nhm.ac.uk/discover/what-are-dinosaurs.html",
        "aves",
    ),
    "sistema solar": Article(
        "El sistema solar",
        "El sistema solar está formado por el Sol y los cuerpos que se mueven bajo su influencia gravitatoria. Posee ocho planetas: Mercurio, Venus, Tierra, Marte, Júpiter, Saturno, Urano y Neptuno. También incluye planetas enanos, satélites, asteroides y cometas. El Sol es una estrella y concentra la mayor parte de la masa del sistema. Los planetas describen órbitas a su alrededor. Los cuatro planetas más cercanos al Sol tienen superficies rocosas. Más allá de Marte se encuentra el cinturón principal de asteroides.",
        "ciencia_espacio",
        "https://science.nasa.gov/solar-system/facts/",
        "ocho",
    ),
    "agujeros negros": Article(
        "Agujeros negros",
        "Los agujeros negros son regiones del espacio cuya gravedad impide que la luz escape desde su interior. El límite a partir del cual nada puede regresar se llama horizonte de sucesos. Algunos agujeros negros se forman cuando estrellas muy masivas colapsan al terminar su evolución. Los astrónomos estudian la materia cercana y sus efectos gravitatorios para obtener información sobre ellos. Un agujero negro no absorbe de forma inevitable todo lo que existe a cualquier distancia: su efecto depende de la masa y de la distancia.",
        "ciencia_espacio",
        "https://science.nasa.gov/universe/black-holes/",
        "horizonte",
    ),
    "volcanes": Article(
        "Los volcanes",
        "Un volcán es una abertura de la corteza terrestre por la que pueden salir materiales del interior del planeta. La roca fundida recibe el nombre de magma dentro de la Tierra y de lava cuando alcanza la superficie. Una erupción puede emitir gases, ceniza y fragmentos de roca. Numerosos volcanes aparecen cerca de los límites de placas tectónicas, aunque también existen sobre puntos calientes. Las erupciones pueden construir nuevas formas del relieve, como islas y montañas. No todos los volcanes tienen la misma forma ni presentan erupciones iguales.",
        "ciencia_espacio",
        "https://www.usgs.gov/programs/VHP/about-volcanoes",
        "magma",
    ),
    "antiguo egipto": Article(
        "Antiguo Egipto",
        "El antiguo Egipto fue una civilización que se desarrolló junto al río Nilo, en el noreste de África. Las crecidas del río favorecían la agricultura en terrenos próximos a sus orillas. Los egipcios construyeron pirámides y utilizaron sistemas de escritura como los jeroglíficos. Los faraones gobernaban el territorio y la administración organizaba trabajos y recursos. El papiro proporcionaba un soporte para escribir. Las pirámides de Guiza pertenecen al Reino Antiguo y muestran conocimientos de construcción y organización. La historia egipcia abarca muchos siglos y diferentes periodos.",
        "historia_misterios",
        "https://www.britishmuseum.org/collection/egypt",
        "papiro",
    ),
    "inteligencia artificial": Article(
        "Inteligencia artificial",
        "La inteligencia artificial es un campo de la informática que desarrolla sistemas capaces de realizar tareas como reconocer patrones o procesar lenguaje. Algunos métodos aprenden relaciones a partir de datos durante un entrenamiento. Un modelo puede utilizar esas relaciones para clasificar imágenes o producir respuestas. Sus resultados dependen de los datos y del diseño, por lo que pueden contener errores. La inteligencia artificial no garantiza que una afirmación sea verdadera. Revisar sus resultados y contrastarlos con fuentes ayuda a utilizarla de manera responsable.",
        "tecnologia",
        "https://www.ibm.com/topics/artificial-intelligence",
        "errores",
    ),
    "robots submarinos": Article(
        "Robots del océano",
        "Los robots del océano permiten observar lugares submarinos y obtener imágenes o muestras. Un vehículo operado a distancia, conocido como ROV, puede estar conectado a un barco mediante un cable. Ese cable permite transmitir información y órdenes entre el vehículo y los operadores. Las cámaras, luces y sensores ayudan a explorar zonas donde llega poca luz. Otros vehículos submarinos pueden funcionar con instrucciones programadas y sin un cable de control. Estos aparatos se utilizan para estudiar el fondo marino y observar animales en su ambiente.",
        "tecnologia",
        "https://oceanexplorer.noaa.gov/ocean-fact/rov/",
        "cable",
    ),
    "juegos olimpicos": Article(
        "Juegos Olímpicos",
        "Los Juegos Olímpicos modernos reúnen competiciones de numerosos deportes. La primera edición de los Juegos de verano de la era moderna se celebró en Atenas en 1896. Los Juegos de invierno comenzaron en 1924 en Chamonix. La tradición antigua se relaciona con competiciones celebradas en Olimpia, en Grecia. El símbolo olímpico tiene cinco aros entrelazados. Los deportes y las pruebas han cambiado a lo largo de las ediciones. Los Juegos de verano y los de invierno tienen programas deportivos diferentes.",
        "deportes",
        "https://olympics.com/ioc/ancient-olympic-games",
        "1896",
    ),
    "robots inteligencia artificial": Article(
        "Robots e Inteligencia Artificial",
        "Los robots son máquinas que ejecutan instrucciones con la finalidad de realizar tareas físicas. Algunos utilizan sensores que proporcionan información del entorno y motores que producen movimientos. La inteligencia artificial comprende métodos informáticos para reconocer patrones o procesar lenguaje. Un robot puede utilizar un modelo de inteligencia artificial, pero numerosos robots funcionan mediante programas sin aprendizaje automático. El entrenamiento de un modelo utiliza datos y sus resultados pueden contener errores. Por consiguiente, un sistema robótico necesita controles adecuados a la tarea y no posee necesariamente forma humana.",
        "tecnologia",
        "https://www.nasa.gov/robotics/",
        "forma humana",
    ),
    "pequeno faro": Article(
        "El Viaje del Pequeño Faro",
        "Este cuento original presenta a un pequeño faro imaginario que desea comprender su trabajo junto al mar. Una noche observa las embarcaciones y utiliza su luz con la finalidad de indicar la posición de la costa. Posteriormente descubre que los faros reales proporcionan señales luminosas para ayudar a la navegación. Numerosos faros poseen secuencias de destellos que permiten distinguirlos. El protagonista no navega: su viaje consiste en comprender su función desde la orilla. Los personajes pertenecen a la ficción, mientras que la explicación sobre las señales de los faros describe una característica real.",
        "cuentos_aventuras",
        "https://oceanservice.noaa.gov/facts/lighthouse.html",
        "destellos",
    ),
}

BANK = {
    "ciencia_espacio": ("tierra", "luna", "telescopio"),
    "animales_naturaleza": ("abejas", "bosques", "agua"),
    "historia_misterios": ("arqueologia", "escritura", "mapas"),
    "deportes": ("futbol", "atletismo", "baloncesto"),
    "tecnologia": ("robots", "internet", "energia solar"),
    "cuentos_aventuras": ("julio verne", "vuelta mundo", "isla tesoro"),
}

# Updated public reference material; received Wikipedia/user originals are untouched.
for _key, _units in SOURCE_REVISIONS.items():
    ARTICLES[_key] = replace(ARTICLES[_key], text=" ".join(_units))
