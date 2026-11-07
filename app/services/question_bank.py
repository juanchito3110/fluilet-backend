"""Reviewed subject-specific questions; ¦ separates fields, ~ required anchors.

All answers are checked against evidence in the actual shortened reading. These
are teaching annotations, never hidden model-training or evaluation examples.
"""

ROWS = """
milo¦vera~huerto~agua¦¿Qué necesita el huerto de Vera en el cuento?¦El agua que le falta¦El hielo que le falta¦El metal que le falta¦El humo que le falta¦fact
milo¦pozo~cubos¦¿De dónde saca Vera el agua para regar?¦Del pozo usando unos cubos¦Del mar usando unas redes¦De las nubes usando unas velas¦De una cueva usando unas cajas¦place
milo¦paja~menos~agua¦¿Para qué colocan paja sobre la tierra húmeda?¦Para reducir la pérdida de agua¦Para impedir que crezcan las raíces¦Para evitar que llegue cualquier luz¦Para hacer que el suelo pierda agua¦purpose
capitana ada¦cofre~campana~bronce¦¿Qué encuentra la capitana Ada dentro del cofre?¦Una campana hecha de bronce¦Una corona hecha de plata¦Una moneda hecha de oro¦Una pulsera hecha de hierro¦fact
capitana ada¦campana~avisaba|avisar~barcos¦¿Para qué servía la campana del puerto?¦Para avisar de la llegada de barcos¦Para señalar la profundidad del fondo¦Para medir la fuerza de las olas¦Para marcar la edad de los barcos¦purpose
capitana ada¦devolver~pueblo¦¿Qué decide hacer Ada con la campana?¦Devolverla al pueblo al que pertenecía¦Venderla en un mercado de otra isla¦Esconderla bajo la arena de la playa¦Fundirla para fabricar monedas de bronce¦inference
iris¦kiro~robot¦¿Con quién cuida Iris el huerto de la nave?¦Con un robot llamado Kiro¦Con un zorro llamado Bruno¦Con un dragón llamado Milo¦Con un marinero llamado Teo¦fact
iris¦cable~suelto¦¿Qué fallo encuentra Kiro en el panel del huerto?¦Un cable que estaba suelto¦Una ventana que estaba rota¦Una rueda que estaba pinchada¦Un tubo que estaba congelado¦cause
iris¦causa~fallo|problema¦¿Qué aprende el equipo de Iris al reparar la luz?¦A buscar la causa antes de cambiar piezas¦A cambiar todas las piezas sin comprobar nada¦A apagar siempre las luces de las plantas¦A ignorar los pasos de seguridad de la nave¦inference
tierra¦tierra~sol~gira|vuelta¦¿Alrededor de qué estrella gira la Tierra?¦Alrededor de la estrella llamada Sol¦Alrededor de la estrella llamada Sirio¦Alrededor de la estrella llamada Vega¦Alrededor de la estrella llamada Rigel¦fact
tierra¦giro|rotacion~dia~noche¦¿Qué produce el día y la noche en la Tierra?¦El giro sobre su propio eje¦El paso de cometas lejanos¦El cambio de color del océano¦El crecimiento de las montañas¦cause
tierra¦plantas~luz~alimento|comida¦¿Para qué aprovechan las plantas la luz del Sol?¦Para crear el alimento que necesitan¦Para cambiar todas sus hojas por piedras¦Para producir arena en sus raíces¦Para dejar de necesitar agua¦purpose
telescopio¦lentes~espejos¦¿Qué pueden utilizar los telescopios para recoger luz?¦Unas lentes o unos espejos¦Unas brújulas o unos relojes¦Unas balanzas o unos termómetros¦Unas palas o unos rastrillos¦fact
telescopio¦lejos|lejanos~luz¦¿Para qué recoge luz un telescopio?¦Para observar objetos que están lejos¦Para medir el peso de los objetos¦Para escuchar sonidos bajo el agua¦Para calentar alimentos sin fuego¦purpose
telescopio¦no~crea~luz¦¿Qué aclara la lectura sobre la luz del telescopio?¦Recoge luz que ya existe¦Crea la luz de las estrellas¦Crea la luz del Sol¦Produce la luz de la Luna¦concept
abejas¦flores~nectar~polen¦¿Qué buscan las abejas en las flores?¦El néctar y el polen¦El musgo y la corteza¦La arena y las piedras¦El barro y las ramas¦fact
abejas¦polen~plantas~reproduc|crias¦¿Por qué es importante el transporte de polen?¦Porque ayuda a reproducirse a muchas plantas¦Porque impide crecer a todas las raíces¦Porque convierte las flores en rocas¦Porque hace desaparecer las semillas¦cause
abejas¦danza~comida|alimento¦¿Qué comunica la danza de algunas abejas obreras?¦La dirección donde pueden encontrar comida¦La altura que tiene cada árbol¦La edad que tiene cada flor¦La cantidad de lluvia del año¦concept
bosque¦raices~agua~suelo¦¿Qué absorben las raíces del árbol?¦El agua que hay en el suelo¦El aire que hay en las nubes¦La luz que hay en las estrellas¦El fuego que hay en el volcán¦fact
bosque¦hojas~luz~alimento¦¿Para qué usan luz las hojas de los árboles?¦Para producir su propio alimento¦Para convertir el tronco en hierro¦Para hacer desaparecer sus raíces¦Para cambiar las piedras por lluvia¦purpose
bosque¦hojas~suelo~deshacen|descomposicion¦¿Qué ocurre cuando las hojas caídas se descomponen?¦Devuelven nutrientes al suelo del bosque¦Transforman todo el suelo en hielo¦Impiden que nazca cualquier planta¦Eliminan el agua de todos los ríos¦inference
agua¦liquido~gas|gaseoso¦¿Qué cambio recibe el nombre de evaporación?¦El paso de agua líquida a gas¦El paso de gas a hielo sólido¦El paso de roca a metal líquido¦El paso de arena a roca dura¦vocabulary
agua¦vapor~enfri|frio~gotas¦¿Qué puede formar el vapor de agua al enfriarse?¦Gotas de agua o cristales de hielo¦Granos de arena o piedras de río¦Hojas de árbol o flores del jardín¦Trozos de metal o vidrio de ventana¦cause
agua¦sol~gravedad|fuerza¦¿Qué impulsa procesos del ciclo del agua?¦La energía solar y la gravedad¦La luz lunar y el ruido¦El color del cielo y las estrellas¦El tamaño de los peces del mar¦concept
arqueologia¦restos~pasado|antes¦¿Qué utiliza la arqueología para estudiar el pasado?¦Los restos materiales que dejó la gente¦Los deseos de personajes de cuentos¦Las predicciones sobre ciudades del futuro¦Los colores de planetas muy lejanos¦fact
arqueologia¦lugar|posicion~hallazgo|excavar¦¿Por qué se anota dónde aparece un hallazgo?¦Porque su lugar ayuda a interpretarlo¦Porque su lugar cambia su antigüedad¦Porque su lugar permite fabricar oro¦Porque su lugar borra todas las huellas¦cause
arqueologia¦pruebas|evidencias~antes¦¿Qué hace la arqueología antes de proponer una explicación?¦Compara las pruebas que ha encontrado¦Inventa hechos sin buscar ninguna prueba¦Mezcla todos los objetos sin registrar nada¦Elige una respuesta por su sonido¦inference
escritura¦mesopotamia~arcilla¦¿Sobre qué se marcaban signos cuneiformes en Mesopotamia?¦Sobre unas tablillas de arcilla¦Sobre unas láminas de hielo¦Sobre unas hojas de metal¦Sobre unas paredes de vidrio¦fact
escritura¦signos~mensajes¦¿Para qué sirve la escritura según la lectura?¦Para conservar mensajes mediante signos¦Para medir distancias entre las estrellas¦Para mover piedras sin tocarlas¦Para cambiar el clima de un lugar¦purpose
escritura¦sonidos~signos¦¿Qué explica el texto sobre los sistemas de escritura?¦Sus signos pueden representar sonidos¦Sus signos siempre son números romanos¦Sus signos solo representan animales¦Sus signos siempre tienen idéntica forma¦concept
mapa¦escala~distancias¦¿Qué relaciona la escala de un mapa?¦Las distancias del mapa y del terreno¦Los colores del cielo y del agua¦Las edades de personas y animales¦Los pesos de piedras y metales¦concept
mapa¦leyenda~colores~senales¦¿Para qué sirve la leyenda de un mapa?¦Para explicar los colores y las señales¦Para indicar la edad del dibujante¦Para medir el peso del papel¦Para contar las estrellas del cielo¦purpose
mapa¦globo~esfera¦¿Qué forma utiliza un globo para representar la Tierra?¦La forma de una esfera¦La forma de un cubo¦La forma de un cono¦La forma de un cilindro¦fact
relevo¦testigo~zona¦¿Dónde deben pasarse el testigo los corredores de relevos?¦Dentro de la zona que está señalada¦Fuera de la pista de la carrera¦Dentro de la grada del público¦Fuera del estadio de la prueba¦place
relevo¦fuera~zona~eliminar|descalificacion¦¿Por qué puede quedar eliminado un equipo de relevos?¦Por entregar el testigo fuera de zona¦Por correr dentro de su propio carril¦Por recibir el testigo en la zona¦Por terminar todos los tramos previstos¦cause
relevo¦equipo~resultado|reparte¦¿Qué destaca la lectura sobre los relevos?¦El resultado depende del trabajo del equipo¦El resultado depende solo del primer corredor¦El resultado depende del color del testigo¦El resultado depende solo de las gradas¦inference
beisbol¦nueve~jugadores¦¿Cuántos jugadores tiene en el campo el equipo defensor?¦Un total de nueve jugadores¦Un total de once jugadores¦Un total de cinco jugadores¦Un total de siete jugadores¦quantity
beisbol¦tres~eliminaciones¦¿Cuántas eliminaciones provocan el cambio de turno en béisbol?¦Un total de tres eliminaciones¦Un total de cinco eliminaciones¦Un total de siete eliminaciones¦Un total de nueve eliminaciones¦quantity
beisbol¦bate~pelota¦¿Qué utiliza el bateador para golpear la pelota?¦Un bate para dar a la pelota¦Una raqueta para dar a la pelota¦Un palo de golf para la pelota¦Una mano sin guante para la pelota¦fact
baloncesto¦cinco~jugadores¦¿Cuántos jugadores tiene cada equipo de baloncesto en la cancha?¦Un total de cinco jugadores¦Un total de once jugadores¦Un total de nueve jugadores¦Un total de siete jugadores¦quantity
baloncesto¦1891¦¿En qué año creó James Naismith el baloncesto?¦En el año 1891¦En el año 1902¦En el año 1924¦En el año 1947¦year
baloncesto¦canasta|cesta~balon¦¿Cuál es el objetivo del baloncesto?¦Meter el balón en la canasta rival¦Meter el balón en la portería rival¦Golpear la pelota con un bate¦Pasar el testigo al siguiente corredor¦purpose
internet¦redes~datos¦¿Qué conecta Internet para intercambiar datos?¦Redes de ordenadores entre sí¦Tuberías de agua entre ciudades¦Vías de tren entre estaciones¦Cables de ascensor entre plantas¦concept
internet¦paquetes~partes|divid¦¿Por qué habla el texto de paquetes de datos?¦Porque la información puede viajar en partes¦Porque la información viaja siempre en papel¦Porque la información se lleva en camiones¦Porque la información no necesita destino¦cause
internet¦web~servicio|parte¦¿Qué relación tiene la Web con Internet?¦La Web es un servicio de Internet¦La Web es un planeta de Internet¦La Web es un motor de Internet¦La Web es un cable de Internet¦inference
panel|solares¦luz~electricidad|corriente¦¿Qué transforma en electricidad un panel fotovoltaico?¦La luz que recibe del Sol¦El sonido que llega del viento¦La arena que sale del suelo¦El hielo que cae de las nubes¦fact
panel|solares¦calor~calentar¦¿Para qué usan calor los paneles solares térmicos?¦Para calentar un fluido del sistema¦Para emitir sonidos por el aire¦Para medir el peso de las piezas¦Para reflejar imágenes de las estrellas¦purpose
panel|solares¦luz~depende¦¿De qué depende la energía obtenida por los paneles?¦De la luz recibida y del sistema¦Del nombre elegido para cada panel¦Del color de los barcos del puerto¦Del número de estrellas que vemos¦inference
verne¦1828¦¿En qué año nació Julio Verne?¦En el año 1828¦En el año 1873¦En el año 1883¦En el año 1902¦year
verne¦nemo~nautilus¦¿Qué dirige el capitán Nemo en la novela?¦Un submarino ficticio llamado Nautilus¦Un tren ficticio llamado Nautilus¦Un globo ficticio llamado Nautilus¦Un carruaje ficticio llamado Nautilus¦fact
verne¦ciencia~imaginacion|ficcion¦¿Qué mezclan muchos relatos de Julio Verne?¦Conocimientos científicos y aventuras de ficción¦Instrucciones de cocina y reglas de fútbol¦Listas de compras y horarios escolares¦Informes del clima y recetas de pintura¦inference
fogg¦1873¦¿Cuándo se publicó La vuelta al mundo en ochenta días?¦En el año 1873¦En el año 1828¦En el año 1883¦En el año 1902¦year
fogg¦apuesta~planeta|mundo¦¿Qué intenta lograr Phileas Fogg con su apuesta?¦Dar la vuelta al planeta¦Llegar al centro de la Tierra¦Encontrar un tesoro bajo el mar¦Construir un barco con un mapa¦purpose
fogg¦passepartout¦¿Quién acompaña a Phileas Fogg durante el viaje?¦Su compañero llamado Passepartout¦Su compañero llamado capitán Nemo¦Su compañero llamado Long John Silver¦Su compañero llamado Jim Hawkins¦fact
isla del tesoro¦1883¦¿En qué año se publicó como libro La isla del tesoro?¦En el año 1883¦En el año 1873¦En el año 1828¦En el año 1902¦year
isla del tesoro¦jim hawkins¦¿Quién es el joven protagonista de La isla del tesoro?¦Un joven llamado Jim Hawkins¦Un joven llamado Phileas Fogg¦Un joven llamado capitán Nemo¦Un joven llamado Passepartout¦fact
isla del tesoro¦mapa~viaje|expedicion¦¿Qué da inicio a la búsqueda del tesoro en la novela?¦Un mapa que inicia la expedición¦Una brújula que aparece sin mapa¦Un reloj que marca la llegada¦Una carta que prohíbe cualquier viaje¦cause
tiburon¦cartilago¦¿De qué está formado principalmente el esqueleto del tiburón?¦De un tejido llamado cartílago¦De un tejido llamado esmalte¦De un material llamado granito¦De un material llamado cuarzo¦fact
tiburon¦branquias~agua¦¿Para qué usan branquias los tiburones?¦Para obtener oxígeno del agua¦Para fabricar luz en el agua¦Para calentar las rocas del fondo¦Para absorber sal de la arena¦purpose
tiburon¦ballena~filtra¦¿Cómo se alimenta el tiburón ballena según el texto?¦Filtra seres vivos muy pequeños¦Caza siempre peces de gran tamaño¦Come solamente hojas de árboles¦Raspa rocas para obtener arena¦concept
dinosaurio¦230¦¿Hace cuánto surgió el grupo de los dinosaurios?¦Hace más de 230 millones de años¦Hace más de 23 millones de años¦Hace más de 2 millones de años¦Hace más de 2300 millones de años¦quantity
dinosaurio¦66¦¿Hace cuánto desaparecieron los dinosaurios no avianos?¦Hace unos 66 millones de años¦Hace unos 6 millones de años¦Hace unos 16 millones de años¦Hace unos 660 millones de años¦quantity
dinosaurio¦aves~dinosaurios¦¿Qué animales actuales pertenecen al grupo de los dinosaurios?¦Las aves que viven hoy¦Los tiburones que viven hoy¦Las ballenas que viven hoy¦Las abejas que viven hoy¦inference
sistema solar¦ocho~planetas¦¿Cuántos planetas tiene el sistema solar?¦Un total de ocho planetas¦Un total de seis planetas¦Un total de diez planetas¦Un total de doce planetas¦quantity
sistema solar¦sol~estrella¦¿Qué clase de astro es el Sol?¦Una estrella del sistema solar¦Un planeta del sistema solar¦Un cometa del sistema solar¦Un satélite del sistema solar¦concept
sistema solar¦planetas~sol~vuelta|orbita¦¿Qué recorrido realizan los planetas del sistema solar?¦Dan vueltas alrededor del Sol¦Dan vueltas alrededor de la Tierra¦Dan vueltas alrededor de la Luna¦Dan vueltas alrededor de Marte¦fact
volcan¦magma~dentro¦¿Cómo se llama la roca fundida dentro de la Tierra?¦Recibe el nombre de magma¦Recibe el nombre de ceniza¦Recibe el nombre de granito¦Recibe el nombre de hielo¦vocabulary
volcan¦lava~superficie|fuera¦¿Cuándo recibe el nombre de lava la roca fundida?¦Cuando llega a la superficie¦Cuando se enfría bajo un glaciar¦Cuando se convierte en vapor¦Cuando entra en el océano helada¦cause
volcan¦erupcion~islas~montanas¦¿Qué pueden crear algunas erupciones volcánicas?¦Islas y montañas nuevas¦Estrellas y planetas nuevos¦Ríos de hielo permanente¦Nubes de oxígeno puro¦inference
rov¦cable~barco¦¿Qué puede unir un ROV a un barco?¦Un cable para transmitir datos¦Una vía de tren submarina¦Un puente de piedra flotante¦Una red de pesca cerrada¦fact
rov¦cable~ordenes¦¿Para qué sirve el cable del ROV?¦Para enviar información y órdenes¦Para convertir el agua en combustible¦Para fabricar aire bajo el mar¦Para crear rocas en el fondo¦purpose
rov¦fondo~estudi|ver¦¿Qué permiten estudiar los robots submarinos?¦El fondo marino y sus animales¦La superficie del Sol y sus manchas¦Las nubes y sus cristales de hielo¦Los glaciares y sus cumbres de nieve¦concept
olimpicos¦1896~atenas¦¿Dónde se celebraron los primeros Juegos de verano modernos?¦En la ciudad de Atenas¦En la ciudad de Roma¦En la ciudad de París¦En la ciudad de Londres¦place
olimpicos¦1924~chamonix¦¿Cuándo comenzaron los Juegos Olímpicos de invierno?¦En el año 1924¦En el año 1896¦En el año 1902¦En el año 1947¦year
olimpicos¦cinco~aros¦¿Cuántos aros entrelazados tiene el símbolo olímpico?¦Un total de cinco aros¦Un total de tres aros¦Un total de siete aros¦Un total de nueve aros¦quantity
ines¦ines~puente~raices¦¿Qué descubre Inés dentro del bosque encantado?¦Un puente hecho de raíces¦Un puente hecho de hielo¦Un puente hecho de cristal¦Un puente hecho de metal¦fact
ines¦bruno~agua|corriente~cruzar¦¿Por qué Bruno no puede cruzar el arroyo?¦Porque el agua corre con fuerza¦Porque el camino está lleno de nieve¦Porque el puente está demasiado caliente¦Porque el bosque se ha quedado seco¦cause
ines¦tabla~puente¦¿Qué colocan Inés y la guardiana para ayudar a Bruno?¦Una tabla sobre el puente¦Una cuerda entre las dos orillas¦Una piedra al borde del arroyo¦Una rama junto a la madriguera¦fact
leo~alba¦semillas~roble¦¿Qué encuentran Leo y Alba junto al roble?¦Una bolsa que contiene semillas¦Una bolsa que contiene monedas¦Una bolsa que contiene conchas¦Una bolsa que contiene botones¦fact
leo~alba¦claro~luz¦¿Por qué deben plantar las semillas en el claro?¦Porque allí llega luz para crecer¦Porque allí no existe agua en el suelo¦Porque allí las raíces no crecen nunca¦Porque allí el sol nunca aparece¦cause
leo~alba¦piedras~marcar|recordar¦¿Para qué colocan piedras después de sembrar?¦Para marcar dónde plantaron las semillas¦Para tapar por completo el arroyo¦Para quitar toda la luz del claro¦Para impedir que entre el agua¦purpose
lia¦mara~panadera¦¿Quién pide ayuda a la dragona Lía?¦La panadera del pueblo llamada Mara¦La guardiana del bosque llamada Alba¦La capitana del barco llamada Sol¦La exploradora lunar llamada Nora¦fact
lia¦horno~invierno~estropea|funcionar¦¿Qué problema tiene el pueblo de Lía en invierno?¦El horno del pueblo deja de funcionar¦El puente del bosque desaparece bajo el agua¦El barco del puerto pierde todas sus velas¦El reloj de la torre deja de sonar¦cause
lia¦fuego~cuidado¦¿Cómo ayuda Lía a preparar el pan?¦Calienta el horno controlando su fuego¦Enfría el horno cubriéndolo de hielo¦Llena el horno con arena del río¦Apaga el horno sin dejar calor¦inference
capitana sol¦botella~mapa¦¿Dónde encuentra la capitana Sol el mapa?¦Dentro de una botella en la playa¦Dentro de una caja en el bosque¦Dentro de una cueva bajo la nieve¦Dentro de una barca en el lago¦place
capitana sol¦brujula~norte¦¿Para qué utiliza una brújula la tripulación de Sol?¦Para orientarse hacia la cueva del norte¦Para medir el peso de las semillas¦Para contar las olas del océano¦Para saber la edad de las piedras¦purpose
capitana sol¦cofre~semillas¦¿Qué contiene el cofre de la aventura de Sol?¦Unas semillas y una carta¦Unas monedas y un collar¦Unas conchas y un anillo¦Unas piedras y un reloj¦fact
nora¦teo~robot¦¿Con quién viaja Nora a la Luna en el cuento?¦Con el robot llamado Teo¦Con el zorro llamado Bruno¦Con la dragona llamada Lía¦Con la capitana llamada Sol¦fact
nora¦aire~respirar~trajes¦¿Por qué Nora y Teo revisan los trajes antes de salir?¦Porque necesitan aire para explorar la Luna¦Porque necesitan agua para apagar el Sol¦Porque necesitan arena para tapar sus ventanas¦Porque necesitan hielo para fabricar sus mapas¦cause
nora¦marcas~camino~nave¦¿Para qué siguen las marcas del camino Nora y Teo?¦Para regresar sin perderse a la nave¦Para encontrar peces dentro de un cráter¦Para cambiar la órbita de la Luna¦Para construir un puente sobre un río¦purpose
marte¦fobos~deimos¦¿Cómo se llaman las dos lunas de Marte?¦Son las lunas Fobos y Deimos¦Son las lunas Europa y Calisto¦Son las lunas Titán y Encélado¦Son las lunas Tritón y Nereida¦fact
marte¦rojo|rojiza~hierro¦¿Por qué parece rojo el suelo de Marte?¦Porque contiene minerales de hierro oxidados¦Porque está cubierto por flores rojas¦Porque refleja solamente el color de Venus¦Porque contiene mucha madera quemada¦cause
marte¦olimpo~volcan¦¿Qué es el monte Olimpo mencionado en la lectura?¦Un enorme volcán que está en Marte¦Un enorme cráter que está en Venus¦Un enorme océano que está en Júpiter¦Un enorme glaciar que está en Mercurio¦concept
amazon¦america del sur¦¿En qué continente se encuentra la selva amazónica?¦En la región de América del Sur¦En la región norte de África¦En la región central de Europa¦En la región este de Asia¦place
amazon¦hojas~vapor~lluvia¦¿Cómo contribuyen las hojas de la selva a la lluvia?¦Liberan vapor que ayuda a formarla¦Absorben todas las nubes del cielo¦Transforman las rocas en agua fría¦Impiden que el agua llegue al aire¦cause
amazon¦indigenas~cuida|cuidado¦¿Qué papel tienen los pueblos indígenas según la lectura?¦Conocen y cuidan la selva amazónica¦Crean nuevas estrellas sobre la selva¦Cambian el agua del Amazonas por sal¦Impiden que crezca cualquier árbol¦inference
estrella¦sol~cercana~tierra¦¿Qué estrella está más cerca de la Tierra?¦La estrella que llamamos Sol¦La estrella que llamamos Sirio¦La estrella que llamamos Vega¦La estrella que llamamos Rigel¦fact
estrella¦azules~rojas~calientes¦¿Qué estrellas están más calientes que las rojas?¦Las estrellas que son azules¦Las estrellas que son naranjas¦Las estrellas que son rojas oscuras¦Las estrellas que son rojas claras¦concept
estrella¦lejos~puntos¦¿Por qué muchas estrellas parecen puntos de luz?¦Porque se encuentran a gran distancia¦Porque todas son menores que una piedra¦Porque todas están detrás de la Luna¦Porque pierden toda su luz de noche¦cause
viking¦escandinavia~europa¦¿De qué región procedían los vikingos?¦De Escandinavia al norte de Europa¦De la costa occidental de África¦De las islas del sur de Asia¦De las montañas del sur de América¦place
viking¦barcos~velas~remos¦¿Qué utilizaban los barcos vikingos para avanzar?¦Las velas o los remos¦Los motores o las hélices¦Las ruedas o las cadenas¦Los reactores o las turbinas¦fact
viking¦comerci|vendian|cambiaban¦¿Qué actividad realizaban muchos vikingos además de las incursiones?¦Intercambiaban productos con otros pueblos¦Fabricaban satélites para observar otros planetas¦Instalaban líneas eléctricas bajo el mar¦Construían aviones para cruzar el océano¦concept
castillo¦murallas~torres¦¿Qué estructuras ayudaban a proteger un castillo medieval?¦Las murallas y las torres¦Las farolas y los semáforos¦Los raíles y los andenes¦Las chimeneas y los hornos¦fact
castillo¦puente~entrada|entrar|puerta|acceso¦¿Para qué servía un puente levadizo del castillo?¦Para controlar el acceso a la entrada¦Para observar estrellas por la noche¦Para moler trigo dentro de una torre¦Para medir la lluvia sobre el tejado¦purpose
castillo¦cocineros~artesanos¦¿Quiénes trabajaban dentro del recinto del castillo?¦Los cocineros y los artesanos¦Los astronautas y los pilotos espaciales¦Los buzos y los guías submarinos¦Los maquinistas y los técnicos ferroviarios¦inference
piratas~caribe¦caribe~rutas¦¿En qué mar actuaban los piratas descritos en la lectura?¦En las rutas del mar Caribe¦En las rutas del mar Báltico¦En las rutas del mar Caspio¦En las rutas del mar Rojo¦place
piratas~caribe¦robar|apropiarse~carga|cargamento¦¿Para qué atacaban los piratas a los barcos mercantes?¦Para robar las mercancías que transportaban¦Para llevar gratis toda su carga al puerto¦Para construir faros en todas las islas¦Para enseñar astronomía a sus tripulaciones¦purpose
piratas~caribe¦cofres~no~real|costumbre¦¿Qué aclara la lectura sobre los cofres enterrados?¦No eran una costumbre general de los piratas¦Eran siempre el único modo de guardar mercancías¦Eran la única prueba usada para navegar¦Eran un sistema para medir las mareas¦inference
natacion¦cuatro~estilos¦¿Cuántos estilos principales nombra la lectura de natación?¦Un total de cuatro estilos¦Un total de dos estilos¦Un total de seis estilos¦Un total de ocho estilos¦quantity
natacion¦espalda~boca arriba¦¿En qué posición se nada el estilo espalda?¦Con el cuerpo boca arriba¦Con el cuerpo boca abajo¦Con el cuerpo de pie¦Con el cuerpo siempre sentado¦fact
natacion¦seguridad~practicar|aprender¦¿Qué es necesario al aprender a nadar?¦Practicar con supervisión y seguir normas de seguridad¦Practicar siempre solo lejos de la orilla¦Entrar al agua sin conocer su profundidad¦Ignorar las señales de peligro de la piscina¦inference
videojuego¦programa~reglas¦¿Qué es un videojuego según la lectura?¦Un programa que responde siguiendo reglas¦Un aparato que guarda solamente agua¦Un libro que no admite ninguna acción¦Un mapa que solo indica carreteras¦concept
videojuego¦pasos|instrucciones~control¦¿Para qué escriben instrucciones quienes programan un videojuego?¦Para controlar personajes y comprobar metas¦Para sustituir las teclas por plantas¦Para hacer que el ordenador pese menos¦Para apagar todas las imágenes del juego¦purpose
videojuego¦probar~fallos|errores¦¿Por qué se prueba un videojuego antes de compartirlo?¦Para encontrar errores y poder corregirlos¦Para borrar sus reglas sin revisarlas¦Para impedir que nadie pueda utilizarlo¦Para eliminar todas sus imágenes y sonidos¦cause
invento¦telescopio~lentes~espejos¦¿Qué invento recoge luz mediante lentes o espejos?¦El aparato que llamamos telescopio¦El aparato que llamamos termómetro¦El aparato que llamamos barómetro¦El aparato que llamamos micrófono¦fact
invento¦microscopio~pequenos¦¿Para qué sirve un microscopio según la lectura?¦Para examinar detalles que son muy pequeños¦Para escuchar sonidos que son muy lejanos¦Para medir distancias entre las estrellas¦Para mover barcos entre dos puertos¦purpose
invento¦prueban~comparan¦¿Cómo eligen los inventores qué diseño funciona mejor?¦Comparan los resultados de sus pruebas¦Eligen siempre el diseño más pesado¦Evitan probar cualquiera de sus aparatos¦Escogen solo por el color de sus piezas¦inference
"""


def reviewed_rows():
    for line in ROWS.strip().splitlines():
        topic, anchors, stem, answer, a, b, c, kind = line.split("¦")
        yield topic.split("~"), anchors.split("~"), stem, (answer, a, b, c), kind
