"""Reviewed multiword educational paraphrases, with explicit agreement/sense.

These extend the existing 500+ reviewed entries; suffixes are never stripped to
guess a synonym. Names, quantities, negation and scientific uncertainty remain.
"""

PAIRS = """
la locomoción|la forma de moverse
su locomoción|su forma de moverse
la hibernación|el largo sueño de invierno
la migración de las aves|el viaje de las aves
la supervivencia|el hecho de seguir vivo
para sobrevivir|para seguir con vida
la extinción de una especie|la desaparición de una especie
los depredadores|los animales que cazan
un depredador|un animal que caza
las presas de los tiburones|los animales que cazan los tiburones
la fauna del bosque|los animales del bosque
la flora del bosque|las plantas del bosque
la biodiversidad|la variedad de seres vivos
la deforestación|la pérdida de bosques
la reforestación|la plantación de árboles nuevos
los organismos microscópicos|los seres vivos muy pequeños
un organismo microscópico|un ser vivo muy pequeño
los seres unicelulares|los seres de una sola célula
la cadena alimentaria|la cadena de quién se come a quién
las cadenas alimentarias|las cadenas de quién se come a quién
la polinización|el paso del polen entre flores
la germinación|el nacimiento de una planta desde una semilla
la fertilidad del suelo|la riqueza del suelo para cultivar
los nutrientes del suelo|el alimento que aporta el suelo
el caudal del río|la cantidad de agua del río
las precipitaciones|la lluvia, la nieve y el granizo
el vapor de agua|el agua en forma de gas
las aguas subterráneas|las aguas que están bajo el suelo
la erosión|el desgaste del suelo o la roca
el enfriamiento|la pérdida de calor
el calentamiento|el aumento de calor
la solidificación|el paso de líquido a sólido
la evaporación del agua|el paso del agua a vapor
la condensación del vapor|el paso del vapor a gotas
las placas tectónicas|las grandes piezas de la corteza terrestre
la corteza terrestre|la capa exterior de la Tierra
el interior terrestre|el interior de la Tierra
las emisiones volcánicas|los gases y materiales que echa un volcán
la actividad volcánica|la actividad de los volcanes
la exploración espacial|los viajes y estudios del espacio
las misiones espaciales|los viajes de estudio al espacio
una misión espacial|un viaje de estudio al espacio
la superficie lunar|la parte exterior de la Luna
la superficie marciana|la parte exterior de Marte
el satélite terrestre|la Luna, que gira alrededor de la Tierra
la radiación solar|la energía que emite el Sol
la atracción gravitatoria|la fuerza de la gravedad
la influencia gravitatoria|el efecto de la gravedad
los cuerpos celestes|los objetos del espacio
la observación astronómica|el estudio del cielo
los astrónomos|quienes estudian los astros
un astrónomo|una persona que estudia los astros
la órbita terrestre|el camino de la Tierra alrededor del Sol
la rotación terrestre|el giro de la Tierra sobre su eje
las distancias interplanetarias|las distancias entre planetas
una nave tripulada|una nave con personas a bordo
una sonda no tripulada|una nave de estudio sin personas a bordo
la civilización egipcia|el pueblo del antiguo Egipto
las civilizaciones antiguas|los pueblos de otros tiempos
la construcción de|la obra de hacer
la edificación de|la obra de hacer
la conservación de|el cuidado de
la fabricación de|la tarea de hacer
la comercialización de|la venta de
el descubrimiento de|el hallazgo de
la denominación de|el nombre de
bajo la denominación de|con el nombre de
la fundación de|el inicio de
la inauguración de|la apertura de
la indumentaria tradicional|la ropa que se usa desde hace tiempo
los encuentros deportivos|los partidos de deporte
los encuentros como local|los partidos en su propio estadio
las instalaciones deportivas|los lugares para hacer deporte
la trayectoria histórica|la historia
la organización del equipo|el modo de ordenar el equipo
el reglamento|las reglas
la reglamentación|las reglas
reglamentario|según las reglas
reglamentaria|según las reglas
el guardameta|el portero
los guardametas|los porteros
los integrantes del equipo|las personas del equipo
los competidores|quienes compiten
los participantes|quienes participan
las competiciones|las pruebas de deporte
la descalificación del equipo|la eliminación del equipo
los desplazamientos|los cambios de lugar
el desplazamiento|el cambio de lugar
la velocidad de desplazamiento|la rapidez al moverse
la propulsión|la fuerza que impulsa
la comunicación|el intercambio de mensajes
la transmisión de datos|el envío de datos
el almacenamiento de datos|la tarea de guardar datos
el procesamiento de datos|el trabajo con los datos
la recopilación de datos|la tarea de reunir datos
los dispositivos electrónicos|los aparatos electrónicos
un dispositivo electrónico|un aparato electrónico
las instrucciones programadas|los pasos que fija un programa
las operaciones repetitivas|las tareas que se repiten
el ensamblaje de piezas|la unión de piezas
ensamblar piezas|unir piezas
las tareas automatizadas|las tareas que una máquina hace sola
la interacción|el trato entre unos y otros
las imágenes digitales|las imágenes que guarda un ordenador
la navegación por Internet|el uso de páginas de Internet
el intercambio de información|el envío y la recepción de datos
la inteligencia humana|la capacidad de pensar de las personas
las herramientas tecnológicas|los aparatos y programas
los materiales pedagógicos|los materiales para aprender
la comprensión lectora|la capacidad de entender lo que se lee
las dificultades fonológicas|los problemas con los sonidos del habla
los procesos cognitivos|los procesos de la mente
la sintomatología|el conjunto de síntomas
la consolidación|el hecho de afianzar algo
la proliferación|el aumento rápido
los estímulos audiovisuales|las imágenes y los sonidos que recibimos
obstaculiza|dificulta
obstaculizan|dificultan
facilita|hace más fácil
facilitan|hacen más fácil
contribuye a|ayuda a
contribuyen a|ayudan a
se desarrolló|surgió
se desarrollaron|surgieron
se encuentra|está
se encuentran|están
se denomina|se llama
se denominan|se llaman
recibe la denominación de|se llama
con posterioridad a|después de
con anterioridad a|antes de
en numerosas ocasiones|muchas veces
en determinadas ocasiones|a veces
de manera simultánea|a la vez
de manera progresiva|poco a poco
de forma gradual|poco a poco
en las proximidades de|cerca de
en las inmediaciones de|cerca de
en su totalidad|por completo
en su mayor parte|en gran parte
en consecuencia|por eso
por el contrario|en cambio
no obstante|pero
con el propósito de|para
a fin de|para
"""

CHILD_PAIRS = dict(line.split("|", 1) for line in PAIRS.strip().splitlines())
