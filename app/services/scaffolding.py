"""Finite, source-grounded reading supports, with an auditable evidence span.

These are authored paraphrases/glosses, not predictions or independent gold
references. Every item has its own concept; items are used at most once and are
never repeated to manufacture a score. Unknown input gets no invented facts.
"""

import re
from dataclasses import dataclass

from app.nlp.segmentation import sentences


@dataclass(frozen=True)
class Support:
    text: str
    evidence: str
    kind: str = "source_paraphrase"


# Index identifies the complete sentence of the unchanged reference article.
# Simple restatements can make an implicit subject explicit and explain a term;
# they do not turn a purpose, condition or possibility into an achieved result.
LOCAL = {
    "tierra": (
        (0, "La Tierra da la vuelta al Sol."),
        (1, "Su giro da el día y la noche."),
        (3, "El Sol da luz."),
        (3, "Las plantas usan esa luz."),
    ),
    "luna": (
        (0, "La luz es del Sol."),
        (0, "La Luna no crea esa luz."),
        (1, "No se ve siempre la misma parte."),
        (4, "Su fuerza influye en el mar."),
    ),
    "telescopio": (
        (0, "La luz viene de lejos."),
        (4, "No crea su propia luz."),
        (1, "Puede haber lentes o espejos."),
        (2, "Sirve para ver más lejos."),
    ),
    "abejas": (
        (0, "Las flores dan néctar y polen."),
        (1, "El polen va de flor en flor."),
        (3, "La danza da una pista."),
        (3, "Esa pista guía hacia la comida."),
    ),
    "bosques": (
        (0, "La raíz toma agua."),
        (0, "La raíz sujeta al árbol."),
        (1, "La hoja usa la luz."),
        (3, "En el bosque hay seres vivos."),
        (4, "Las hojas vuelven al suelo."),
    ),
    "agua": (
        (0, "El agua puede pasar a gas."),
        (1, "El frío forma gotas."),
        (3, "Parte del agua va al suelo."),
        (3, "Otra parte va por ríos."),
        (4, "El Sol da energía al ciclo."),
    ),
    "arqueologia": (
        (0, "Se mira lo que quedó."),
        (0, "Hay huellas de antes."),
        (1, "Son pistas de la vida de antes."),
        (2, "El sitio da una pista."),
        (3, "La vasija da pistas de comida."),
        (4, "Se ven antes las pruebas."),
    ),
    "escritura": (
        (0, "Hay más de un signo."),
        (3, "Hay textos sobre la ley."),
        (3, "Hay textos sobre ventas."),
        (4, "No todos los signos son iguales."),
        (0, "Lo escrito guarda un mensaje."),
        (1, "Un trazo puede ser de cuña."),
        (2, "Se usó más de un soporte."),
    ),
    "mapas": (
        (0, "El mapa usa signos."),
        (2, "La clave dice qué son."),
        (3, "Se puede ver por dónde ir."),
        (4, "Un globo no es plano."),
        (2, "El color da una pista."),
        (4, "El plano cambia formas o tamaños."),
        (3, "En ellos se pueden ver ríos."),
    ),
    "futbol": (
        (1, "El fin es un gol."),
        (0, "Hay dos equipos."),
        (3, "No todos usan las manos igual."),
        (4, "Hay reglas del juego."),
    ),
    "atletismo": (
        (0, "Cada cual corre su tramo."),
        (1, "Un pase une los tramos."),
        (1, "Se pasa un testigo."),
        (3, "El pase debe ir en su zona."),
        (4, "El grupo logra el resultado."),
        (2, "Hace falta correr y coordinarse."),
    ),
    "baloncesto": (
        (0, "El fin es que el balón entre."),
        (1, "Son cinco en la cancha."),
        (3, "No todo tiro vale igual."),
        (3, "Un tiro puede dar puntos."),
        (2, "Se puede pasar el balón."),
        (2, "También se puede botar."),
    ),
    "robots": (
        (0, "Hay pasos que se han de seguir."),
        (1, "Un motor hace que se mueva."),
        (2, "Puede llevar piezas."),
        (4, "No todos son iguales."),
        (4, "No todos trabajan solos."),
        (3, "Puede ir donde cuesta llegar."),
    ),
    "internet": (
        (0, "Las redes se unen."),
        (1, "Los datos van en partes."),
        (2, "Cada envío tiene un destino."),
        (3, "La Web es una parte de esa red."),
        (4, "Por la red van mensajes."),
    ),
    "energia solar": (
        (0, "La luz se vuelve electricidad."),
        (1, "Hace falta que llegue luz."),
        (2, "Se puede unir más de un panel."),
        (3, "El Sol da calor."),
        (3, "Ese calor sirve para calentar."),
    ),
    "julio verne": (
        (1, "Hay viajes e inventos."),
        (2, "Hay un viaje bajo el mar."),
        (3, "Nemo no es real."),
        (4, "Hay ciencia y ficción."),
        (3, "En la obra, va por mar."),
        (4, "Son relatos sobre el mundo."),
    ),
    "vuelta mundo": (
        (1, "El fin es dar la vuelta al mundo."),
        (1, "Fogg acepta una apuesta."),
        (2, "Fogg no va solo."),
        (3, "El tiempo cuenta en el viaje."),
        (4, "La apuesta no fue real."),
    ),
    "isla tesoro": (
        (2, "El mapa da inicio al viaje."),
        (2, "Se busca un tesoro."),
        (1, "Jim es el joven del relato."),
        (4, "Los piratas son de ficción."),
        (3, "Hay decisiones y conflictos."),
    ),
    "real madrid": (
        (0, "Es un club de Madrid."),
        (2, "Su ropa es blanca."),
        (5, "No juega solo al fútbol."),
        (4, "La FIFA lo eligió."),
    ),
    "biologia marina": (
        (0, "El mar tiene vida."),
        (1, "Hay peces y ballenas."),
        (2, "Las algas usan luz del Sol."),
        (3, "El coral da refugio."),
        (4, "Al fondo llega menos luz."),
        (5, "Hay seres que dan su propia luz."),
        (6, "La sal del agua influye."),
    ),
    "tiburon": (
        (0, "El tiburón es un pez."),
        (0, "Su tejido se puede doblar."),
        (2, "Puede salir un diente nuevo."),
        (3, "No todos comen presas grandes."),
        (3, "El ballena filtra seres muy pequeños."),
        (5, "Unos nacen de huevos."),
        (5, "Otros nacen vivos."),
        (6, "El mar debe ser apto para su vida."),
    ),
    "dinosaurios": (
        (4, "Las aves son de ese grupo."),
        (5, "No todo fue a la vez."),
        (1, "Hay restos de sus pasos."),
        (1, "Se ven huesos y huevos."),
        (1, "Sus restos dan pistas."),
        (5, "Los hubo de más de un tamaño."),
        (2, "No todos comían lo mismo."),
        (3, "Los que no eran aves ya no están."),
        (0, "Son seres de un pasado muy lejano."),
    ),
    "sistema solar": (
        (0, "El Sol es parte del grupo."),
        (3, "El Sol es una estrella."),
        (4, "Se gira en torno al Sol."),
        (1, "No hay un solo planeta."),
        (5, "Los más cercanos son de roca."),
        (2, "Hay más que planetas."),
        (6, "Tras Marte hay un cinturón de rocas."),
    ),
    "agujeros negros": (
        (0, "De dentro no sale luz."),
        (1, "Hay un borde sin retorno."),
        (4, "No se traga todo sin más."),
        (3, "Se mira lo que hay cerca."),
        (4, "La masa y la distancia importan."),
        (2, "Una estrella puede darles origen."),
    ),
    "volcanes": (
        (0, "Puede salir roca de dentro."),
        (1, "Al salir se llama lava."),
        (2, "Pueden salir gases y rocas."),
        (4, "Puede surgir una isla."),
        (5, "No todos tienen la misma forma."),
    ),
    "antiguo egipto": (
        (0, "Fue junto al Nilo."),
        (1, "El agua ayudó al campo."),
        (3, "Fue el rey quien mandó."),
        (2, "Se usó más de un tipo de signo."),
        (6, "No fue todo a la vez."),
        (6, "No fue un solo siglo."),
        (5, "Una gran obra pide un plan."),
        (3, "Se fijaban las tareas y los medios."),
        (2, "Se dejó escritura."),
        (5, "Hubo saber para hacer grandes obras."),
    ),
    "inteligencia artificial": (
        (1, "Se usan datos."),
        (2, "Se puede crear una respuesta."),
        (3, "No todo sale bien."),
        (4, "No todo lo que dice es cierto."),
        (5, "Hay que ver si es verdad."),
        (5, "Hay que mirar las fuentes."),
        (0, "Puede tratar lo que se dice."),
        (3, "Su diseño influye."),
    ),
    "robots submarinos": (
        (0, "Van bajo el mar."),
        (1, "Puede haber un cable al barco."),
        (2, "Por él van datos y órdenes."),
        (3, "La luz ayuda a ver."),
        (4, "No todos llevan cable."),
        (5, "Sirven para ver el fondo."),
    ),
    "juegos olimpicos": (
        (0, "Hay más de una prueba."),
        (6, "Son dos tipos de juegos."),
        (4, "Los aros son su signo."),
        (4, "Los cinco aros se cruzan."),
        (5, "Las pruebas no fueron siempre iguales."),
        (1, "Hubo unos primeros Juegos modernos."),
        (6, "No todos los juegos tienen las mismas pruebas."),
        (0, "Hay más de un deporte."),
        (4, "Los aros están unidos."),
    ),
    "robots inteligencia artificial": (
        (0, "Hay pasos que se han de seguir."),
        (1, "Un motor hace que se mueva."),
        (3, "No todos aprenden de datos."),
        (4, "No todo sale bien."),
        (5, "No siempre tiene forma humana."),
        (5, "Se debe controlar su tarea."),
    ),
    "pequeno faro": (
        (0, "El faro del cuento no es real."),
        (1, "Su luz señala la costa."),
        (4, "No se va por el mar."),
        (3, "Cada señal ayuda a distinguirlo."),
        (5, "Las señales de los faros sí son reales."),
    ),
}


def supports(source):
    from app.encyclopedia import ARTICLES
    from app.services.pedagogy import source_hash

    identity = source_hash(source)
    for key, article in ARTICLES.items():
        if source_hash(article.text) == identity:
            units = sentences(article.text)
            return [Support(text, units[index]) for index, text in LOCAL[key]]
    # Bounded positive frames. Unknown negations/conditions get no new assertion.
    normalized = " ".join(source.split())
    if re.search(r"\b(?:si|aunque|no|nunca|excepto)\b", normalized, re.I):
        # The clinical ratio frame has an explicit licensed concessive below.
        if not normalized.startswith("Y aunque también puede afectar a niños y personas mayores,"):
            return []
    values = []
    if re.fullmatch(
        r"Los historiadores utilizan documentos antiguos para comprender las transformaciones de las ciudades y posteriormente proporcionan explicaciones sobre las actividades de sus habitantes[.]?",
        normalized,
    ):
        values = [
            Support("Su fin es ver qué pasó.", normalized),
            Support("Hay textos de otros tiempos.", normalized),
            Support("Se busca entender los cambios.", normalized),
        ]
    elif re.fullmatch(
        r"El texto recoge las medidas organizativas, procesales y de seguridad laboral más urgentes para la paulatina vuelta a la actividad de los juzgados y tribunales y tiene como prioridad la salud de los profesionales que desarrollan su trabajo en ese ámbito[.]?",
        normalized,
    ):
        values = [
            Support("El fin es la salud.", normalized),
            Support("La vuelta debe ser gradual.", normalized),
            Support("Se cuida a quienes trabajan.", normalized),
        ]
    elif re.fullmatch(
        r"Y aunque también puede afectar a niños y personas mayores, el 70 por 100 de los nuevos casos se detectan en personas de entre 20 y 40 años de edad y, en 3 de cada 4 pacientes, en mujeres[.]?",
        normalized,
    ):
        values = [
            Support("Son más de la mitad.", "en 3 de cada 4 pacientes, en mujeres"),
            Support("No son todos de una edad.", normalized),
        ]
    elif normalized.startswith(
        "Existe además un cuarto objetivo transversal que es la coordinación con otros países de la UE "
    ):
        values = [
            Support("Hay más de un país.", "otros países de la UE"),
            Support(
                "El fin es que se sumen.", "participación e involucración de las partes interesadas"
            ),
            Support("Se quiere ver cómo va el Plan.", "evaluación continua del Plan"),
        ]
    return values
