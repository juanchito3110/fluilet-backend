"""Friendly glossary with literal examples from the delivered reading."""

import re

from app.education import normalized
from app.nlp.segmentation import WORD_RE, sentences, words

# Definitions are authored independently; examples always come from the reading.
_ENTRIES = (
    ("biología", "La ciencia que estudia los seres vivos."),
    ("fauna", "El conjunto de animales de un lugar."),
    ("océano|océanos", "Una enorme extensión de agua salada."),
    ("mar|mares", "Una extensión de agua salada conectada con el océano."),
    ("marina|marino|marinos|marinas", "Que pertenece al mar o vive en él."),
    ("peces|pez", "Animales acuáticos que respiran mediante branquias."),
    ("moluscos", "Animales de cuerpo blando, como caracoles y pulpos."),
    ("crustáceos", "Animales con una cubierta externa, como cangrejos y camarones."),
    ("mamíferos", "Animales cuyas crías se alimentan de leche materna."),
    ("algas", "Organismos que suelen vivir en el agua y pueden aprovechar la luz."),
    ("fitoplancton", "Seres muy pequeños que flotan en el agua y aprovechan la luz."),
    ("bioluminiscencia", "La capacidad de algunos seres vivos para producir luz."),
    ("arrecife|arrecifes", "Una estructura submarina donde viven muchos organismos."),
    ("coral|corales", "Pequeños animales marinos; algunos construyen estructuras duras."),
    ("salinidad", "La cantidad de sales que contiene el agua."),
    ("temperatura", "Una medida de lo caliente o frío que está algo."),
    ("fútbol", "Un deporte en el que dos equipos intentan marcar goles con un balón."),
    ("club", "Una organización de personas que comparten una actividad."),
    ("estadio", "Un recinto preparado para competiciones y espectadores."),
    ("equipo|equipos", "Un grupo de personas que colaboran para un objetivo."),
    ("baloncesto", "Un deporte en el que se intenta meter el balón en una canasta."),
    ("balón", "Una pelota utilizada en distintos deportes."),
    ("portería", "El espacio donde se intenta marcar un gol."),
    ("guardameta", "El jugador que defiende la portería."),
    ("competición|competiciones", "Una actividad en la que se comparan resultados deportivos."),
    ("testigo", "En los relevos, el objeto que pasa de un corredor a otro."),
    ("relevos", "Una prueba en la que los participantes se turnan para completar un recorrido."),
    ("olímpico|olímpicos|olímpica|olímpicas", "Relacionado con los Juegos Olímpicos."),
    ("planeta|planetas", "Un gran cuerpo celeste que gira alrededor de una estrella."),
    ("satélite|satélites", "Un cuerpo que gira alrededor de otro más grande."),
    ("órbita|órbitas", "El recorrido de un cuerpo que gira alrededor de otro."),
    ("rotación", "El giro de un cuerpo sobre su propio eje."),
    ("atmósfera", "La capa de gases que rodea un planeta."),
    ("gravedad", "La atracción que existe entre los cuerpos con masa."),
    ("estrella|estrellas", "Una gran esfera de gas que produce luz y energía."),
    ("solar|solares", "Relacionado con el Sol."),
    ("masa", "Una medida de la cantidad de materia de un cuerpo."),
    ("asteroides|asteroide", "Cuerpos rocosos que giran alrededor del Sol."),
    ("cometas|cometa", "Cuerpos con hielo y polvo que giran alrededor del Sol."),
    ("galaxia|galaxias", "Un enorme conjunto de estrellas, gas y polvo."),
    ("telescopio|telescopios", "Un instrumento que recoge luz para observar objetos lejanos."),
    ("lente|lentes", "Una pieza transparente que cambia el recorrido de la luz."),
    ("espejo|espejos", "Una superficie que refleja la luz."),
    ("cráter|cráteres", "Una depresión del terreno que puede formarse por un impacto o un volcán."),
    (
        "volcán|volcanes",
        "Una abertura de la corteza por donde pueden salir materiales del interior terrestre.",
    ),
    ("magma", "Roca fundida que se encuentra dentro de la Tierra."),
    ("lava", "Roca fundida que ha llegado a la superficie."),
    ("erupción|erupciones", "La salida de materiales desde un volcán."),
    ("corteza", "La capa exterior sólida de la Tierra, en este contexto."),
    ("dinosaurio|dinosaurios", "Un grupo de animales al que también pertenecen las aves."),
    ("fósil|fósiles", "Restos o huellas de seres vivos conservados del pasado."),
    ("huella|huellas", "Una marca que deja el paso o el contacto de algo."),
    ("antepasado|antepasados", "Seres vivos de generaciones anteriores."),
    ("tiburón|tiburones", "Peces con un esqueleto formado principalmente por cartílago."),
    ("cartílago", "Un material firme y flexible que forma parte de algunos esqueletos."),
    ("branquias", "Estructuras que permiten a muchos animales obtener oxígeno del agua."),
    ("oxígeno", "Un gas que muchos seres vivos utilizan para respirar."),
    ("robot|robots", "Una máquina que realiza tareas siguiendo instrucciones."),
    ("sensor|sensores", "Un dispositivo que detecta información del entorno."),
    ("motor|motores", "Un mecanismo que transforma energía para producir movimiento."),
    ("programa|programas", "Un conjunto de instrucciones que ejecuta una máquina."),
    ("datos", "Información que se puede registrar y procesar."),
    ("algoritmo|algoritmos", "Una serie ordenada de pasos para resolver una tarea."),
    ("informática", "El estudio del tratamiento de información con ordenadores."),
    (
        "modelo|modelos",
        "En informática, un sistema que representa relaciones aprendidas o definidas.",
    ),
    (
        "inteligencia artificial",
        "Sistemas informáticos que realizan tareas como reconocer patrones.",
    ),
    ("patrón|patrones", "Una forma o relación que se repite y puede reconocerse."),
    ("Internet", "Una gran red que conecta otras redes de ordenadores."),
    ("red|redes", "Un conjunto de elementos conectados para intercambiar información."),
    ("protocolo|protocolos", "Reglas que permiten que los sistemas se comuniquen."),
    ("paquete|paquetes", "En una red, una parte de los datos que se envían."),
    ("energía", "La capacidad de producir cambios o realizar un trabajo."),
    ("electricidad", "Fenómenos relacionados con las cargas eléctricas."),
    ("fotovoltaico|fotovoltaica", "Que transforma luz en electricidad."),
    (
        "semiconductor|semiconductores",
        "Materiales que permiten controlar el paso de corriente eléctrica.",
    ),
    ("cable", "Un elemento que puede transportar energía o señales."),
    ("submarino|submarinos|submarina|submarinas", "Que se encuentra o funciona debajo del mar."),
    ("vehículo|vehículos", "Un medio que sirve para desplazarse o transportar algo."),
    (
        "civilización|civilizaciones",
        "Una sociedad con formas compartidas de organización y cultura.",
    ),
    ("faraón|faraones", "El título de quienes gobernaban el antiguo Egipto."),
    ("jeroglífico|jeroglíficos", "Signos de una escritura utilizada en el antiguo Egipto."),
    ("papiro", "Un material de escritura elaborado con una planta."),
    ("pirámide|pirámides", "Una construcción con caras que se unen en una parte alta."),
    ("agricultura", "La actividad de cultivar plantas para obtener alimentos y otros productos."),
    ("arqueología", "El estudio de sociedades del pasado mediante sus restos materiales."),
    ("hallazgo|hallazgos", "Algo que se encuentra durante una búsqueda o investigación."),
    ("contexto", "La situación y los elementos que ayudan a entender algo."),
    ("evidencia|evidencias", "Información o restos que ayudan a comprobar una explicación."),
    ("vasija", "Un recipiente que puede servir para guardar o transportar sustancias."),
    ("arcilla", "Un material del suelo que puede moldearse al mezclarse con agua."),
    ("escritura", "Un sistema de signos que representa el lenguaje."),
    ("cuneiforme", "Una escritura cuyos signos tienen forma de cuña."),
    ("mapa|mapas", "Una representación de un territorio mediante símbolos."),
    ("escala", "En un mapa, la relación entre la distancia dibujada y la real."),
    ("leyenda", "En un mapa, la explicación de sus símbolos."),
    ("proyección", "Una manera de representar una superficie curva en un plano."),
    ("territorio|territorios", "Una zona de tierra con características o límites."),
    ("novela|novelas", "Un relato literario extenso."),
    ("personaje|personajes", "Un ser que participa en una historia."),
    ("protagonista", "El personaje principal de un relato."),
    ("ficción", "Una historia creada con imaginación."),
    ("autor|autores|escritor|escritora", "Una persona que crea un texto o una obra."),
    ("aventura|aventuras", "Una experiencia que incluye retos o sucesos poco habituales."),
    ("navegación", "La actividad de desplazarse y orientarse por el agua."),
    (
        "fotosíntesis",
        "El proceso con el que plantas y otros organismos aprovechan luz para producir alimento.",
    ),
    ("polen", "Pequeños granos que intervienen en la reproducción de muchas plantas."),
    ("néctar", "Un líquido dulce que producen muchas flores."),
    ("colonia|colonias", "Un grupo de seres vivos que vive de forma organizada."),
    ("polinizador|polinizadores", "Seres que transportan polen entre flores."),
    ("raíz|raíces", "Partes de una planta que suelen sujetarla y absorber agua."),
    ("ecosistema", "Los seres vivos de un lugar y sus relaciones con el ambiente."),
    ("nutriente|nutrientes", "Sustancias que los seres vivos necesitan para crecer y funcionar."),
    ("evapora|evaporación", "El paso del agua líquida a vapor."),
    ("precipitación", "Agua que cae de la atmósfera, como lluvia o nieve."),
    ("vapor", "El estado gaseoso del agua, en este contexto."),
    ("alumno|alumnos", "Personas que aprenden y practican conocimientos."),
    ("libro|libros", "Un conjunto de páginas con textos o imágenes."),
    ("escuela", "Un lugar dedicado a aprender y enseñar."),
    ("lee|leer", "Comprender palabras o signos escritos."),
    ("usa|usan|utiliza|utilizan", "Emplear algo para un propósito."),
)


def _example(text, term):
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
    for sentence in sentences(text):
        found = pattern.search(sentence)
        if found:
            if len(sentence) <= 240:
                return sentence
            start = max(0, found.start() - 70)
            return sentence[start : found.end() + 100].strip()
    return term


def key_vocabulary(text):
    result, chosen = [], set()
    available = {normalized(token) for token in words(text)}
    for forms, definition in _ENTRIES:
        for term in forms.split("|"):
            if " " not in term and normalized(term) not in available:
                continue
            match = re.search(r"\b" + re.escape(term) + r"\b", text, re.I)
            if match and normalized(match[0]) not in chosen:
                word = match[0]
                result.append(
                    {"word": word, "definition": definition, "example": _example(text, word)}
                )
                chosen.add(normalized(word))
                break
        if len(result) == 4:
            return result
    # An unfamiliar article may define its own terms. Keep the definition
    # extractive instead of guessing meanings from a neural model.
    for sentence in sentences(text):
        match = re.match(r"(?:El|La|Un|Una)\s+(.{2,60}?)\s+(?:es|son|se llama)\s+(.+)", sentence)
        if match and normalized(match[1]) not in chosen and len(words(match[1])) <= 4:
            result.append({"word": match[1], "definition": match[2], "example": sentence})
            chosen.add(normalized(match[1]))
            if len(result) == 4:
                return result
    # Context-only entries are explicitly labelled; no made-up dictionary meaning.
    for match in WORD_RE.finditer(text):
        word = match[0]
        if len(word) < 5 or not word.isalpha() or normalized(word) in chosen:
            continue
        example = _example(text, word)
        result.append(
            {
                "word": word,
                "definition": f"En esta lectura, su significado se entiende en este contexto: «{example}»",
                "example": example,
            }
        )
        chosen.add(normalized(word))
        if len(result) == 4:
            break
    return result


def fun_fact(text, hint=""):
    units = sentences(text)
    suitable = [unit for unit in units if 5 <= len(words(unit)) <= 50]
    selected = next(
        (unit for unit in suitable if hint and hint.casefold() in unit.casefold()), None
    )
    selected = selected or next((unit for unit in suitable if re.search(r"\d", unit)), None)
    selected = selected or (suitable[0] if suitable else units[0])
    if len(selected) > 480:
        selected = selected[:477].rsplit(" ", 1)[0] + "…"
    return f"Dato de la lectura: «{selected}»"


def enrich(text, hint=""):
    return fun_fact(text, hint), key_vocabulary(text)
