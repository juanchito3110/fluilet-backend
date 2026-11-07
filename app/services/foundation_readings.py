"""Early-reader restatements, one tuple item per complete source sentence.

Short explanations retain the educational term rather than substituting an
unrelated dictionary sense. These are openly authored teaching alignments.
"""

REVISIONS = {
    "nasa": (
        "La NASA es un grupo que estudia el espacio. Ese grupo es de Estados Unidos. Empezó el 1 de octubre de 1958.",
        "Sus equipos crean naves para estudiar el espacio. Estudian la Tierra y el sistema solar. También estudian el universo, todo lo que existe.",
        "Apolo 11 llegó a la Luna en 1969. Llevó a las primeras personas que pisaron la Luna.",
        "Las sondas y los robots van a sitios lejanos. Pueden ir sin llevar gente a bordo. Envían datos por señales de radio.",
        "Otros satélites miran la Tierra desde lo alto. Dan datos sobre las nubes, los mares y el hielo.",
    ),
    "vikingos": (
        "Los vikingos eran del norte de Europa. Esa zona se llama Escandinavia. Viajaron por mar en la Edad Media.",
        "Sus barcos eran de madera. Para moverse usaban velas o remos. Podían ir por la costa y subir por los ríos.",
        "Unos viajes servían para atacar otros lugares. En muchos otros viajes se vendían o cambiaban productos.",
        "Algunos barcos llevaban tallas en la proa. La proa es la parte de delante del barco. Las tallas eran figuras de animales hechas de madera. Podían tener forma de dragón o de serpiente.",
    ),
    "castillos": (
        "Los castillos eran casas fuertes de la Edad Media. La gente vivía en ellos. Sus muros servían para defenderse de los ataques.",
        "Las murallas y las torres protegían el castillo. Desde lo alto se podía ver a lo lejos. Así era más fácil ver a quienes se acercaban.",
        "Algunos castillos tenían un foso junto a sus muros. El foso era un gran hueco en el suelo. Un puente podía subir y cerrar el paso. Así se controlaba quién podía entrar.",
        "Dentro del castillo había gente que hacía la comida. Eran los cocineros. También había artesanos que hacían cosas a mano. Sus tareas eran parte de la vida del castillo.",
    ),
    "videojuegos": (
        "Un videojuego es un programa que sigue reglas. Quien juega le da órdenes con sus acciones. El juego responde con imágenes y sonidos.",
        "Quienes crean el programa escriben sus instrucciones. Las instrucciones son pasos que la máquina sigue. Esos pasos guían lo que hacen los personajes. También ven si se logra una meta.",
        "Unas personas crean los lugares y los retos del juego. Otras dibujan las imágenes. Otras hacen la música y los sonidos.",
        "Antes de compartir el juego hay que probarlo. Las pruebas sirven para hallar fallos. Sus creadores pueden corregirlos y ajustar las reglas.",
    ),
    "inventos": (
        "Un telescopio sirve para ver cosas que están lejos. Recoge luz con unas lentes o con unos espejos.",
        "Un microscopio sirve para ver cosas muy pequeñas. Deja ver detalles que no vemos solo con los ojos. Algunas células son así de pequeñas.",
        "Quienes inventan hacen pruebas para mejorar sus aparatos. Comparan lo que pasa con cada diseño. Así eligen qué forma de hacerlo va mejor.",
        "Estos inventos no hacen las preguntas por la gente. Las personas siguen pensando qué quieren saber. Los aparatos ayudan a buscar nuevas pruebas.",
    ),
    "piratas caribe": (
        "Los piratas atacaban barcos para robar su carga. Algunos lo hacían en el mar Caribe. Allí pasaban barcos que iban a vender sus productos.",
        "Los barcos de comercio llevaban cosas de gran valor. Podían ser telas, comida o metales. Su ruta iba de un puerto a otro por mar.",
        "Para navegar había que conocer los vientos y las costas. La tripulación debía trabajar en equipo. Cada persona tenía tareas a bordo.",
        "Muchos cuentos hablan de cofres llenos de tesoros enterrados. Pero eso es parte de muchas historias de ficción. Los piratas reales no solían guardar así sus tesoros.",
    ),
    "energia solar": (
        "Un panel fotovoltaico cambia la luz en corriente eléctrica. Esa corriente es la que lleva la electricidad. Para ello usa materiales que se llaman semiconductores.",
        "Sus células solares crean corriente al recibir luz. Son las partes del panel que hacen ese trabajo.",
        "Se puede unir más de un panel. Juntos dan energía a las piezas que se han montado.",
        "Los paneles solares térmicos usan el calor del Sol. Con ese calor se calienta un fluido del sistema. No funcionan igual que los que crean corriente.",
        "La energía que dan depende de la luz recibida. También depende de cómo sea el sistema.",
    ),
    "inteligencia artificial": (
        "La inteligencia artificial es un campo de la informática. Trata de hacer tareas propias de la mente con máquinas. Puede hallar patrones, rasgos que se repiten en los datos. También puede tratar lo que decimos o escribimos.",
        "Algunos métodos aprenden a partir de datos. En esos datos buscan cosas que tienen algo en común. Ese aprendizaje ocurre durante su entrenamiento.",
        "Un modelo usa los lazos que aprendió en los datos. Puede poner imágenes en grupos o crear respuestas.",
        "Los datos y el diseño influyen en lo que da. Por eso sus resultados pueden tener errores.",
        "La inteligencia artificial no asegura que algo sea verdad.",
        "Conviene revisar los resultados y compararlos con fuentes. Así se comprueba si coinciden con hechos reales. Es una forma de usar estos sistemas con cuidado.",
    ),
    "robots inteligencia artificial": (
        "Un robot es una máquina que sigue instrucciones. Las instrucciones dicen qué pasos debe dar. Con esos pasos puede hacer tareas físicas.",
        "Algunos robots usan sensores para saber qué hay cerca. Un sensor es una pieza que recibe datos. Los motores hacen que sus partes se muevan.",
        "La inteligencia artificial es un campo de la informática. Sirve para reconocer patrones y tratar el lenguaje. Un patrón es un rasgo que se repite.",
        "Un robot puede usar un modelo de inteligencia artificial. Pero muchos siguen un programa sin aprender de datos.",
        "Un modelo usa datos durante su entrenamiento. Sus resultados pueden tener errores.",
        "Un robot necesita controles adecuados para su tarea. No tiene por qué tener forma de persona.",
    ),
}

INTERMEDIATE = {
    "real madrid": (
        "El Real Madrid es una entidad deportiva con sede en Madrid, España. Su fundación tuvo lugar el 6 de marzo de 1902. Su primer nombre fue Madrid Foot Ball Club.",
        "La entidad recibió el título de Real en 1920. Desde entonces, esa distinción forma parte de su nombre.",
        "La indumentaria tradicional del equipo de fútbol es blanca. Disputa sus encuentros como local en el estadio Santiago Bernabéu.",
        "El estadio se inauguró en 1947. Esa fecha forma parte de la historia de las instalaciones del club.",
        "La FIFA eligió al Real Madrid como el mejor club del siglo XX. El reconocimiento procede de esa organización deportiva internacional.",
        "La entidad también posee una sección de baloncesto. Su actividad deportiva abarca más de una disciplina.",
    ),
}
