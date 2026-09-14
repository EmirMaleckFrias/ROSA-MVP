"""Pone tildes a los textos visibles del frontend sin tocar el codigo.

Solo actua sobre: texto JSX entre etiquetas (sin llaves), los atributos de
texto (titulo, nota, placeholder, aria-label, title, etiqueta, label, texto,
explicacion, definicion, pista) y los valores (no las claves) de etiquetas.ts
y glosario.ts. Nunca toca identificadores, claves, rutas ni nombres de clase.
Diccionario cerrado de palabras con acento inequivoco; las ambiguas (esta,
como, que, si, solo, aun) se dejan como estan.
"""

import re
import sys
from pathlib import Path

PALABRAS = {
    # Palabras con ñ (14 de septiembre, segunda pasada)
    "pestana": "pestaña", "pestanas": "pestañas", "senala": "señala", "senalan": "señalan", "senalar": "señalar", "senalado": "señalado", "senalada": "señalada", "senalados": "señalados", "senaladas": "señaladas", "ensenado": "enseñado", "ensenada": "enseñada", "ensene": "enseñe", "anadiendo": "añadiendo", "anadio": "añadió", "anadiste": "añadiste", "anadimos": "añadimos", "anaden": "añaden", "anadira": "añadirá", "anadirlo": "añadirlo", "anadirla": "añadirla", "resena": "reseña", "resenas": "reseñas", "contrasena": "contraseña", "contrasenas": "contraseñas", "manana": "mañana", "companera": "compañera", "companeros": "compañeros", "companeras": "compañeras", "disenar": "diseñar", "disenado": "diseñado", "disenada": "diseñada", "disenados": "diseñados", "disenadas": "diseñadas", "extrano": "extraño", "extrana": "extraña", "extranos": "extraños", "extranas": "extrañas", "engano": "engaño", "enganoso": "engañoso", "enganosa": "engañosa", "enganosos": "engañosos", "enganosas": "engañosas", "dueno": "dueño", "duena": "dueña", "nino": "niño", "ninos": "niños", "nina": "niña", "ninas": "niñas", "sueno": "sueño", "cumpleanos": "cumpleaños", "otono": "otoño", "danado": "dañado", "danada": "dañada", "danar": "dañar", "punado": "puñado", "tamanos": "tamaños", "pequenez": "pequeñez", "ensenanza": "enseñanza", "antano": "antaño", "desempeno": "desempeño", "empeno": "empeño", "panuelo": "pañuelo",
    # -cion / -sion
    "hipotesis": "hipótesis", "investigacion": "investigación", "iteracion": "iteración", "decision": "decisión", "revision": "revisión",
    "verificacion": "verificación", "extraccion": "extracción", "comprobacion": "comprobación", "informacion": "información", "poblacion": "población",
    "intervencion": "intervención", "prediccion": "predicción", "reproduccion": "reproducción", "clasificacion": "clasificación", "evaluacion": "evaluación",
    "atencion": "atención", "seccion": "sección", "opcion": "opción", "configuracion": "configuración", "generacion": "generación", "replicacion": "replicación",
    "relacion": "relación", "publicacion": "publicación", "situacion": "situación", "condicion": "condición", "direccion": "dirección", "explicacion": "explicación",
    "descripcion": "descripción", "funcion": "función", "version": "versión", "precision": "precisión", "aprobacion": "aprobación", "ejecucion": "ejecución",
    "calibracion": "calibración", "aclaracion": "aclaración", "reformulacion": "reformulación", "retractacion": "retractación", "mision": "misión",
    "conclusion": "conclusión", "exclusion": "exclusión", "inclusion": "inclusión", "fusion": "fusión", "expresion": "expresión", "vision": "visión",
    "division": "división", "conexion": "conexión", "dimension": "dimensión", "cuestion": "cuestión", "gestion": "gestión", "extension": "extensión",
    "sesion": "sesión", "region": "región", "opinion": "opinión", "atribucion": "atribución", "transcripcion": "transcripción", "interpretacion": "interpretación",
    "refutacion": "refutación", "confirmacion": "confirmación", "formulacion": "formulación", "priorizacion": "priorización", "normalizacion": "normalización",
    "agregacion": "agregación", "simulacion": "simulación", "migracion": "migración", "sincronizacion": "sincronización", "integracion": "integración",
    "notificacion": "notificación", "resolucion": "resolución", "distribucion": "distribución", "evolucion": "evolución", "proporcion": "proporción",
    "correccion": "corrección", "seleccion": "selección", "coleccion": "colección", "deteccion": "detección", "inyeccion": "inyección", "produccion": "producción",
    "reduccion": "reducción", "construccion": "construcción", "posicion": "posición", "disposicion": "disposición", "composicion": "composición",
    "exposicion": "exposición", "transicion": "transición", "edicion": "edición", "definicion": "definición", "medicion": "medición", "peticion": "petición",
    "repeticion": "repetición", "cognicion": "cognición", "mutacion": "mutación", "asociacion": "asociación", "variacion": "variación", "operacion": "operación",
    "aplicacion": "aplicación", "comunicacion": "comunicación", "ubicacion": "ubicación", "identificacion": "identificación", "certificacion": "certificación",
    "justificacion": "justificación", "especificacion": "especificación", "modificacion": "modificación", "calificacion": "calificación",
    "estratificacion": "estratificación", "cuantificacion": "cuantificación", "comparacion": "comparación", "preparacion": "preparación", "reparacion": "reparación",
    "separacion": "separación", "declaracion": "declaración", "colaboracion": "colaboración", "consideracion": "consideración", "exploracion": "exploración",
    "elaboracion": "elaboración", "valoracion": "valoración", "creacion": "creación", "negacion": "negación", "obligacion": "obligación", "navegacion": "navegación",
    "indicacion": "indicación", "conservacion": "conservación", "observacion": "observación", "activacion": "activación", "elevacion": "elevación",
    "atenuacion": "atenuación", "continuacion": "continuación", "actuacion": "actuación", "puntuacion": "puntuación", "ecuacion": "ecuación", "solucion": "solución",
    "contribucion": "contribución", "institucion": "institución", "sustitucion": "sustitución", "disminucion": "disminución", "senalizacion": "señalización",
    "deduplicacion": "deduplicación", "compactacion": "compactación", "presentacion": "presentación", "documentacion": "documentación", "recomendacion": "recomendación",
    "autenticacion": "autenticación", "asignacion": "asignación", "combinacion": "combinación", "eliminacion": "eliminación", "determinacion": "determinación",
    "coordinacion": "coordinación", "imaginacion": "imaginación", "inclinacion": "inclinación", "terminacion": "terminación", "contaminacion": "contaminación",
    "informacion": "información", "anotacion": "anotación", "interaccion": "interacción", "reaccion": "reacción", "accion": "acción", "traduccion": "traducción",
    "adopcion": "adopción", "excepcion": "excepción", "recepcion": "recepción", "percepcion": "percepción", "concepcion": "concepción", "descripcion": "descripción",
    "inscripcion": "inscripción", "suscripcion": "suscripción", "prescripcion": "prescripción", "conversion": "conversión", "inversion": "inversión",
    "progresion": "progresión", "regresion": "regresión", "agresion": "agresión", "depresion": "depresión", "supresion": "supresión", "compresion": "compresión",
    "impresion": "impresión", "admision": "admisión", "emision": "emisión", "omision": "omisión", "remision": "remisión", "transmision": "transmisión",
    "comision": "comisión", "tension": "tensión", "hipertension": "hipertensión", "pension": "pensión", "comprension": "comprensión", "aprehension": "aprehensión",
    "extension": "extensión", "pretension": "pretensión", "dispersion": "dispersión", "confusion": "confusión", "difusion": "difusión", "profusion": "profusión",
    "ilusion": "ilusión", "colusion": "colusión", "alusion": "alusión", "erosion": "erosión", "explosion": "explosión", "corrosion": "corrosión",
    "lesion": "lesión", "adhesion": "adhesión", "cohesion": "cohesión", "revision": "revisión", "supervision": "supervisión", "prevision": "previsión",
    "provision": "provisión", "television": "televisión", "concesion": "concesión", "sucesion": "sucesión", "posesion": "posesión", "recesion": "recesión",
    "obsesion": "obsesión", "profesion": "profesión", "confesion": "confesión", "expresion": "expresión", "represion": "represión",
    # esdrujulas y otras
    "analisis": "análisis", "sintesis": "síntesis", "tecnico": "técnico", "tecnica": "técnica", "tecnicos": "técnicos", "tecnicas": "técnicas",
    "clinico": "clínico", "clinica": "clínica", "clinicos": "clínicos", "clinicas": "clínicas", "medica": "médica", "medicos": "médicos", "medicas": "médicas",
    "cientifico": "científico", "cientifica": "científica", "cientificos": "científicos", "cientificas": "científicas", "estadistico": "estadístico",
    "estadistica": "estadística", "estadisticos": "estadísticos", "estadisticas": "estadísticas", "biologico": "biológico", "biologica": "biológica",
    "genetica": "genética", "genetico": "genético", "geneticos": "genéticos", "geneticas": "genéticas", "plasmatico": "plasmático", "plasmatica": "plasmática",
    "plasmaticos": "plasmáticos", "plasmaticas": "plasmáticas", "publica": "pública", "publicos": "públicos", "publicas": "públicas",
    "unico": "único", "unica": "única", "unicos": "únicos", "unicas": "únicas", "ultimo": "último", "ultima": "última", "ultimos": "últimos", "ultimas": "últimas",
    "numero": "número", "numeros": "números", "numerico": "numérico", "numerica": "numérica", "codigo": "código", "codigos": "códigos", "metodo": "método", "metodos": "métodos",
    "minimo": "mínimo", "minima": "mínima", "minimos": "mínimos", "maximo": "máximo", "maxima": "máxima", "maximos": "máximos", "automatico": "automático",
    "automatica": "automática", "automaticos": "automáticos", "automaticas": "automáticas", "valida": "válida", "validos": "válidos",
    "rapida": "rápida", "rapido": "rápido", "dificil": "difícil", "facil": "fácil", "aqui": "aquí", "asi": "así", "mas": "más", "tambien": "también",
    "despues": "después", "segun": "según", "pagina": "página", "paginas": "páginas", "dia": "día", "dias": "días", "todavia": "todavía", "categoria": "categoría",
    "categorias": "categorías", "articulo": "artículo", "articulos": "artículos", "especifica": "específica", "especificos": "específicos",
    "especificas": "específicas", "farmaco": "fármaco", "farmacos": "fármacos", "celula": "célula", "celulas": "células", "molecula": "molécula", "moleculas": "moléculas",
    "proteina": "proteína", "proteinas": "proteínas", "ademas": "además", "area": "área", "areas": "áreas", "campana": "campaña", "campanas": "campañas",
    "anadir": "añadir", "anade": "añade", "anadido": "añadido", "anadida": "añadida", "anadidos": "añadidos", "anadidas": "añadidas", "ensena": "enseña", "ensenan": "enseñan",
    "ensenar": "enseñar", "pequeno": "pequeño", "pequena": "pequeña", "pequenos": "pequeños", "pequenas": "pequeñas", "tamano": "tamaño", "ano": "año", "anos": "años",
    "diseno": "diseño", "disenos": "diseños", "senal": "señal", "senales": "señales", "dano": "daño", "danos": "daños", "companero": "compañero", "espanol": "español",
    "cronologico": "cronológico", "cronologica": "cronológica", "historico": "histórico", "historica": "histórica", "indice": "índice", "limite": "límite",
    "limites": "límites", "practica": "práctica", "practico": "práctico", "grafico": "gráfico", "grafica": "gráfica", "critica": "crítica",
    "criticos": "críticos", "criticas": "críticas", "logica": "lógica", "logico": "lógico", "proximo": "próximo", "proxima": "próxima", "linea": "línea", "lineas": "líneas",
    "medicion": "medición", "epoca": "época", "capitulo": "capítulo", "titulo": "título", "titulos": "títulos", "musculo": "músculo", "energia": "energía",
    "teoria": "teoría", "memoria": "memoria", "mecanico": "mecánico", "quimico": "químico", "quimica": "química", "fisico": "físico", "fisica": "física",
    "matematico": "matemático", "matematica": "matemática", "electronico": "electrónico", "electronica": "electrónica", "cronico": "crónico", "cronica": "crónica",
    "sintoma": "síntoma", "sintomas": "síntomas", "diagnostico": "diagnóstico", "diagnostica": "diagnóstica", "pronostico": "pronóstico", "pronostica": "pronóstica",
    "terapeutico": "terapéutico", "terapeutica": "terapéutica", "terapeuticos": "terapéuticos", "terapeuticas": "terapéuticas", "patologico": "patológico",
    "patologica": "patológica", "neurologico": "neurológico", "neurologica": "neurológica", "cognitivo": "cognitivo", "amiloide": "amiloide",     "vinculos": "vínculos", "parrafo": "párrafo", "parrafos": "párrafos", "sabado": "sábado", "miercoles": "miércoles", "credito": "crédito",     "proposito": "propósito", "propositos": "propósitos", "hipotetico": "hipotético", "hipotetica": "hipotética", "sistematico": "sistemático", "sistematica": "sistemática",
    "sistematicas": "sistemáticas", "aleatorio": "aleatorio", "electrico": "eléctrico", "atomico": "atómico", "dinamico": "dinámico", "dinamica": "dinámica",
    "semantico": "semántico", "semantica": "semántica", "esporadico": "esporádico", "esporadica": "esporádica", "periodico": "periódico", "periodica": "periódica",
    "cardiaco": "cardíaco", "basico": "básico", "basica": "básica", "basicos": "básicos", "basicas": "básicas", "practicas": "prácticas", "practicos": "prácticos",
    "identico": "idéntico", "identica": "idéntica", "autentico": "auténtico", "autentica": "auténtica", "fantastico": "fantástico", "drastico": "drástico",
    "elastico": "elástico", "plastico": "plástico", "estatico": "estático", "estatica": "estática", "sintetico": "sintético", "sintetica": "sintética",
    "sinteticos": "sintéticos", "sinteticas": "sintéticas", "canonico": "canónico", "canonica": "canónica", "canonicos": "canónicos", "canonicas": "canónicas",
    "heuristico": "heurístico", "heuristica": "heurística", "determinista": "determinista", "empirico": "empírico", "empirica": "empírica",
    "bibliografico": "bibliográfico", "bibliografica": "bibliográfica", "biomedico": "biomédico", "biomedica": "biomédica", "academico": "académico",
    "academica": "académica", "economico": "económico", "economica": "económica", "politica": "política", "politicas": "políticas", "estrategico": "estratégico",
    "estrategica": "estratégica", "geografico": "geográfico", "electronicos": "electrónicos", "utiles": "útiles", "util": "útil", "inutil": "inútil", "debil": "débil",
    "debiles": "débiles", "fragil": "frágil", "fragiles": "frágiles", "estable": "estable", "movil": "móvil", "moviles": "móviles", "habil": "hábil",
    "facilmente": "fácilmente", "rapidamente": "rápidamente", "ultimamente": "últimamente", "unicamente": "únicamente", "automaticamente": "automáticamente",
    "tecnicamente": "técnicamente", "practicamente": "prácticamente", "basicamente": "básicamente", "especificamente": "específicamente",
    "explicitamente": "explícitamente", "explicito": "explícito", "explicita": "explícita", "implicito": "implícito", "implicita": "implícita",
    "podra": "podrá", "sera": "será", "seran": "serán", "habra": "habrá", "estara": "estará", "tendra": "tendrá", "hara": "hará", "dira": "dirá",
    "volvera": "volverá", "quedara": "quedará", "cambiara": "cambiará", "arrancara": "arrancará", "ira": "irá", "iran": "irán", "pondra": "pondrá", "dejara": "dejará",
    "empezo": "empezó", "propuso": "propuso", "encontro": "encontró", "decidio": "decidió", 
    "llego": "llegó", "quedo": "quedó", "volvio": "volvió", "corrio": "corrió", "recibio": "recibió", 
    "respondio": "respondió", "resolvio": "resolvió", "reformulo": "reformuló", "murio": "murió", "mostro": "mostró", "pidio": "pidió",
    "mientras": "mientras", "esta": "esta", "estan": "están", "estas": "estas", "esto": "esto",
    "biomarcador": "biomarcador", "electronico": "electrónico", "acido": "ácido", "acidos": "ácidos", "oxigeno": "oxígeno", "hidrogeno": "hidrógeno",
    "torax": "tórax", "cancer": "cáncer", "cerebro": "cerebro", "cranial": "cranial", "neuron": "neurón", "regimen": "régimen", "origen": "origen",
    "examen": "examen", "imagen": "imagen", "volumen": "volumen", "margen": "margen", "orden": "orden", "joven": "joven", "jovenes": "jóvenes", "examenes": "exámenes",
    "imagenes": "imágenes", "volumenes": "volúmenes", "margenes": "márgenes", "ordenes": "órdenes", "origenes": "orígenes", "regimenes": "regímenes",
    "caracter": "carácter", "caracteres": "caracteres", "cinetica": "cinética", "cinetico": "cinético",
    "dolares": "dólares", "dolar": "dólar", "porcentaje": "porcentaje", "parametro": "parámetro", "parametros": "parámetros", "topico": "tópico",
    "simbolo": "símbolo", "simbolos": "símbolos", "vertice": "vértice", "pelicula": "película", "peninsula": "península", "formula": "fórmula", "formulas": "fórmulas",
    "cupula": "cúpula", "molecular": "molecular", "cronologia": "cronología", "metodologia": "metodología", "tecnologia": "tecnología", "biologia": "biología",
    "genealogia": "genealogía", "patologia": "patología", "neurologia": "neurología", "epidemiologia": "epidemiología", "ontologia": "ontología",
    "ontologias": "ontologías", "farmacologia": "farmacología", "ecologia": "ecología", "teologia": "teología", "geologia": "geología", "tipologia": "tipología",
    "jerarquia": "jerarquía", "garantia": "garantía", "guia": "guía", "guias": "guías", "via": "vía", "vias": "vías", "compania": "compañía", "companias": "compañías",
    "mayoria": "mayoría", "minoria": "minoría", "autonomia": "autonomía", "economia": "economía", "anatomia": "anatomía", "autopsia": "autopsia",
    "policia": "policía", "cirugia": "cirugía", "alergia": "alergia", "energia": "energía", "sinergia": "sinergia", "estrategia": "estrategia",
    "todavia": "todavía", "frio": "frío", "rio": "río", "vacio": "vacío", "vacia": "vacía", "vacios": "vacíos", "vacias": "vacías", "raiz": "raíz", "raices": "raíces",
    "pais": "país", "paises": "países", "maiz": "maíz", "oido": "oído", "caido": "caído", "traido": "traído", "leido": "leído", "leidos": "leídos", "leida": "leída", "leidas": "leídas",
    "construido": "construido", "incluido": "incluido", "continuo": "continuo", "reune": "reúne", "reunen": "reúnen", "prohibe": "prohíbe", "prohibido": "prohibido",
    "ahi": "ahí", "baul": "baúl", "atras": "atrás", "detras": "detrás", "ademas": "además", "jamas": "jamás", "quizas": "quizás", "traves": "través",
    "veras": "verás", "sabras": "sabrás", "podras": "podrás", "tendras": "tendrás", "estaras": "estarás", "encontraras": "encontrarás",
    "interes": "interés", "intereses": "intereses", "frances": "francés", "ingles": "inglés", "japones": "japonés", "portugues": "portugués",
    "marques": "marqués", "despues": "después", "entremes": "entremés", "reves": "revés", "ademas": "además",
    "vesícula": "vesícula", "invalido": "inválido", "invalida": "inválida", "invalidos": "inválidos", "invalidas": "inválidas",
}
AMBIGUAS_EXCLUIDAS = {"esta", "estas", "esto", "mientras", "memoria", "biomarcador", "cerebro", "cranial", "examen", "imagen", "volumen", "margen", "orden", "joven", "origen", "caracteres", "porcentaje", "molecular", "autopsia", "alergia", "sinergia", "estrategia", "construido", "incluido", "continuo", "prohibido", "intereses", "aleatorio", "amiloide", "cognitivo", "determinista", "estable", "propuso", "vesícula", "neuron"}
for k in AMBIGUAS_EXCLUIDAS:
    PALABRAS.pop(k, None)

PATRON = re.compile(r"\b(" + "|".join(sorted(map(re.escape, PALABRAS), key=len, reverse=True)) + r")\b", re.I)


def acentuar_texto(texto: str) -> str:
    def rep(m: re.Match) -> str:
        palabra = m.group(0)
        base = PALABRAS[palabra.lower()]
        if palabra.isupper():
            return base.upper()
        if palabra[0].isupper():
            return base[0].upper() + base[1:]
        return base

    return PATRON.sub(rep, texto)


ATRIBUTOS = ("titulo", "nota", "placeholder", "aria-label", "title", "etiqueta", "label", "texto", "explicacion", "definicion", "pista", "descripcion", "resumen", "sub")


def acentuar_tsx(codigo: str) -> str:
    # 1. Texto JSX entre etiquetas: solo tramos que son texto de verdad (en una
    #    linea, sin llaves ni signos de codigo: parentesis, igual, punto y coma,
    #    corchetes, flechas). Asi no se toca `=> b.numero - a.numero` ni tipos.
    def jsx(m: re.Match) -> str:
        t = m.group(1)
        if re.search(r"[=(){};\[\]`|&]", t) or re.search(r"\w\.\w", t) or t.strip() == "":
            return m.group(0)
        return ">" + acentuar_texto(t) + "<"

    codigo = re.sub(r">([^<>{}\n]+)<", jsx, codigo)
    # 2. Atributos de texto con comillas dobles.
    def attr(m: re.Match) -> str:
        return f'{m.group(1)}="{acentuar_texto(m.group(2))}"'

    codigo = re.sub(r"\b(" + "|".join(ATRIBUTOS) + r')="([^"\n]*)"', attr, codigo)
    # 3. Atributos de texto con comillas simples dentro de objetos: etiqueta: '...', nota: '...'
    def prop(m: re.Match) -> str:
        return f"{m.group(1)}: '{acentuar_texto(m.group(2))}'"

    codigo = re.sub(r"\b(" + "|".join(ATRIBUTOS) + r"|nombre|corto|frase)\s*:\s*'((?:[^'\\\n]|\\.)*)'", prop, codigo)
    # 4. Cadenas de texto largas (con espacio) entre comillas simples dentro de JSX o ternarios: solo si tienen al menos dos palabras y empiezan por mayuscula o por articulo.
    def cadena(m: re.Match) -> str:
        t = m.group(1)
        if " " in t and not t.startswith(("#", "/", "http")) and re.match(r"^[A-ZÁÉÍÓÚÑ¿¡]", t):
            return "'" + acentuar_texto(t) + "'"
        return m.group(0)

    codigo = re.sub(r"'((?:[^'\\\n]|\\.){12,})'", cadena, codigo)
    # 5. Plantillas `...${x}...` con texto: se acentua solo el texto fuera de las
    #    llaves, y nunca en plantillas que forman rutas, clases o claves.
    def plantilla(m: re.Match) -> str:
        t = m.group(1)
        if any(c in t for c in "/#=") or " " not in t or "${" not in t:
            return m.group(0)
        # Plantillas de clases, ids o claves: `sección ${x}` seria un desastre.
        antes = m.string[max(0, m.start() - 14) : m.start()]
        if re.search(r"(className|class|id|key|htmlFor|name|href|data-\w+)=\{$", antes):
            return m.group(0)
        partes = re.split(r"(\$\{[^}]*\})", t)
        # Si algun trozo de texto parece codigo (acceso a propiedad, ternario,
        # plantilla anidada), la plantilla entera se deja como esta.
        if any(re.search(r"\w\.\w|[?]|\$\{", x) for x in partes if not x.startswith("${")):
            return m.group(0)
        return "`" + "".join(x if x.startswith("${") else acentuar_texto(x) for x in partes) + "`"

    codigo = re.sub(r"`([^`\n]*)`", plantilla, codigo)
    return codigo


def acentuar_valores_ts(codigo: str) -> str:
    # Valores de cadena tras ": " (no claves), y valores en arrays de textos.
    def valor(m: re.Match) -> str:
        v = m.group(2)
        # Una sola palabra en minuscula es casi siempre un valor que se compara
        # con el servidor ('sistematica', 'vacio'), no un texto visible.
        if " " not in v and v[:1].islower():
            return m.group(0)
        # Con pinta de codigo (claves, rutas, plantillas, llamadas): no se toca.
        if re.search(r"[_={}$/\\<>]|\w\.\w", v):
            return m.group(0)
        return f"{m.group(1)}'{acentuar_texto(v)}'"

    return re.sub(r"(:\s*)'((?:[^'\\\n]|\\.)*)'", valor, codigo)


def acentuar_cadenas_ts(codigo: str) -> str:
    """Ficheros de datos y del almacen: cualquier cadena entre comillas simples
    con un espacio y sin pinta de codigo es un texto que alguien lee (eventos,
    avisos, datos de muestra)."""

    def cadena(m: re.Match) -> str:
        v = m.group(1)
        if " " not in v or re.search(r"[_={}$/\\<>]|\w\.\w", v):
            return m.group(0)
        return f"'{acentuar_texto(v)}'"

    return re.sub(r"'((?:[^'\\\n]|\\.)*)'", cadena, codigo)


def main() -> None:
    raiz = Path(__file__).resolve().parents[1] / "src"
    cambiados = 0
    for f in sorted(raiz.rglob("*.tsx")):
        if f.name.endswith(".test.tsx"):
            continue
        antes = f.read_text()
        despues = acentuar_tsx(antes)
        if despues != antes:
            f.write_text(despues)
            cambiados += 1
    for nombre in ("lib/etiquetas.ts", "lib/glosario.ts", "lib/objetivo.ts", "lib/digest.ts", "lib/priorizacion.ts", "lib/evidencia.ts", "lib/calidad.ts", "lib/hipotesis.ts", "lib/exportar.ts"):
        f = raiz / nombre
        if not f.exists():
            continue
        antes = f.read_text()
        despues = acentuar_valores_ts(antes)
        if despues != antes:
            f.write_text(despues)
            cambiados += 1
    for nombre in ("datos/muestra.ts", "datos/simulacion.ts", "datos/acciones.ts", "datos/almacen.ts"):
        f = raiz / nombre
        antes = f.read_text()
        despues = acentuar_cadenas_ts(antes)
        if despues != antes:
            f.write_text(despues)
            cambiados += 1
    print(f"{cambiados} ficheros con tildes nuevas")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probar":
        print(acentuar_texto(sys.stdin.read()))
    else:
        main()
