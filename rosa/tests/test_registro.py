"""Qué cambió entre versiones de una hipótesis (rosa/registro.py): el diff
por regla, el resumen en castellano, la instantánea extendida, las revisiones
PROV para el RO-Crate y la paridad con frontend/src/lib/registro.ts. Sin red
ni modelos."""

import copy
import json
import re
import tempfile
from pathlib import Path

import pytest

from rosa import registro as R
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen

# Los mismos casos, con el mismo texto, que frontend/src/lib/registro.test.ts.
# El test de paridad de abajo lee aquel fichero y comprueba que el JSON es el
# mismo: si se cambia uno, hay que cambiar el otro igual.
# CASOS-INICIO
CASOS_JSON = r"""{
  "sinCambios": "Sin cambios en los campos de la hipótesis",
  "etiquetas": {
    "titulo": "Título",
    "enunciado": "Enunciado",
    "mecanismo": "Mecanismo",
    "comprobacion.biomarcador": "Biomarcador",
    "comprobacion.cohorte": "Cohorte",
    "comprobacion.diseno": "Diseño",
    "tarjeta.diana": "Diana",
    "tarjeta.celula": "Célula",
    "tarjeta.etapa": "Etapa",
    "tarjeta.intervencion": "Intervención",
    "tarjeta.direccion": "Dirección",
    "tarjeta.prediccionFalsable": "Predicción falsable",
    "tarjeta.riesgos": "Riesgos",
    "tarjeta.pasoRuta": "Paso de la ruta"
  },
  "legibles": [
    {"campo": "tarjeta.direccion", "valor": "aumenta", "legible": "aumenta"},
    {"campo": "tarjeta.direccion", "valor": "disminuye", "legible": "disminuye"},
    {"campo": "tarjeta.direccion", "valor": "modula", "legible": "modula"},
    {"campo": "tarjeta.direccion", "valor": "sin_intervencion", "legible": "sin intervención"},
    {"campo": "tarjeta.direccion", "valor": "inhibe_parcialmente", "legible": "inhibe parcialmente"},
    {"campo": "tarjeta.direccion", "valor": "", "legible": ""},
    {"campo": "tarjeta.pasoRuta", "valor": "mecanismo", "legible": "Mecanismo"},
    {"campo": "tarjeta.pasoRuta", "valor": "opciones_intervencion", "legible": "Opciones de intervención"},
    {"campo": "tarjeta.pasoRuta", "valor": "compromiso_diana", "legible": "Compromiso de diana"},
    {"campo": "tarjeta.pasoRuta", "valor": "efecto_funcional", "legible": "Efecto funcional"},
    {"campo": "tarjeta.pasoRuta", "valor": "selectividad_toxicidad", "legible": "Selectividad y toxicidad"},
    {"campo": "tarjeta.pasoRuta", "valor": "exposicion", "legible": "Entrega y exposición"},
    {"campo": "tarjeta.pasoRuta", "valor": "replicacion_independiente", "legible": "Replicación independiente"},
    {"campo": "tarjeta.pasoRuta", "valor": "evidencia_poblacion", "legible": "Evidencia en la población"},
    {"campo": "tarjeta.pasoRuta", "valor": "paso_inventado", "legible": "paso inventado"},
    {"campo": "titulo", "valor": "sin_intervencion", "legible": "sin_intervencion"},
    {"campo": "tarjeta.direccion", "valor": "constructor", "legible": "constructor"},
    {"campo": "tarjeta.direccion", "valor": "hasOwnProperty", "legible": "hasOwnProperty"},
    {"campo": "tarjeta.pasoRuta", "valor": "toString", "legible": "toString"},
    {"campo": "tarjeta.pasoRuta", "valor": "valueOf", "legible": "valueOf"},
    {"campo": "tarjeta.direccion", "valor": "  aumenta \t", "legible": "aumenta"},
    {"campo": "tarjeta.pasoRuta", "valor": " compromiso_diana ", "legible": "Compromiso de diana"},
    {"campo": "tarjeta.riesgos", "valor": "confusión por edad", "legible": "confusión por edad"}
  ],
  "cadenas": [
    {
      "nombre": "ordenada_de_v1_a_v3",
      "hipotesis": {"id": "hip-a", "version": 3, "titulo": "C", "versiones": [{"n": 1, "fecha": 10, "quien": "Rosa", "motivo": "primera", "titulo": "A"}, {"n": 2, "fecha": 20, "quien": "persona", "motivo": "segunda", "titulo": "B"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": [{"campo": "titulo", "antes": "A", "despues": "B"}]},
        {"deN": 2, "aN": 3, "cambios": [{"campo": "titulo", "antes": "B", "despues": "C"}]}
      ]
    },
    {
      "nombre": "desordenada_con_n_repetido",
      "hipotesis": {"id": "hip-b", "version": 3, "titulo": "C", "versiones": [{"n": 2, "titulo": "B"}, {"n": 1, "titulo": "A"}, {"n": 2, "titulo": "B2"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": [{"campo": "titulo", "antes": "A", "despues": "B"}]},
        {"deN": 2, "aN": 3, "cambios": [{"campo": "titulo", "antes": "B", "despues": "B2"}]},
        {"deN": 3, "aN": 4, "cambios": [{"campo": "titulo", "antes": "B2", "despues": "C"}]}
      ]
    },
    {
      "nombre": "sin_n_ni_version_y_con_entradas_rotas",
      "hipotesis": {"id": "hip-c", "titulo": "C", "versiones": [{"titulo": "A"}, "rota", null, {"titulo": "B"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": [{"campo": "titulo", "antes": "A", "despues": "B"}]},
        {"deN": 2, "aN": 3, "cambios": [{"campo": "titulo", "antes": "B", "despues": "C"}]}
      ]
    },
    {
      "nombre": "sin_versiones",
      "hipotesis": {"id": "hip-d", "titulo": "A"},
      "esperado": []
    },
    {
      "nombre": "version_actual_atrasada_no_apunta_a_si_misma",
      "hipotesis": {"id": "hip-e", "version": 1, "titulo": "B", "versiones": [{"n": 1, "titulo": "A"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": [{"campo": "titulo", "antes": "A", "despues": "B"}]}
      ]
    },
    {
      "nombre": "sin_id_y_sin_cambios_en_los_campos",
      "hipotesis": {"version": 2, "titulo": "A", "versiones": [{"n": 1, "titulo": "A", "motivo": "solo cambió el motivo"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": []}
      ]
    },
    {
      "nombre": "sin_n_toma_su_posicion_y_un_n_alto_manda",
      "hipotesis": {"id": "hip-f", "version": 3, "titulo": "C", "versiones": [{"n": 5, "titulo": "X"}, {"titulo": "Y"}]},
      "esperado": [
        {"deN": 1, "aN": 5, "cambios": [{"campo": "titulo", "antes": "Y", "despues": "X"}]},
        {"deN": 5, "aN": 6, "cambios": [{"campo": "titulo", "antes": "X", "despues": "C"}]}
      ]
    },
    {
      "nombre": "n_booleano_texto_o_con_decimales_toma_su_posicion",
      "hipotesis": {"id": "hip-g", "titulo": "B", "versiones": [{"n": true, "titulo": "A"}, {"n": "2", "titulo": "A2"}, {"n": 1.5, "titulo": "A3"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": [{"campo": "titulo", "antes": "A", "despues": "A2"}]},
        {"deN": 2, "aN": 3, "cambios": [{"campo": "titulo", "antes": "A2", "despues": "A3"}]},
        {"deN": 3, "aN": 4, "cambios": [{"campo": "titulo", "antes": "A3", "despues": "B"}]}
      ]
    },
    {
      "nombre": "n_y_version_como_flotantes_enteros",
      "hipotesis": {"id": "hip-j", "version": 3.0, "titulo": "C", "versiones": [{"n": 1.0, "titulo": "A"}, {"n": 2.0, "titulo": "B"}]},
      "esperado": [
        {"deN": 1, "aN": 2, "cambios": [{"campo": "titulo", "antes": "A", "despues": "B"}]},
        {"deN": 2, "aN": 3, "cambios": [{"campo": "titulo", "antes": "B", "despues": "C"}]}
      ]
    },
    {
      "nombre": "versiones_que_no_son_lista_sino_objeto",
      "hipotesis": {"id": "hip-h", "version": 2, "titulo": "B", "versiones": {"n": 1, "titulo": "A"}},
      "esperado": []
    },
    {
      "nombre": "versiones_como_texto",
      "hipotesis": {"id": "hip-i", "version": 2, "titulo": "B", "versiones": "v1"},
      "esperado": []
    }
  ],
  "casos": [
    {
      "nombre": "sin_cambios_identicas",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "despues": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "enunciado_y_cohorte",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "despues": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que p-tau181", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "BioFINDER", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "cambios": [
        {"campo": "enunciado", "antes": "En portadores de APOE4 GFAP se altera antes que NfL", "despues": "En portadores de APOE4 GFAP se altera antes que p-tau181"},
        {"campo": "comprobacion.cohorte", "antes": "ADNI", "despues": "BioFINDER"}
      ],
      "resumen": "Cambió el enunciado y la cohorte (ADNI -> BioFINDER)"
    },
    {
      "nombre": "tarjeta_aparece_campo_a_campo",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": null},
      "despues": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "", "etapa": "", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": [], "pasoRuta": "mecanismo"}},
      "cambios": [
        {"campo": "tarjeta.diana", "antes": "", "despues": "GFAP"},
        {"campo": "tarjeta.direccion", "antes": "", "despues": "sin_intervencion"},
        {"campo": "tarjeta.prediccionFalsable", "antes": "", "despues": "GFAP no sube antes que NfL en ADNI"},
        {"campo": "tarjeta.pasoRuta", "antes": "", "despues": "mecanismo"}
      ],
      "resumen": "Cambió la diana (nuevo: GFAP), la dirección (nuevo: sin intervención), la predicción falsable (nuevo: GFAP no sube antes que NfL en ADNI) y el paso de la ruta (nuevo: Mecanismo)"
    },
    {
      "nombre": "tarjeta_desaparece_campo_a_campo",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "despues": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": null},
      "cambios": [
        {"campo": "tarjeta.diana", "antes": "GFAP", "despues": ""},
        {"campo": "tarjeta.celula", "antes": "astrocito", "despues": ""},
        {"campo": "tarjeta.etapa", "antes": "preclínica", "despues": ""},
        {"campo": "tarjeta.direccion", "antes": "sin_intervencion", "despues": ""},
        {"campo": "tarjeta.prediccionFalsable", "antes": "GFAP no sube antes que NfL en ADNI", "despues": ""},
        {"campo": "tarjeta.riesgos", "antes": "confusión por edad", "despues": ""},
        {"campo": "tarjeta.pasoRuta", "antes": "mecanismo", "despues": ""}
      ],
      "resumen": "Cambió la diana (quitado: GFAP), la célula (quitado: astrocito), la etapa (quitado: preclínica), la dirección (quitado: sin intervención), la predicción falsable (quitado: GFAP no sube antes que NfL en ADNI), los riesgos (quitado: confusión por edad) y el paso de la ruta (quitado: Mecanismo)"
    },
    {
      "nombre": "registro_antiguo_sin_claves_nuevas",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL"},
      "despues": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "", "comprobacion": {"biomarcador": "GFAP", "cohorte": "", "diseno": ""}, "tarjeta": null},
      "cambios": [
        {"campo": "comprobacion.biomarcador", "antes": "", "despues": "GFAP"}
      ],
      "resumen": "Cambió el biomarcador (nuevo: GFAP)"
    },
    {
      "nombre": "riesgos_lista_unida_por_punto_y_coma",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad", "n pequeño"], "pasoRuta": "mecanismo"}},
      "despues": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad", "sesgo de selección"], "pasoRuta": "mecanismo"}},
      "cambios": [
        {"campo": "tarjeta.riesgos", "antes": "confusión por edad; n pequeño", "despues": "confusión por edad; sesgo de selección"}
      ],
      "resumen": "Cambió los riesgos (confusión por edad; n pequeño -> confusión por edad; sesgo de selección)"
    },
    {
      "nombre": "espacios_nulos_y_riesgos_vacios_no_cuentan",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": null, "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "despues": {"titulo": "  GFAP sube antes que NfL  ", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI ", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": null, "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": [" confusión por edad ", "", "   "], "pasoRuta": "mecanismo"}},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "riesgos_como_texto_y_como_lista_equivalen",
      "antes": {"tarjeta": {"riesgos": "confusión por edad; n pequeño"}},
      "despues": {"tarjeta": {"riesgos": ["confusión por edad", "n pequeño"]}},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "texto_largo_o_con_saltos_se_nombra_sin_copiarlo",
      "antes": {"titulo": "GFAP sube antes que NfL", "mecanismo": "Astrogliosis reactiva"},
      "despues": {"titulo": "Un título más largo que cuarenta caracteres para el resumen", "mecanismo": "Astrogliosis\nreactiva"},
      "cambios": [
        {"campo": "titulo", "antes": "GFAP sube antes que NfL", "despues": "Un título más largo que cuarenta caracteres para el resumen"},
        {"campo": "mecanismo", "antes": "Astrogliosis reactiva", "despues": "Astrogliosis\nreactiva"}
      ],
      "resumen": "Cambió el título y el mecanismo"
    },
    {
      "nombre": "un_solo_cambio_corto",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": null},
      "despues": {"titulo": "GFAP sube antes que p-tau181", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": null},
      "cambios": [
        {"campo": "titulo", "antes": "GFAP sube antes que NfL", "despues": "GFAP sube antes que p-tau181"}
      ],
      "resumen": "Cambió el título (GFAP sube antes que NfL -> GFAP sube antes que p-tau181)"
    },
    {
      "nombre": "tres_cambios_con_comas_y_conjuncion",
      "antes": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "mecanismo"}},
      "despues": {"titulo": "GFAP sube antes que p-tau181", "enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "mecanismo": "Astrogliosis reactiva", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "transversal"}, "tarjeta": {"diana": "GFAP", "celula": "astrocito", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GFAP no sube antes que NfL en ADNI", "riesgos": ["confusión por edad"], "pasoRuta": "compromiso_diana"}},
      "cambios": [
        {"campo": "titulo", "antes": "GFAP sube antes que NfL", "despues": "GFAP sube antes que p-tau181"},
        {"campo": "comprobacion.diseno", "antes": "longitudinal", "despues": "transversal"},
        {"campo": "tarjeta.pasoRuta", "antes": "mecanismo", "despues": "compromiso_diana"}
      ],
      "resumen": "Cambió el título (GFAP sube antes que NfL -> GFAP sube antes que p-tau181), el diseño (longitudinal -> transversal) y el paso de la ruta (Mecanismo -> Compromiso de diana)"
    },
    {
      "nombre": "direccion_fuera_de_la_tabla_se_ensena_con_espacios",
      "antes": {"tarjeta": {"direccion": "sin_intervencion"}},
      "despues": {"tarjeta": {"direccion": "inhibe_parcialmente"}},
      "cambios": [
        {"campo": "tarjeta.direccion", "antes": "sin_intervencion", "despues": "inhibe_parcialmente"}
      ],
      "resumen": "Cambió la dirección (sin intervención -> inhibe parcialmente)"
    },
    {
      "nombre": "texto_en_ingles_con_etiquetas_en_castellano",
      "antes": {"titulo": "GFAP rises before NfL", "enunciado": "In APOE4 carriers GFAP changes before NfL does", "mecanismo": "Reactive astrogliosis", "comprobacion": {"biomarcador": "GFAP", "cohorte": "ADNI", "diseno": "longitudinal"}, "tarjeta": null},
      "despues": {"titulo": "GFAP rises before NfL", "enunciado": "In APOE4 carriers GFAP changes before NfL does", "mecanismo": "Reactive astrogliosis", "comprobacion": {"biomarcador": "GFAP", "cohorte": "BioFINDER", "diseno": "cross-sectional"}, "tarjeta": null},
      "cambios": [
        {"campo": "comprobacion.cohorte", "antes": "ADNI", "despues": "BioFINDER"},
        {"campo": "comprobacion.diseno", "antes": "longitudinal", "despues": "cross-sectional"}
      ],
      "resumen": "Cambió la cohorte (ADNI -> BioFINDER) y el diseño (longitudinal -> cross-sectional)"
    },
    {
      "nombre": "dos_vacias",
      "antes": {},
      "despues": {},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "comprobacion_null_frente_a_ausente",
      "antes": {"comprobacion": null, "tarjeta": null},
      "despues": {},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "valores_que_no_son_texto_valen_vacio",
      "antes": {"titulo": true, "enunciado": false, "mecanismo": {"a": 1}, "comprobacion": {"biomarcador": ["GFAP"], "cohorte": 2.0, "diseno": -0.0}, "tarjeta": {"riesgos": [["anidada"], {"texto": "objeto"}, "c", 2, 2.0, 1.5, null, false, "  "]}},
      "despues": {"titulo": "", "comprobacion": {"biomarcador": "GFAP", "cohorte": "2", "diseno": "0"}, "tarjeta": {"riesgos": "c; 2; 2; 1.5"}},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "numeros_con_decimales_se_escriben_como_python",
      "antes": {"titulo": 0.00001, "enunciado": 1e-7, "mecanismo": 123.456, "comprobacion": {"biomarcador": 1e21, "cohorte": 0.1, "diseno": -2.5e-10}},
      "despues": {},
      "cambios": [
        {"campo": "titulo", "antes": "1e-05", "despues": ""},
        {"campo": "enunciado", "antes": "1e-07", "despues": ""},
        {"campo": "mecanismo", "antes": "123.456", "despues": ""},
        {"campo": "comprobacion.biomarcador", "antes": "1000000000000000000000", "despues": ""},
        {"campo": "comprobacion.cohorte", "antes": "0.1", "despues": ""},
        {"campo": "comprobacion.diseno", "antes": "-2.5e-10", "despues": ""}
      ],
      "resumen": "Cambió el título (quitado: 1e-05), el enunciado (quitado: 1e-07), el mecanismo (quitado: 123.456), el biomarcador (quitado: 1000000000000000000000), la cohorte (quitado: 0.1) y el diseño (quitado: -2.5e-10)"
    },
    {
      "nombre": "espacios_raros_en_los_extremos_no_cuentan",
      "antes": {"titulo": "\ufeffGFAP\u00a0", "enunciado": "\u001fE\u0085", "mecanismo": "\u2028M\u3000", "comprobacion": {"cohorte": "\t ADNI \u200a", "diseno": "\u000b\u000clongitudinal\r\n"}},
      "despues": {"titulo": "GFAP", "enunciado": "E", "mecanismo": "M", "comprobacion": {"cohorte": "ADNI", "diseno": "longitudinal"}},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    },
    {
      "nombre": "un_espacio_dentro_si_cuenta_y_las_mayusculas_tambien",
      "antes": {"titulo": "GFAP sube", "comprobacion": {"cohorte": "ADNI"}},
      "despues": {"titulo": "GFAP  sube", "comprobacion": {"cohorte": "adni"}},
      "cambios": [
        {"campo": "titulo", "antes": "GFAP sube", "despues": "GFAP  sube"},
        {"campo": "comprobacion.cohorte", "antes": "ADNI", "despues": "adni"}
      ],
      "resumen": "Cambió el título (GFAP sube -> GFAP  sube) y la cohorte (ADNI -> adni)"
    },
    {
      "nombre": "claves_llamadas_como_el_prototipo_no_son_campos",
      "antes": {"constructor": "a", "toString": "b", "__proto__": {"titulo": "heredado"}, "hasOwnProperty": null, "titulo": "A"},
      "despues": {"titulo": "A"},
      "cambios": [],
      "resumen": "Sin cambios en los campos de la hipótesis"
    }
  ]
}"""
# CASOS-FIN
CASOS = json.loads(CASOS_JSON)

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def al():
    return Almacen(Path(tempfile.mkdtemp()) / "t.db")


def _hipotesis(**campos):
    return P.nueva_hipotesis("inv-t", 1, 1_700_000_000_000, **campos)


# --------------------------------------------------------------------------
# Casos compartidos con vitest
# --------------------------------------------------------------------------


@pytest.mark.parametrize("caso", CASOS["casos"], ids=[c["nombre"] for c in CASOS["casos"]])
def test_caso_compartido(caso):
    cambios = R.diff_hipotesis(caso["antes"], caso["despues"])
    assert cambios == caso["cambios"]
    assert R.resumen_diff(cambios) == caso["resumen"]


def test_etiquetas_compartidas_y_orden_fijo():
    assert list(CASOS["etiquetas"]) == list(R.ORDEN_CAMPOS)
    for campo, etiqueta in CASOS["etiquetas"].items():
        assert R.etiqueta_campo(campo) == etiqueta
    assert R.etiqueta_campo("campo_que_no_existe") == "campo_que_no_existe"
    assert R.SIN_CAMBIOS == CASOS["sinCambios"]


@pytest.mark.parametrize("legible", CASOS["legibles"], ids=[f"{l['campo']}={l['valor'] or 'vacio'}" for l in CASOS["legibles"]])
def test_valores_legibles_compartidos(legible):
    assert R.valor_legible(legible["campo"], legible["valor"]) == legible["legible"]


@pytest.mark.parametrize("cadena", CASOS["cadenas"], ids=[c["nombre"] for c in CASOS["cadenas"]])
def test_cadena_de_revisiones_compartida(cadena):
    h = cadena["hipotesis"]
    revisiones = R.revisiones_prov(h)
    assert [(r["revisionDe"], r["entidad"], r["cambios"]) for r in revisiones] == [(f"hipotesis-{h.get('id', '')}-v{e['deN']}", f"hipotesis-{h.get('id', '')}-v{e['aN']}", e["cambios"]) for e in cadena["esperado"]]


def test_paridad_con_el_test_de_vitest():
    """El bloque JSON entre CASOS-INICIO y CASOS-FIN de registro.test.ts es el
    mismo que el de este fichero: mismos datos, misma salida esperada."""
    ruta = RAIZ / "frontend" / "src" / "lib" / "registro.test.ts"
    if not ruta.exists():
        pytest.skip("sin el frontend en este árbol")
    texto = ruta.read_text(encoding="utf-8")
    bloque = re.search(r"CASOS-INICIO(.*?)CASOS-FIN", texto, re.S)
    assert bloque, "registro.test.ts no tiene el bloque CASOS-INICIO ... CASOS-FIN"
    cuerpo = bloque.group(1)
    js = cuerpo[cuerpo.index("{") : cuerpo.rindex("}") + 1]
    assert json.loads(js) == CASOS


# --------------------------------------------------------------------------
# El diff: reglas y tolerancia
# --------------------------------------------------------------------------


def test_diff_no_muta_las_entradas_y_es_determinista():
    antes = CASOS["casos"][1]["antes"]
    despues = CASOS["casos"][1]["despues"]
    copia_a, copia_d = copy.deepcopy(antes), copy.deepcopy(despues)
    primero = R.diff_hipotesis(antes, despues)
    segundo = R.diff_hipotesis(antes, despues)
    assert primero == segundo
    assert antes == copia_a and despues == copia_d
    # El orden de las claves del diccionario no cambia el orden del diff.
    barajado = {k: despues[k] for k in reversed(list(despues))}
    assert R.diff_hipotesis(antes, barajado) == primero


def test_diff_tolera_entradas_que_no_son_diccionarios():
    assert R.diff_hipotesis(None, None) == []
    assert R.diff_hipotesis("texto", 5) == []
    assert R.diff_hipotesis(None, {"titulo": "A"}) == [{"campo": "titulo", "antes": "", "despues": "A"}]
    assert R.diff_hipotesis({"titulo": "A"}, None) == [{"campo": "titulo", "antes": "A", "despues": ""}]
    # Una tarjeta que no es diccionario cuenta como vacía, no rompe.
    assert R.diff_hipotesis({"tarjeta": "rota"}, {"tarjeta": ["lista"]}) == []
    assert R.diff_hipotesis({"comprobacion": 3}, {"comprobacion": {"cohorte": "ADNI"}}) == [{"campo": "comprobacion.cohorte", "antes": "", "despues": "ADNI"}]


def test_riesgos_con_none_dentro_y_valores_no_texto():
    assert R.valor_campo({"tarjeta": {"riesgos": [None, "a", None, " b "]}}, "tarjeta.riesgos") == "a; b"
    assert R.valor_campo({"tarjeta": {"riesgos": None}}, "tarjeta.riesgos") == ""
    assert R.valor_campo({"titulo": 12}, "titulo") == "12"
    assert R.valor_campo({"titulo": "x"}, "campo_inexistente") == ""


def test_resumen_tolera_cambios_incompletos_o_desconocidos():
    assert R.resumen_diff([]) == R.SIN_CAMBIOS
    assert R.resumen_diff(None) == R.SIN_CAMBIOS
    assert R.resumen_diff([{"campo": "otro", "antes": "a", "despues": "b"}]) == "Cambió otro (a -> b)"
    assert R.resumen_diff([{"campo": "titulo"}]) == "Cambió el título"
    assert R.resumen_diff([{"campo": "titulo", "antes": None, "despues": "B"}]) == "Cambió el título (nuevo: B)"
    largo = "x" * (R.LARGO_MAXIMO_EN_RESUMEN + 1)
    justo = "x" * R.LARGO_MAXIMO_EN_RESUMEN
    assert R.resumen_diff([{"campo": "titulo", "antes": "", "despues": largo}]) == "Cambió el título"
    assert R.resumen_diff([{"campo": "titulo", "antes": "", "despues": justo}]) == f"Cambió el título (nuevo: {justo})"
    assert R.resumen_diff([{"campo": "titulo", "antes": justo, "despues": largo}]) == "Cambió el título"


def test_textos_con_tildes_y_sin_guion_largo():
    for _, _, etiqueta, nombre in R.CAMPOS:
        assert "\u2014" not in etiqueta and "\u2014" not in nombre
    assert R.etiqueta_campo("titulo") == "Título"
    assert R.etiqueta_campo("comprobacion.diseno") == "Diseño"
    assert R.etiqueta_campo("tarjeta.celula") == "Célula"
    assert R.etiqueta_campo("tarjeta.intervencion") == "Intervención"
    assert R.etiqueta_campo("tarjeta.direccion") == "Dirección"
    assert R.etiqueta_campo("tarjeta.prediccionFalsable") == "Predicción falsable"
    assert R.valor_legible("tarjeta.direccion", "sin_intervencion") == "sin intervención"
    assert "ó" in R.resumen_diff([{"campo": "titulo", "antes": "a", "despues": "b"}])
    assert "ó" in R.SIN_CAMBIOS


# --------------------------------------------------------------------------
# Instantánea extendida y versión con diff
# --------------------------------------------------------------------------


def test_instantanea_extendida_con_todo_y_con_nada():
    h = _hipotesis(elo=1512, decisionKiller="avanzar", conclusion={"certeza": "baja", "direccion": "a_favor"}, afirmaciones=[{"texto": "a"}, {"texto": "b"}])
    h["procedencia"]["fuentes"] = [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}]
    assert R.instantanea_extendida(h) == {"certeza": "baja", "direccion": "a_favor", "nAfirmaciones": 2, "nFuentes": 3, "decisionKiller": "avanzar", "elo": 1512}
    todo_none = {"certeza": None, "direccion": None, "nAfirmaciones": None, "nFuentes": None, "decisionKiller": None, "elo": None}
    assert R.instantanea_extendida(None) == todo_none
    assert R.instantanea_extendida("no es un diccionario") == todo_none
    assert R.instantanea_extendida({}) == todo_none


def test_instantanea_extendida_distingue_cero_de_no_se():
    """Una lista vacía es 0; una clave ausente o rota es None ("no pude
    comprobar"), nunca 0."""
    recien_nacida = _hipotesis()
    inst = R.instantanea_extendida(recien_nacida)
    assert inst["nAfirmaciones"] == 0 and inst["nFuentes"] == 0
    assert inst["certeza"] is None and inst["direccion"] is None and inst["decisionKiller"] is None
    assert inst["elo"] == recien_nacida["elo"]
    antigua = {"conclusion": None, "procedencia": {"fuentes": "rota"}, "afirmaciones": None}
    inst = R.instantanea_extendida(antigua)
    assert inst["nAfirmaciones"] is None and inst["nFuentes"] is None and inst["certeza"] is None
    assert R.instantanea_extendida({"conclusion": "texto suelto"})["certeza"] is None


def test_version_con_diff_copia_y_extiende():
    h = _hipotesis(titulo="A", enunciado="E1", mecanismo="M", elo=1490, decisionKiller="reformular", conclusion={"certeza": "muy_baja", "direccion": "sin_direccion"})
    h["comprobacion"].update(biomarcador="GFAP", cohorte="ADNI", diseno="longitudinal")
    version = P.version_de(h, 1_700_000_000_500, "Rosa", "más específica")
    h_antes = copy.deepcopy(h)
    h["enunciado"] = "E2"
    h["comprobacion"]["cohorte"] = "BioFINDER"
    h["version"] = 2
    h["decisionKiller"] = None
    con_anterior = R.version_con_diff(version, h, h_antes)
    assert con_anterior["cambios"] == [{"campo": "enunciado", "antes": "E1", "despues": "E2"}, {"campo": "comprobacion.cohorte", "antes": "ADNI", "despues": "BioFINDER"}]
    assert con_anterior["decisionKiller"] == "reformular" and con_anterior["elo"] == 1490
    assert con_anterior["certeza"] == "muy_baja" and con_anterior["direccion"] == "sin_direccion"
    assert con_anterior["nAfirmaciones"] == 0 and con_anterior["nFuentes"] == 0
    for clave in ("n", "fecha", "quien", "motivo", "titulo", "enunciado", "mecanismo", "comprobacion", "tarjeta"):
        assert con_anterior[clave] == version[clave]
    assert "cambios" not in version  # no muta la versión guardada
    # Sin la hipótesis anterior: lo que la versión ya tuviera se conserva y lo
    # que falte queda en None.
    version_vieja = {**version, "elo": 1400}
    sin_anterior = R.version_con_diff(version_vieja, h)
    assert sin_anterior["elo"] == 1400
    assert sin_anterior["certeza"] is None and sin_anterior["nAfirmaciones"] is None
    assert sin_anterior["cambios"] == con_anterior["cambios"]
    # Un registro antiguo que no es diccionario no rompe.
    assert R.version_con_diff(None, h)["cambios"] == R.diff_hipotesis(None, h)


# --------------------------------------------------------------------------
# Revisiones PROV
# --------------------------------------------------------------------------


def test_revisiones_prov_lleva_fecha_quien_motivo_y_tolera_lo_roto():
    h = _hipotesis(titulo="C", version=3)
    h["id"] = "hip-1"
    h["versiones"] = [
        {"n": 1, "fecha": 10, "quien": "Rosa", "motivo": "primera", "titulo": "A"},
        {"n": 2, "fecha": 20, "quien": None, "motivo": None, "titulo": "B"},
    ]
    revs = R.revisiones_prov(h)
    assert [r["entidad"] for r in revs] == ["hipotesis-hip-1-v2", "hipotesis-hip-1-v3"]
    assert [r["revisionDe"] for r in revs] == ["hipotesis-hip-1-v1", "hipotesis-hip-1-v2"]
    assert revs[0]["fecha"] == 10 and revs[0]["quien"] == "Rosa" and revs[0]["motivo"] == "primera"
    assert revs[1]["fecha"] == 20 and revs[1]["quien"] == "" and revs[1]["motivo"] == ""
    assert revs[0]["cambios"] == [{"campo": "titulo", "antes": "A", "despues": "B"}]
    assert revs[1]["cambios"] == [{"campo": "titulo", "antes": "B", "despues": "C"}]
    assert R.revisiones_prov(None) == []
    assert R.revisiones_prov({"id": "x"}) == []
    assert R.revisiones_prov({"id": "x", "versiones": None}) == []
    assert R.revisiones_prov({"id": "x", "versiones": ["rota", 3, None]}) == []
    # Una versión guardada igual que la actual da una revisión sin cambios, no desaparece.
    sin_cambio = R.revisiones_prov({"id": "x", "version": 2, "titulo": "A", "versiones": [{"n": 1, "titulo": "A"}]})
    assert len(sin_cambio) == 1 and sin_cambio[0]["cambios"] == []
    # `n` booleano o texto no vale como número: toma su posición.
    raro = R.revisiones_prov({"id": "x", "titulo": "B", "versiones": [{"n": True, "titulo": "A"}, {"n": "2", "titulo": "A2"}]})
    assert [(r["revisionDe"], r["entidad"]) for r in raro] == [("hipotesis-x-v1", "hipotesis-x-v2"), ("hipotesis-x-v2", "hipotesis-x-v3")]


# --------------------------------------------------------------------------
# De punta a punta con la acción real de reformular
# --------------------------------------------------------------------------


def test_reformular_de_verdad_y_ver_que_cambio(al):
    assert al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "3 iteraciones"}, "id_": "inv-t"}) == "inv-t"
    al.aplicar("iniciarCorrida", {"investigacion_id": "inv-t"})
    hid = al.aplicar("proponerHipotesis", {"investigacion_id": "inv-t", "datos": {"titulo": "GFAP sube antes que NfL", "enunciado": "En portadores de APOE4 GFAP se altera antes", "biomarcador": "GFAP", "cohorte": "ADNI"}, "quien": "persona"})
    h0 = copy.deepcopy(next(x for x in al.estado["hipotesis"] if x["id"] == hid))
    assert al.aplicar("reformularHipotesis", {"hipotesis_id": hid, "cambios": {"enunciado": "En portadores de APOE4 GFAP se altera antes que NfL", "comprobacion": {"cohorte": "BioFINDER"}, "tarjeta": {"prediccionFalsable": "GFAP no precede a NfL"}}, "quien": "Rosa", "motivo": "más específica"}) is True
    h = next(x for x in al.estado["hipotesis"] if x["id"] == hid)
    assert h["version"] == 2 and len(h["versiones"]) == 1
    anterior = h["versiones"][0]
    cambios = R.diff_hipotesis(anterior, h)
    assert cambios == [
        {"campo": "enunciado", "antes": "En portadores de APOE4 GFAP se altera antes", "despues": "En portadores de APOE4 GFAP se altera antes que NfL"},
        {"campo": "comprobacion.cohorte", "antes": "ADNI", "despues": "BioFINDER"},
        {"campo": "tarjeta.direccion", "antes": "", "despues": "sin_intervencion"},
        {"campo": "tarjeta.prediccionFalsable", "antes": "", "despues": "GFAP no precede a NfL"},
        {"campo": "tarjeta.pasoRuta", "antes": "", "despues": "mecanismo"},
    ]
    assert R.resumen_diff(cambios) == "Cambió el enunciado, la cohorte (ADNI -> BioFINDER), la dirección (nuevo: sin intervención), la predicción falsable (nuevo: GFAP no precede a NfL) y el paso de la ruta (nuevo: Mecanismo)"
    enriquecida = R.version_con_diff(anterior, h, h0)
    assert enriquecida["cambios"] == cambios
    assert enriquecida["decisionKiller"] is None and enriquecida["elo"] == h0["elo"]
    assert enriquecida["nAfirmaciones"] == 0 and enriquecida["nFuentes"] == 0
    revs = R.revisiones_prov(h)
    assert len(revs) == 1
    assert revs[0]["entidad"] == f"hipotesis-{hid}-v2" and revs[0]["revisionDe"] == f"hipotesis-{hid}-v1"
    assert revs[0]["quien"] == "Rosa" and revs[0]["motivo"] == "más específica" and revs[0]["cambios"] == cambios
    # El bloque de versiones sigue siendo serializable tal cual (va al estado y al RO-Crate).
    json.dumps(enriquecida, ensure_ascii=False)
    json.dumps(revs, ensure_ascii=False)


# --------------------------------------------------------------------------
# Adversariales: lo que intentó romper el módulo y ahora vigila que no vuelva
# --------------------------------------------------------------------------


def test_valores_que_no_son_texto_se_normalizan_por_regla():
    """Un booleano, un diccionario, un conjunto, NaN o infinito no tienen texto
    que enseñar: valen vacío. Un entero (también 2.0 o 1e21) se escribe sin
    decimales; uno con decimales como repr()."""
    assert R.valor_campo({"titulo": True}, "titulo") == ""
    assert R.valor_campo({"titulo": False}, "titulo") == ""
    assert R.valor_campo({"titulo": {"a": 1}}, "titulo") == ""
    assert R.valor_campo({"titulo": {"b", "a"}}, "titulo") == ""
    assert R.valor_campo({"titulo": float("nan")}, "titulo") == ""
    assert R.valor_campo({"titulo": float("inf")}, "titulo") == ""
    assert R.valor_campo({"titulo": 2.0}, "titulo") == "2"
    assert R.valor_campo({"titulo": -0.0}, "titulo") == "0"
    assert R.valor_campo({"titulo": 1e21}, "titulo") == "1000000000000000000000"
    assert R.valor_campo({"titulo": 0.00001}, "titulo") == "1e-05"
    assert R.valor_campo({"titulo": 12}, "titulo") == "12"
    assert R.valor_campo({"tarjeta": {"riesgos": ("a", ("anidada",), {"x": 1}, None, True, 3)}}, "tarjeta.riesgos") == "a; 3"
    assert R.valor_campo({"tarjeta": {"riesgos": {"a", "b"}}}, "tarjeta.riesgos") == ""  # un conjunto no tiene orden: vacío, no azar
    assert R.diff_hipotesis({"titulo": True}, {"titulo": None}) == []


def test_espacios_es_la_union_de_strip_y_trim():
    """ESPACIOS contiene todo lo que quita str.strip() más el BOM que quita
    trim() en JavaScript, y nada más; cada uno de sus caracteres se recorta en
    los extremos y no cuenta como cambio."""
    de_python = {chr(c) for c in range(0x110000) if (chr(c) + "x").strip() == "x"}
    assert set(R.ESPACIOS) == de_python | {"\ufeff"}
    assert len(set(R.ESPACIOS)) == len(R.ESPACIOS)
    for c in R.ESPACIOS:
        assert R.valor_campo({"titulo": c + "x" + c}, "titulo") == "x", hex(ord(c))
    assert R.diff_hipotesis({"titulo": "\ufeff\x1fx\x85\u3000"}, {"titulo": "x"}) == []
    # Un espacio raro dentro del texto sí cuenta.
    assert R.diff_hipotesis({"titulo": "a\u00a0b"}, {"titulo": "a b"}) == [{"campo": "titulo", "antes": "a\u00a0b", "despues": "a b"}]


def test_tablas_no_confunden_claves_del_prototipo_ni_campos_no_texto():
    """Los mismos nombres que en JavaScript viven en el prototipo ('constructor',
    'toString') son campos desconocidos en los dos lados."""
    for raro in ("constructor", "toString", "__proto__", "hasOwnProperty", "valueOf"):
        assert R.etiqueta_campo(raro) == raro
        assert R.valor_campo({raro: "x", "titulo": "A"}, raro) == ""
        assert R.valor_legible("tarjeta.direccion", raro) == raro.replace("_", " ")
        assert R.valor_legible("tarjeta.pasoRuta", raro) == raro.replace("_", " ")
        assert R.resumen_diff([{"campo": raro, "antes": "a", "despues": "b"}]) == f"Cambió {raro} (a -> b)"
    assert R.etiqueta_campo(None) == ""
    assert R.etiqueta_campo(5) == ""
    assert R.valor_campo({"titulo": "A"}, None) == ""
    assert R.valor_campo({"titulo": "A"}, ["titulo"]) == ""


def test_resumen_ignora_entradas_rotas_y_nombra_el_campo_sin_nombre():
    assert R.resumen_diff([None, "texto", 5, {"campo": "", "antes": "a", "despues": "b"}]) == f"Cambió {R.CAMPO_SIN_NOMBRE} (a -> b)"
    assert R.resumen_diff([{"campo": 5, "antes": "a", "despues": "b"}]) == f"Cambió {R.CAMPO_SIN_NOMBRE} (a -> b)"
    assert R.resumen_diff([{"antes": "a", "despues": "b"}]) == f"Cambió {R.CAMPO_SIN_NOMBRE} (a -> b)"
    assert R.resumen_diff({"campo": "titulo", "antes": "a", "despues": "b"}) == R.SIN_CAMBIOS  # un diccionario no es una lista de cambios
    assert R.resumen_diff("titulo") == R.SIN_CAMBIOS
    assert R.resumen_diff([{"campo": "tarjeta.riesgos", "antes": ["a", "b"], "despues": "a"}]) == "Cambió los riesgos (a; b -> a)"
    # El mismo campo dos veces (registro roto) se nombra dos veces, en su orden.
    assert R.resumen_diff([{"campo": "titulo", "antes": "a", "despues": "b"}, {"campo": "titulo", "antes": "b", "despues": "c"}]) == "Cambió el título (a -> b) y el título (b -> c)"
    assert "\u2014" not in R.CAMPO_SIN_NOMBRE


def test_valor_legible_normaliza_antes_de_buscar_en_la_tabla():
    assert R.valor_legible("tarjeta.direccion", "  sin_intervencion\n") == "sin intervención"
    assert R.valor_legible("tarjeta.direccion", "Aumenta") == "Aumenta"  # mayúscula: no está en la tabla, va tal cual
    assert R.valor_legible("tarjeta.pasoRuta", ["mecanismo"]) == "Mecanismo"
    assert R.valor_legible("tarjeta.riesgos", ["a", None, " b "]) == "a; b"
    assert R.valor_legible("titulo", None) == ""
    assert R.valor_legible("titulo", True) == ""
    assert R.valor_legible(None, "x") == "x"


def test_paso_ruta_legible_cubre_los_pasos_de_la_plantilla():
    """Si alguien añade un paso a PASOS_RUTA en plantilla.py, la tabla legible
    tiene que crecer igual (y la de etiquetas.ts, que vigila el caso compartido)."""
    assert set(R.PASO_RUTA_LEGIBLE) == set(P.PASOS_RUTA)
    for paso in P.PASOS_RUTA:
        assert R.valor_legible("tarjeta.pasoRuta", paso) == R.PASO_RUTA_LEGIBLE[paso]
        assert "_" not in R.PASO_RUTA_LEGIBLE[paso]
    for direccion in ("aumenta", "disminuye", "modula", "sin_intervencion"):
        assert "_" not in R.valor_legible("tarjeta.direccion", direccion)


def test_revisiones_prov_numera_de_forma_estrictamente_creciente():
    """Ninguna entidad aparece dos veces ni ninguna revisión apunta a sí misma,
    aunque el registro traiga `n` repetidos, hacia atrás o una versión actual
    atrasada."""
    h = {"id": "hip-r", "version": 2, "titulo": "F", "versiones": [{"n": 3, "titulo": "A"}, {"n": 3, "titulo": "B"}, {"n": 1, "titulo": "C"}, {"titulo": "D"}, {"n": 2, "titulo": "E"}]}
    revs = R.revisiones_prov(h)
    entidades = [r["entidad"] for r in revs]
    origenes = [r["revisionDe"] for r in revs]
    assert len(set(entidades)) == len(entidades)
    assert len(set(origenes)) == len(origenes)
    for r in revs:
        assert r["entidad"] != r["revisionDe"]
    # Cada revisión sale de la entidad que generó la anterior: una cadena, no un árbol.
    for anterior, siguiente in zip(revs, revs[1:]):
        assert siguiente["revisionDe"] == anterior["entidad"]
    numeros = [int(r["revisionDe"].rsplit("-v", 1)[1]) for r in revs] + [int(revs[-1]["entidad"].rsplit("-v", 1)[1])]
    assert numeros == sorted(numeros) and len(set(numeros)) == len(numeros)
    # El orden es el de `n` (estable) y una versión sin `n` ordena por su posición original:
    # C (n=1), E (n=2), A y B (n=3, en su orden) y D (sin n, cuarta). Se numeran 1, 2, 3, 4, 5.
    assert [r["cambios"][0]["antes"] for r in revs] == ["C", "E", "A", "B", "D"]
    assert revs[-1]["cambios"] == [{"campo": "titulo", "antes": "D", "despues": "F"}]
    # Dos llamadas dan lo mismo y no mutan la hipótesis.
    copia = copy.deepcopy(h)
    assert R.revisiones_prov(h) == revs and h == copia


def test_revisiones_prov_con_muchas_versiones_no_se_atasca():
    versiones = [{"n": i + 1, "titulo": f"T{i}", "tarjeta": {"riesgos": [f"r{j}" for j in range(20)]}} for i in range(3000)]
    h = {"id": "hip-m", "version": 3001, "titulo": "final", "tarjeta": {"riesgos": [f"r{j}" for j in range(20)]}, "versiones": versiones}
    revs = R.revisiones_prov(h)
    assert len(revs) == 3000
    assert revs[0]["revisionDe"] == "hipotesis-hip-m-v1" and revs[-1]["entidad"] == "hipotesis-hip-m-v3001"
    assert all(r["cambios"] == [{"campo": "titulo", "antes": f"T{i}", "despues": f"T{i + 1}" if i < 2999 else "final"}] for i, r in enumerate(revs))


def test_version_con_diff_con_h_anterior_que_no_es_diccionario():
    """Si quien llama pasa algo que no es la hipótesis anterior, las claves
    extendidas quedan en None ("no pude comprobar"), no en lo que hubiera."""
    v = R.version_con_diff({"n": 1, "titulo": "A", "elo": 1400}, {"titulo": "B"}, "texto")
    assert v["elo"] is None and v["certeza"] is None
    assert v["cambios"] == [{"campo": "titulo", "antes": "A", "despues": "B"}]
    # Volver a pasar por una versión ya enriquecida sin h_anterior conserva lo que tenía.
    otra = R.version_con_diff(v, {"titulo": "C"})
    assert otra["elo"] is None and otra["cambios"] == [{"campo": "titulo", "antes": "A", "despues": "C"}]
    con_elo = R.version_con_diff({"n": 1, "titulo": "A", "elo": 1400, "cambios": "viejo"}, {"titulo": "A"})
    assert con_elo["elo"] == 1400 and con_elo["cambios"] == []


def test_docstrings_y_textos_del_modulo_llevan_tildes_y_no_guion_largo():
    """Los textos que ve una persona salen de este módulo en castellano con
    sus tildes; el fichero entero no lleva U+2014."""
    fuente = (RAIZ / "rosa" / "registro.py").read_text(encoding="utf-8")
    assert "\u2014" not in fuente
    for palabra in ("hipotesis ", "version ", "tambien", "numero ", "vacio", "linea", "codigo", "diccionario ", "informacion", "aqui", "asi "):  # sin tildes
        assert not re.search(r"(?<![\w_.'\"])" + palabra + r"(?![\w_])", fuente.replace("registro.py", "").replace("frontend/src/lib/registro.ts", "")), palabra
    for texto in (R.SIN_CAMBIOS, R.CAMPO_SIN_NOMBRE, *R.DIRECCION_LEGIBLE.values(), *R.PASO_RUTA_LEGIBLE.values(), *[c[2] for c in R.CAMPOS], *[c[3] for c in R.CAMPOS]):
        assert "\u2014" not in texto
    assert R.DIRECCION_LEGIBLE["sin_intervencion"] == "sin intervención"
    assert R.PASO_RUTA_LEGIBLE["evidencia_poblacion"] == "Evidencia en la población"
    assert R.PASO_RUTA_LEGIBLE["replicacion_independiente"] == "Replicación independiente"
