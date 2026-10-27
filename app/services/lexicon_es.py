"""Independently authored, agreement-preserving Spanish lexical simplifications.

Levels 1..3 prefer shorter forms; technical concepts with ambiguous meanings are
expressed as phrases, not blindly substituted with unrelated corpus synonyms.
"""

# Each line is source | accessible equivalent. Inflections are explicit.
PAIRS = """
con la finalidad de|para
con el objetivo de|para
a través de la utilización de|usando
por medio de la utilización de|usando
se encuentra ubicado en|está en
se encuentra ubicada en|está en
se encuentran ubicados en|están en
se encuentran ubicadas en|están en
cuya función consiste en|que sirve para
se caracteriza por poseer|tiene
se caracterizan por poseer|tienen
en el momento en que|cuando
en la actualidad|hoy
con posterioridad|después
con anterioridad|antes
a consecuencia de|por
como consecuencia de|por
por consiguiente|por eso
por esta razón|por eso
a pesar de que|aunque
sin embargo|pero
debido a que|porque
con respecto a|sobre
en relación con|sobre
en lo que respecta a|sobre
con la excepción de|salvo
exceptuando a|salvo a
únicamente|solo
solamente|solo
posteriormente|después
previamente|antes
inicialmente|primero
finalmente|al final
actualmente|hoy
asimismo|además
adicionalmente|además
contemporáneo|actual
contemporánea|actual
contemporáneos|actuales
contemporáneas|actuales
frecuentemente|a menudo
habitualmente|a menudo
ocasionalmente|a veces
simultáneamente|a la vez
paulatinamente|poco a poco
progresivamente|poco a poco
inmediatamente|de inmediato
aproximadamente|cerca de
considerablemente|mucho
significativamente|de forma clara
principalmente|sobre todo
fundamentalmente|sobre todo
especialmente|en especial
particularmente|en especial
específicamente|en concreto
generalmente|por lo general
regularmente|de forma regular
necesariamente|por fuerza
probablemente|tal vez
posiblemente|quizá
incluso en el caso de que|aun si
siempre y cuando|si
si y solo si|si y solo si
utilizar|usar
utiliza|usa
utilizan|usan
utilizamos|usamos
utilizando|usando
utilizaba|usaba
utilizaban|usaban
utilizó|usó
utilizaron|usaron
utilizará|usará
utilizarán|usarán
utilizado|usado
utilizada|usada
utilizados|usados
utilizadas|usadas
realizar|hacer
realiza|hace
realizan|hacen
realizamos|hacemos
realizando|haciendo
realizaba|hacía
realizaban|hacían
realizó|hizo
realizaron|hicieron
realizado|hecho
realizada|hecha
realizados|hechos
realizadas|hechas
efectuar|hacer
efectúa|hace
efectúan|hacen
efectuó|hizo
efectuaron|hicieron
efectuando|haciendo
iniciar|empezar
inicia|empieza
inician|empiezan
inició|empezó
iniciaron|empezaron
finalizar|acabar
finaliza|acaba
finalizan|acaban
finalizó|acabó
finalizaron|acabaron
concluir|acabar
concluye|acaba
concluyen|acaban
comprender|entender
comprende|entiende
comprenden|entienden
comprendió|entendió
comprendieron|entendieron
comprendiendo|entendiendo
proporcionar|dar
proporciona|da
proporcionan|dan
proporcionaba|daba
proporcionaban|daban
proporcionó|dio
proporcionaron|dieron
proporcionando|dando
otorgar|dar
otorga|da
otorgan|dan
otorgó|dio
otorgaron|dieron
poseer|tener
posee|tiene
poseen|tienen
poseía|tenía
poseían|tenían
poseyó|tuvo
poseían|tenían
numeroso|mucho
numerosa|mucha
numerosos|muchos
numerosas|muchas
diversos|varios
diversas|varias
múltiples|varios
fundamental|clave
fundamentales|claves
imprescindible|necesario
imprescindibles|necesarios
indispensable|necesario
indispensables|necesarios
beneficioso|bueno
beneficiosa|buena
beneficiosos|buenos
beneficiosas|buenas
perjudicial|dañino
perjudiciales|dañinos
adverso|malo
adversa|mala
complejo|difícil
compleja|difícil
complejos|difíciles
complejas|difíciles
sencillo|simple
sencilla|simple
sencillos|simples
sencillas|simples
incrementar|aumentar
incrementa|aumenta
incrementan|aumentan
incrementó|aumentó
incrementaron|aumentaron
disminuir|bajar
disminuye|baja
disminuyen|bajan
disminuyó|bajó
disminuyeron|bajaron
reducir el tamaño|hacer más pequeño
ampliar|agrandar
amplía|agranda
amplían|agrandan
obstaculizar|dificultar
obstaculiza|dificulta
obstaculizan|dificultan
impedir|no dejar
impide|no deja
impiden|no dejan
facilitar|hacer más fácil
facilita|hace más fácil
facilitan|hacen más fácil
permitir|dejar
permite|deja
permiten|dejan
requerir|necesitar
requiere|necesita
requieren|necesitan
precisar de|necesitar
carece de|no tiene
carecen de|no tienen
permanecer|seguir
permanece en|sigue en
permanecen en|siguen en
retornar|volver
retorna|vuelve
retornan|vuelven
regresar|volver
regresa|vuelve
regresan|vuelven
adquirir|conseguir
adquiere|consigue
adquieren|consiguen
obtener|lograr
obtiene|logra
obtienen|logran
obtuvo|logró
obtuvieron|lograron
hallar|encontrar
halla|encuentra
hallan|encuentran
halló|encontró
hallaron|encontraron
localizar|encontrar
localiza|encuentra
localizan|encuentran
ubicar|situar
ubicado|situado
ubicada|situada
ubicados|situados
ubicadas|situadas
residir|vivir
reside|vive
residen|viven
habitar|vivir en
habita en|vive en
habitan en|viven en
habitan los|viven en los
habitan las|viven en las
habitan el|viven en el
habitan la|viven en la
habitan mares|viven en mares
habitan océanos|viven en océanos
fallecer|morir
fallece|muere
fallecen|mueren
falleció|murió
fallecieron|murieron
construir|crear
construye|crea
construyen|crean
elaborar|crear
elabora|crea
elaboran|crean
elaboró|creó
elaboraron|crearon
denominado|llamado
denominada|llamada
denominados|llamados
denominadas|llamadas
denominación|nombre
recibe la denominación de|se llama
reciben la denominación de|se llaman
se denomina|se llama
se denominan|se llaman
constituye una|es una
constituye un|es un
constituyen una|son una
constituyen un|son un
es considerado como|se considera
es considerada como|se considera
son considerados como|se consideran
son consideradas como|se consideran
individuo|persona
individuos|personas
pobladores|habitantes
poblador|habitante
progenitores|padres
infantes|niños
infante|niño
alumnado|grupo de alumnos
docente|profesor
docentes|profesores
educando|alumno
educandos|alumnos
enseñanza|educación
pedagógico|educativo
pedagógica|educativa
pedagógicos|educativos
pedagógicas|educativas
cognitivo|mental
cognitiva|mental
cognitivos|mentales
cognitivas|mentales
comprensión|entendimiento
consolidar|afianzar
consolida|afianza
consolidan|afianzan
inconveniente|problema
inconvenientes|problemas
obstáculo|barrera
obstáculos|barreras
propósito|fin
propósitos|fines
objetivo|fin
objetivos|fines
metodología|método
metodologías|métodos
procedimiento|proceso
procedimientos|procesos
característica|rasgo
características|rasgos
particularidad|rasgo
particularidades|rasgos
magnitud|tamaño
magnitudes|tamaños
dimensión|tamaño
dimensiones|tamaños
ubicación|lugar
localización|lugar
emplazamiento|lugar
proximidad|cercanía
adyacente|cercano
adyacentes|cercanos
colindante|vecino
colindantes|vecinos
extenso|grande
extensa|grande
extensos|grandes
extensas|grandes
reducido|pequeño
reducida|pequeña
reducidos|pequeños
reducidas|pequeñas
diminuto|muy pequeño
diminuta|muy pequeña
diminutos|muy pequeños
diminutas|muy pequeñas
inmenso|muy grande
inmensa|muy grande
inmensos|muy grandes
inmensas|muy grandes
veloz|rápido
veloces|rápidos
lentamente|despacio
celeridad|rapidez
rapidez|velocidad
trayecto|camino
trayectos|caminos
recorrido|camino
recorridos|caminos
transitar|pasar
transita|pasa
transitan|pasan
desplazarse|moverse
se desplaza|se mueve
se desplazan|se mueven
superficie terrestre|suelo de la Tierra
subsuelo|suelo bajo tierra
subterráneo|bajo tierra
subterránea|bajo tierra
submarino|bajo el mar
submarina|bajo el mar
acuático|del agua
acuática|del agua
acuáticos|del agua
acuáticas|del agua
marítimo|del mar
marítima|del mar
marítimos|del mar
marítimas|del mar
terrestre|de la Tierra
terrestres|de la Tierra
celeste|del cielo
celestes|del cielo
luminoso|con luz
luminosa|con luz
luminosos|con luz
luminosas|con luz
esférico|redondo
esférica|redonda
esféricos|redondos
esféricas|redondas
esqueleto|grupo de huesos
alimentación|forma de comer
alimento|comida
alimentos|comida
nutrición|forma de alimentarse
nutrientes|sustancias que dan alimento
organismos|seres vivos
organismo|ser vivo
fauna|conjunto de animales
flora|conjunto de plantas
fotosíntesis|proceso que usa luz para crear alimento
bioluminiscencia|capacidad de crear luz propia
invertebrados|animales sin columna vertebral
mamíferos|animales que dan leche a sus crías
ovíparos|animales que nacen de huevos
herbívoros|animales que comen plantas
carnívoros|animales que comen carne
omnívoros|animales que comen plantas y carne
caducifolio|que pierde sus hojas cada año
perenne|que dura varios años
sedimento|material que se deposita en el fondo
sedimentos|materiales que se depositan en el fondo
erupción volcánica|salida de materiales de un volcán
tectónica de placas|movimiento de grandes partes de la corteza
precipitación|agua que cae como lluvia o nieve
condensación|cambio del vapor a agua líquida
estado gaseoso|estado de gas
estado líquido|estado de agua líquida
satélite natural|cuerpo que gira alrededor de otro
rotación|giro sobre su propio eje
órbita|camino alrededor de otro cuerpo
órbitas|caminos alrededor de otros cuerpos
astronomía|ciencia que estudia el espacio
gravitatoria|de la gravedad
gravitatorio|de la gravedad
gravitatorias|de la gravedad
gravitatorios|de la gravedad
computadora|ordenador
computadoras|ordenadores
computacional|informático
computacionales|informáticos
recopilar datos|reunir datos
procesar datos|trabajar con datos
almacenar|guardar
almacena|guarda
almacenan|guardan
almacenamiento|guardado
transmitir|enviar
transmite|envía
transmiten|envían
transmisión|envío
dispositivo|aparato
dispositivos|aparatos
mecanismo|sistema
mecanismos|sistemas
automatizado|que funciona de forma automática
automatizada|que funciona de forma automática
innovación|nueva idea
innovaciones|nuevas ideas
artilugio|aparato
artilugios|aparatos
legislación|conjunto de leyes
monarca|rey
monarcas|reyes
soberano|rey
soberanos|reyes
soberana|reina
soberanas|reinas
edificación|construcción
edificaciones|construcciones
vestigio|resto del pasado
vestigios|restos del pasado
civilización|sociedad organizada
civilizaciones|sociedades organizadas
ancestral|muy antiguo
ancestrales|muy antiguos
prehistórico|anterior a la escritura
prehistórica|anterior a la escritura
indumentaria|ropa
atuendo|ropa
contienda deportiva|partido
recinto deportivo|estadio
balompié|fútbol
esférico de juego|balón
plantel deportivo|equipo
guardameta|portero
afiliados|socios
afiliado|socio
competición deportiva|prueba deportiva
competición|prueba
competiciones|pruebas
contrincante|rival
contrincantes|rivales
triunfo|victoria
triunfos|victorias
adversario|rival
adversarios|rivales
entrenamiento físico|práctica de ejercicio
entrenamiento deportivo|práctica de deporte
preparación física|forma física
sede deportiva|lugar del club
sección de baloncesto|equipo de baloncesto
"""

CURATED = {line.split("|", 1)[0]: line.split("|", 1)[1] for line in PAIRS.strip().splitlines()}

# These forms need a parser/sense decision, so retain them as technical terms.
# In particular sharks do not have bony skeletons, and 'líquido' is not always water.
for ambiguous in (
    "individuo",
    "individuos",
    "enseñanza",
    "comprensión",
    "objetivo",
    "objetivos",
    "magnitud",
    "magnitudes",
    "dimensión",
    "dimensiones",
    "reducido",
    "reducida",
    "reducidos",
    "reducidas",
    "esqueleto",
    "estado líquido",
    "terrestre",
    "terrestres",
    "celeste",
    "celestes",
    "monarca",
    "monarcas",
    "esférico",
    "esférica",
    "esféricos",
    "esféricas",
    "permanecer",
    "rápidez",
    "esférico de juego",
    "construir",
    "construye",
    "construyen",
    "esqueleto",
    "submarino",
    "submarina",
):
    CURATED.pop(ambiguous, None)

# Definition fragments and polysemous words cannot be dropped into arbitrary
# grammar. Their meanings are taught by the aligned bank/glossary instead.
for context_dependent in (
    "fauna",
    "flora",
    "fotosíntesis",
    "rotación",
    "órbita",
    "órbitas",
    "precipitación",
    "condensación",
    "satélite natural",
    "nutrición",
    "nutrientes",
    "superficie terrestre",
    "residir",
    "reside",
    "residen",
    "habitar",
    "habitan los",
    "habitan las",
    "habitan el",
    "habitan la",
    "habitan mares",
    "habitan océanos",
    "inmenso",
    "inmensa",
    "inmensos",
    "inmensas",
    "diminuto",
    "diminuta",
    "diminutos",
    "diminutas",
    "subterráneo",
    "subterránea",
    "caducifolio",
    "perenne",
    "adverso",
    "adversa",
):
    CURATED.pop(context_dependent, None)

CURATED.update({"realizar actividades": "hacer tareas", "realizan actividades": "hacen tareas"})

for needs_sense_or_modifier_analysis in (
    "mamíferos",
    "ovíparos",
    "herbívoros",
    "carnívoros",
    "omnívoros",
    "sedimento",
    "sedimentos",
    "astronomía",
    "organismo",
    "organismos",
    "legislación",
    "soberano",
    "soberanos",
    "soberana",
    "soberanas",
    "sede deportiva",
):
    CURATED.pop(needs_sense_or_modifier_analysis, None)
