"""Scoped clause alignments for the two documented educational support frames.

These are explicit rules, not claims that an untrained language model can safely
rewrite arbitrary diagnoses. Every population, alternative and cause is retained.
"""

import re


def rewrite_frame(text, level):
    normalized = " ".join(text.split()).rstrip(".")
    attention = re.fullmatch(
        r"La proliferación contemporánea de estímulos audiovisuales fragmentados "
        r"obstaculiza considerablemente la consolidación de los procesos cognitivos "
        r"vinculados con la comprensión lectora sostenida en infantes diagnosticados "
        r"con sintomatología de inatención o dificultades fonológicas",
        normalized,
        re.I,
    )
    if attention:
        if level == 1:
            return (
                "Estos niños tienen un diagnóstico sobre sus síntomas. "
                "Puede indicar falta de atención o problemas con sonidos. "
                "Son los sonidos del habla. "
                "Hoy hay cada vez más imágenes y sonidos fragmentados. "
                "Es decir, llegan en pequeñas partes. "
                "Eso dificulta mucho afianzar procesos de la mente. "
                "La dificultad afecta a estos niños. "
                "Esos procesos sirven para entender lo que se lee. "
                "Se trata de entender la lectura de forma continua."
            )
        if level == 2:
            return (
                "Estos niños tienen un diagnóstico de síntomas de inatención o dificultades fonológicas. "
                "Son problemas de atención o con los sonidos del habla. "
                "Hoy aumentan las imágenes y sonidos fragmentados, que llegan en pequeñas partes. "
                "Ese aumento dificulta mucho que se afiancen procesos mentales en estos niños. "
                "Estos procesos permiten entender la lectura de forma continua."
            )
        if level == 3:
            return (
                "Los niños mencionados tienen un diagnóstico de síntomas de inatención o dificultades fonológicas. "
                "Son problemas de atención o con los sonidos del habla. "
                "El aumento actual de estímulos audiovisuales fragmentados dificulta mucho afianzar procesos cognitivos en estos niños. "
                "Los estímulos son imágenes y sonidos que llegan en partes. "
                "Estos procesos de la mente se vinculan con entender la lectura de forma continua."
            )
        if level == 4:
            return (
                "En niños con diagnóstico de síntomas de inatención o dificultades fonológicas, el aumento actual de estímulos audiovisuales fragmentados dificulta afianzar procesos cognitivos. "
                "Esos procesos se relacionan con la comprensión continua de la lectura."
            )
        return (
            "La proliferación actual de estímulos audiovisuales fragmentados dificulta mucho consolidar procesos cognitivos relacionados con la comprensión lectora sostenida. "
            "Este efecto se describe en niños diagnosticados con síntomas de inatención o dificultades fonológicas."
        )
    students = re.fullmatch(
        r"Los estudiantes que presentan dificultades adicionales durante las actividades escolares "
        r"necesitan subsecuentemente materiales pedagógicos accesibles\. Asimismo,? "
        r"la implementación de herramientas tecnológicas contemporáneas facilita considerablemente "
        r"la comprensión de los libros en la escuela",
        normalized,
        re.I,
    )
    if students:
        if level == 1:
            return (
                "Algunos alumnos tienen más problemas en las tareas de clase. "
                "Después necesitan cosas que les sirvan para aprender. "
                "Deben poder usar esas cosas. "
                "Además, hay herramientas de tecnología de hoy. "
                "Ponerlas en marcha ayuda mucho. "
                "Así cuesta menos entender los libros en la escuela."
            )
        if level == 2:
            return (
                "Los alumnos con más problemas en clase necesitan después materiales para aprender. "
                "Son materiales que estos alumnos puedan usar. "
                "Esas herramientas pueden ser aparatos o programas de hoy. "
                "Poner en marcha esas herramientas ayuda mucho. "
                "Así cuesta menos entender lo que dicen los libros."
            )
        if level == 3:
            return (
                "Los estudiantes con dificultades adicionales en las tareas escolares necesitan después materiales pedagógicos accesibles. "
                "Son materiales para aprender que estos estudiantes puedan usar. "
                "Además, poner en marcha herramientas tecnológicas actuales facilita mucho entender los libros en la escuela."
            )
        if level == 4:
            return (
                "Los estudiantes con dificultades adicionales en las tareas escolares necesitan después materiales pedagógicos accesibles. "
                "Además, poner en marcha herramientas tecnológicas actuales hace mucho más fácil comprender los libros en la escuela."
            )
        return (
            "Los estudiantes con dificultades adicionales durante las actividades escolares necesitan después materiales pedagógicos accesibles. "
            "Asimismo, la implementación de herramientas tecnológicas actuales facilita mucho la comprensión de los libros en la escuela."
        )
    return None


def question_rows(source):
    """Reviewed facts only for the exact two previously documented inputs."""
    if rewrite_frame(source, 1) is None:
        return []
    if "obstaculiza" in source.casefold():
        return [
            (
                [],
                [
                    "niños|infantes",
                    "diagnóstico|diagnosticados",
                    "atención|inatención",
                    "fonológicas|sonidos",
                ],
                "¿Qué dificultades se mencionan en estos niños?",
                (
                    "Problemas de atención o con los sonidos del habla",
                    "Problemas para ver colores o reconocer formas",
                    "Problemas para mover brazos o mantener el equilibrio",
                    "Problemas para recordar rutas o calcular distancias",
                ),
                "fact",
            ),
            (
                [],
                [
                    "aumento|proliferación|cada vez más",
                    "imágenes|estímulos",
                    "sonidos|audiovisuales",
                    "dificulta|obstaculiza",
                ],
                "¿Qué hace más difícil comprender la lectura según el texto?",
                (
                    "El aumento de imágenes y sonidos fragmentados",
                    "La falta de libros en todas las escuelas",
                    "El cambio de los horarios de clase",
                    "El tamaño de las páginas de los libros",
                ),
                "cause",
            ),
            (
                [],
                ["lectura|leer|lee|lectora", "continua|continuo|sostenida"],
                "¿Qué significa leer de forma continua en esta lectura?",
                (
                    "Entender lo leído sin perder el hilo",
                    "Leer solo palabras sueltas sin relacionarlas",
                    "Mirar las páginas sin entender sus ideas",
                    "Repetir sonidos sin seguir el sentido del texto",
                ),
                "concept",
            ),
        ]
    return [
        (
            [],
            ["alumnos|estudiantes", "necesitan", "materiales|cosas"],
            "¿Qué necesitan los alumnos con más dificultades?",
            (
                "Materiales para aprender que puedan usar",
                "Materiales preparados solo para alumnos muy avanzados",
                "Materiales con instrucciones que no puedan comprender",
                "Materiales sin relación con las tareas escolares",
            ),
            "fact",
        ),
        (
            [],
            ["herramientas", "ayuda|facilita|fácil", "libros"],
            "¿Para qué ayudan las herramientas tecnológicas según el texto?",
            (
                "Para entender mejor los libros de la escuela",
                "Para memorizar solamente los títulos de los libros",
                "Para sustituir la lectura por la copia de dibujos",
                "Para practicar únicamente el cálculo sin leer libros",
            ),
            "purpose",
        ),
        (
            [],
            ["materiales|cosas", "usar|accesibles"],
            "¿Qué significa que un material sea accesible?",
            (
                "Que el alumno pueda utilizarlo para aprender",
                "Que el material tenga muchas páginas y palabras difíciles",
                "Que el material se reserve solo para los profesores",
                "Que el material esté escrito sin instrucciones claras",
            ),
            "concept",
        ),
    ]
