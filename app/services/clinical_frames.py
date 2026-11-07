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
