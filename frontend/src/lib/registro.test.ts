// Qué cambió entre versiones de una hipótesis (lib/registro.ts). Los casos
// de abajo son los mismos, con el mismo texto, que los de
// rosa/tests/test_registro.py: el test de paridad de pytest lee este fichero
// y comprueba que el JSON coincide. Si se cambia uno, hay que cambiar el otro.

import { describe, expect, it } from 'vitest';
import type { Hipotesis, VersionHipotesis } from '../datos/tipos';
import { PASO_RUTA } from './etiquetas';
import { CAMPOS_DIFF, CAMPO_SIN_NOMBRE, ESPACIOS, LARGO_MAXIMO_EN_RESUMEN, SIN_CAMBIOS, cambiosPorVersion, diffVersion, etiquetaCampo, resumenDiff, valorCampo, valorLegible } from './registro';
import type { InstantaneaHipotesis, VersionRegistro } from './registro';

// CASOS-INICIO
const CASOS_JSON = String.raw`{
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
}`;
// CASOS-FIN

interface CasoDiff {
  nombre: string;
  antes: unknown;
  despues: unknown;
  cambios: { campo: string; antes: string; despues: string }[];
  resumen: string;
}

interface CasoCadena {
  nombre: string;
  hipotesis: { id?: string; version?: number; versiones?: unknown[]; titulo?: string };
  esperado: { deN: number; aN: number; cambios: { campo: string; antes: string; despues: string }[] }[];
}

interface CasosCompartidos {
  sinCambios: string;
  etiquetas: Record<string, string>;
  legibles: { campo: string; valor: string; legible: string }[];
  casos: CasoDiff[];
  cadenas: CasoCadena[];
}

const CASOS = JSON.parse(CASOS_JSON) as CasosCompartidos;

describe('casos compartidos con pytest', () => {
  for (const caso of CASOS.casos) {
    it(caso.nombre, () => {
      const cambios = diffVersion(caso.antes as InstantaneaHipotesis, caso.despues as InstantaneaHipotesis);
      expect(cambios).toEqual(caso.cambios);
      expect(resumenDiff(cambios)).toBe(caso.resumen);
    });
  }

  it('etiquetas en castellano y orden fijo', () => {
    expect(Object.keys(CASOS.etiquetas)).toEqual([...CAMPOS_DIFF]);
    for (const [campo, etiqueta] of Object.entries(CASOS.etiquetas)) expect(etiquetaCampo(campo)).toBe(etiqueta);
    expect(etiquetaCampo('campo_que_no_existe')).toBe('campo_que_no_existe');
    expect(SIN_CAMBIOS).toBe(CASOS.sinCambios);
  });

  it('valores legibles de la dirección y del paso de la ruta', () => {
    for (const l of CASOS.legibles) expect(valorLegible(l.campo, l.valor)).toBe(l.legible);
    // Las etiquetas del paso de la ruta son las de la pantalla (PASO_RUTA).
    for (const [clave, def] of Object.entries(PASO_RUTA)) expect(valorLegible('tarjeta.pasoRuta', clave)).toBe(def.etiqueta);
  });

  for (const cadena of CASOS.cadenas) {
    it(`cadena de versiones: ${cadena.nombre}`, () => {
      const h = cadena.hipotesis;
      const revisiones = cambiosPorVersion(h.versiones as VersionRegistro[] | undefined, h as InstantaneaHipotesis);
      expect(revisiones.map((r) => ({ deN: r.deN, aN: r.aN, cambios: r.cambios }))).toEqual(cadena.esperado);
    });
  }
});

describe('diffVersion', () => {
  it('acepta una VersionHipotesis y una Hipotesis del estado tal cual', () => {
    // Comprobación de tipos: si tipos.ts dejara de encajar, esto no compilaría.
    const compara = (v: VersionHipotesis, h: Hipotesis) => diffVersion(v, h);
    const porVersion = (h: Hipotesis) => cambiosPorVersion(h.versiones, h);
    expect(typeof compara).toBe('function');
    expect(typeof porVersion).toBe('function');
  });

  it('no muta las entradas y es determinista', () => {
    const caso = CASOS.casos[1]!;
    const antes = structuredClone(caso.antes) as InstantaneaHipotesis;
    const despues = structuredClone(caso.despues) as InstantaneaHipotesis;
    const primero = diffVersion(antes, despues);
    expect(diffVersion(antes, despues)).toEqual(primero);
    expect(antes).toEqual(caso.antes);
    expect(despues).toEqual(caso.despues);
    // El orden de las claves del objeto no cambia el orden del diff.
    const barajado = Object.fromEntries(Object.entries(despues).reverse()) as InstantaneaHipotesis;
    expect(diffVersion(antes, barajado)).toEqual(primero);
  });

  it('tolera entradas que no son objetos', () => {
    expect(diffVersion(null, undefined)).toEqual([]);
    expect(diffVersion('texto' as unknown as InstantaneaHipotesis, 5 as unknown as InstantaneaHipotesis)).toEqual([]);
    expect(diffVersion(null, { titulo: 'A' })).toEqual([{ campo: 'titulo', antes: '', despues: 'A' }]);
    expect(diffVersion({ titulo: 'A' }, undefined)).toEqual([{ campo: 'titulo', antes: 'A', despues: '' }]);
    expect(diffVersion({ tarjeta: 'rota' as unknown as null }, { tarjeta: ['lista'] as unknown as null })).toEqual([]);
    expect(diffVersion({ comprobacion: 3 as unknown as null }, { comprobacion: { cohorte: 'ADNI' } })).toEqual([{ campo: 'comprobacion.cohorte', antes: '', despues: 'ADNI' }]);
  });

  it('riesgos con nulos dentro y valores que no son texto', () => {
    expect(valorCampo({ tarjeta: { riesgos: [null, 'a', undefined, ' b '] } }, 'tarjeta.riesgos')).toBe('a; b');
    expect(valorCampo({ tarjeta: { riesgos: null } }, 'tarjeta.riesgos')).toBe('');
    expect(valorCampo({ titulo: 12 }, 'titulo')).toBe('12');
    expect(valorCampo({ titulo: 'x' }, 'campo_inexistente')).toBe('');
  });
});

describe('resumenDiff', () => {
  it('tolera cambios incompletos o con campos desconocidos', () => {
    expect(resumenDiff([])).toBe(SIN_CAMBIOS);
    expect(resumenDiff(null)).toBe(SIN_CAMBIOS);
    expect(resumenDiff(undefined)).toBe(SIN_CAMBIOS);
    expect(resumenDiff([{ campo: 'otro', antes: 'a', despues: 'b' }])).toBe('Cambió otro (a -> b)');
    expect(resumenDiff([{ campo: 'titulo' }])).toBe('Cambió el título');
    expect(resumenDiff([{ campo: 'titulo', antes: null, despues: 'B' }])).toBe('Cambió el título (nuevo: B)');
    const largo = 'x'.repeat(LARGO_MAXIMO_EN_RESUMEN + 1);
    const justo = 'x'.repeat(LARGO_MAXIMO_EN_RESUMEN);
    expect(resumenDiff([{ campo: 'titulo', antes: '', despues: largo }])).toBe('Cambió el título');
    expect(resumenDiff([{ campo: 'titulo', antes: '', despues: justo }])).toBe(`Cambió el título (nuevo: ${justo})`);
    expect(resumenDiff([{ campo: 'titulo', antes: justo, despues: largo }])).toBe('Cambió el título');
  });

  it('mide la longitud en puntos de código, como Python', () => {
    // 40 emojis: 80 unidades UTF-16 pero 40 puntos de código, así que caben.
    const emojis = '😀'.repeat(LARGO_MAXIMO_EN_RESUMEN);
    expect(resumenDiff([{ campo: 'titulo', antes: '', despues: emojis }])).toBe(`Cambió el título (nuevo: ${emojis})`);
  });

  it('textos con tildes y sin guion largo', () => {
    for (const campo of CAMPOS_DIFF) expect(etiquetaCampo(campo)).not.toContain('\u2014');
    expect(etiquetaCampo('titulo')).toBe('Título');
    expect(etiquetaCampo('comprobacion.diseno')).toBe('Diseño');
    expect(etiquetaCampo('tarjeta.celula')).toBe('Célula');
    expect(etiquetaCampo('tarjeta.intervencion')).toBe('Intervención');
    expect(etiquetaCampo('tarjeta.direccion')).toBe('Dirección');
    expect(etiquetaCampo('tarjeta.prediccionFalsable')).toBe('Predicción falsable');
    expect(valorLegible('tarjeta.direccion', 'sin_intervencion')).toBe('sin intervención');
    expect(resumenDiff([{ campo: 'titulo', antes: 'a', despues: 'b' }])).toContain('ó');
    expect(SIN_CAMBIOS).toContain('ó');
  });
});

describe('cambiosPorVersion', () => {
  it('devuelve la versión entera para pintarla, y tolera listas rotas', () => {
    const versiones: VersionRegistro[] = [
      { n: 1, fecha: 10, quien: 'Rosa', motivo: 'primera', titulo: 'A' },
      { n: 2, fecha: 20, quien: null, motivo: null, titulo: 'B' },
    ];
    const revs = cambiosPorVersion(versiones, { titulo: 'C', version: 3 });
    expect(revs.map((r) => [r.deN, r.aN])).toEqual([
      [1, 2],
      [2, 3],
    ]);
    expect(revs[0]!.version).toBe(versiones[0]);
    expect(revs[0]!.cambios).toEqual([{ campo: 'titulo', antes: 'A', despues: 'B' }]);
    expect(revs[1]!.cambios).toEqual([{ campo: 'titulo', antes: 'B', despues: 'C' }]);
    expect(cambiosPorVersion(null, { titulo: 'C' })).toEqual([]);
    expect(cambiosPorVersion(undefined, null)).toEqual([]);
    expect(cambiosPorVersion(['rota', 3, null] as unknown as VersionRegistro[], { titulo: 'C' })).toEqual([]);
    // Una versión igual que la actual da una revisión sin cambios, no desaparece.
    const sinCambio = cambiosPorVersion([{ n: 1, titulo: 'A' }], { titulo: 'A', version: 2 });
    expect(sinCambio).toHaveLength(1);
    expect(sinCambio[0]!.cambios).toEqual([]);
    // `n` que no es entero toma su posición.
    const raro = cambiosPorVersion([{ n: 1.5, titulo: 'A' }, { n: '2' as unknown as number, titulo: 'A2' }], { titulo: 'B' });
    expect(raro.map((r) => [r.deN, r.aN])).toEqual([
      [1, 2],
      [2, 3],
    ]);
  });
});

// Adversariales: lo que intentó romper el módulo y ahora vigila que no vuelva.
describe('adversariales', () => {
  it('los valores que no son texto se normalizan como en Python', () => {
    expect(valorCampo({ titulo: true }, 'titulo')).toBe('');
    expect(valorCampo({ titulo: false }, 'titulo')).toBe('');
    expect(valorCampo({ titulo: { a: 1 } }, 'titulo')).toBe('');
    expect(valorCampo({ titulo: () => 'x' }, 'titulo')).toBe('');
    expect(valorCampo({ titulo: NaN }, 'titulo')).toBe('');
    expect(valorCampo({ titulo: Infinity }, 'titulo')).toBe('');
    expect(valorCampo({ titulo: -0 }, 'titulo')).toBe('0');
    expect(valorCampo({ titulo: 2 }, 'titulo')).toBe('2');
    expect(valorCampo({ titulo: 1e21 }, 'titulo')).toBe('1000000000000000000000');
    expect(valorCampo({ titulo: 2 ** 60 }, 'titulo')).toBe('1152921504606846976');
    expect(valorCampo({ titulo: 10n }, 'titulo')).toBe('10');
    // repr() de Python para los decimales: fijo entre 1e-4 y 1e16, científico con dos cifras de exponente fuera.
    const casos: [number, string][] = [
      [0.00001, '1e-05'],
      [1.5e-5, '1.5e-05'],
      [1e-7, '1e-07'],
      [0.0001, '0.0001'],
      [0.00012, '0.00012'],
      [0.1, '0.1'],
      [-1.5, '-1.5'],
      [1234.5, '1234.5'],
      [123.456, '123.456'],
      [4503599627370495.5, '4503599627370495.5'],
      [-2.5e-10, '-2.5e-10'],
      [5e-324, '5e-324'],
      [0.30000000000000004, '0.30000000000000004'],
    ];
    for (const [numero, esperado] of casos) expect(valorCampo({ titulo: numero }, 'titulo')).toBe(esperado);
    expect(valorCampo({ tarjeta: { riesgos: ['a', ['anidada'], { x: 1 }, null, true, 3] } }, 'tarjeta.riesgos')).toBe('a; 3');
    expect(diffVersion({ titulo: true as unknown as string }, { titulo: null })).toEqual([]);
  });

  it('ESPACIOS es la unión de trim() y str.strip(), y cada uno se recorta', () => {
    for (let c = 0; c < 0x10000; c++) {
      const s = String.fromCharCode(c);
      if ((s + 'x').trim() === 'x') expect(ESPACIOS.includes(s), `trim quita U+${c.toString(16)}`).toBe(true);
    }
    for (const s of ['\x1c', '\x1d', '\x1e', '\x1f', '\x85', '\ufeff', '\u00a0', '\u3000']) expect(ESPACIOS.includes(s)).toBe(true);
    expect(new Set(ESPACIOS).size).toBe(ESPACIOS.length);
    expect(ESPACIOS.length).toBe(30);
    for (const c of ESPACIOS) expect(valorCampo({ titulo: c + 'x' + c }, 'titulo'), `U+${c.codePointAt(0)!.toString(16)}`).toBe('x');
    expect(diffVersion({ titulo: '\ufeff\x1fx\x85\u3000' }, { titulo: 'x' })).toEqual([]);
    // Un espacio raro dentro del texto sí cuenta.
    expect(diffVersion({ titulo: 'a\u00a0b' }, { titulo: 'a b' })).toEqual([{ campo: 'titulo', antes: 'a\u00a0b', despues: 'a b' }]);
  });

  it('las tablas no confunden claves del prototipo ni campos que no son texto', () => {
    for (const raro of ['constructor', 'toString', '__proto__', 'hasOwnProperty', 'valueOf']) {
      expect(etiquetaCampo(raro)).toBe(raro);
      expect(valorCampo({ [raro]: 'x', titulo: 'A' }, raro)).toBe('');
      expect(valorLegible('tarjeta.direccion', raro)).toBe(raro.replace(/_/g, ' '));
      expect(valorLegible('tarjeta.pasoRuta', raro)).toBe(raro.replace(/_/g, ' '));
      expect(resumenDiff([{ campo: raro, antes: 'a', despues: 'b' }])).toBe(`Cambió ${raro} (a -> b)`);
    }
    expect(etiquetaCampo(undefined as unknown as string)).toBe('');
    expect(etiquetaCampo(5 as unknown as string)).toBe('');
    expect(valorCampo({ titulo: 'A' }, undefined as unknown as string)).toBe('');
    expect(valorCampo({ titulo: 'A' }, ['titulo'] as unknown as string)).toBe('');
  });

  it('resumenDiff ignora entradas rotas y nombra el campo sin nombre', () => {
    expect(resumenDiff([null, 'texto', 5, { campo: '', antes: 'a', despues: 'b' }] as unknown as { campo: string }[])).toBe(`Cambió ${CAMPO_SIN_NOMBRE} (a -> b)`);
    expect(resumenDiff([{ campo: 5 as unknown as string, antes: 'a', despues: 'b' }])).toBe(`Cambió ${CAMPO_SIN_NOMBRE} (a -> b)`);
    expect(resumenDiff([{ antes: 'a', despues: 'b' } as unknown as { campo: string }])).toBe(`Cambió ${CAMPO_SIN_NOMBRE} (a -> b)`);
    expect(resumenDiff({ campo: 'titulo', antes: 'a', despues: 'b' } as unknown as { campo: string }[])).toBe(SIN_CAMBIOS);
    expect(resumenDiff('titulo' as unknown as { campo: string }[])).toBe(SIN_CAMBIOS);
    expect(resumenDiff([{ campo: 'tarjeta.riesgos', antes: ['a', 'b'] as unknown as string, despues: 'a' }])).toBe('Cambió los riesgos (a; b -> a)');
    expect(resumenDiff([{ campo: 'titulo', antes: 'a', despues: 'b' }, { campo: 'titulo', antes: 'b', despues: 'c' }])).toBe('Cambió el título (a -> b) y el título (b -> c)');
    expect(CAMPO_SIN_NOMBRE).not.toContain('\u2014');
  });

  it('valorLegible normaliza antes de buscar en la tabla', () => {
    expect(valorLegible('tarjeta.direccion', '  sin_intervencion\n')).toBe('sin intervención');
    expect(valorLegible('tarjeta.direccion', 'Aumenta')).toBe('Aumenta');
    expect(valorLegible('tarjeta.pasoRuta', ['mecanismo'])).toBe('Mecanismo');
    expect(valorLegible('tarjeta.riesgos', ['a', null, ' b '])).toBe('a; b');
    expect(valorLegible('titulo', null)).toBe('');
    expect(valorLegible('titulo', true)).toBe('');
    expect(valorLegible('titulo', '  x ')).toBe('x');
  });

  it('cambiosPorVersion numera de forma estrictamente creciente y tolera listas rotas', () => {
    expect(cambiosPorVersion('v1' as unknown as VersionRegistro[], { titulo: 'x' })).toEqual([]);
    expect(cambiosPorVersion({ n: 1 } as unknown as VersionRegistro[], { titulo: 'x' })).toEqual([]);
    expect(cambiosPorVersion([{ n: 1, titulo: 'A' }], 'texto' as unknown as InstantaneaHipotesis)).toEqual([{ version: { n: 1, titulo: 'A' }, deN: 1, aN: 2, cambios: [{ campo: 'titulo', antes: 'A', despues: '' }] }]);
    const versiones: VersionRegistro[] = [
      { n: 3, titulo: 'A' },
      { n: 3, titulo: 'B' },
      { n: 1, titulo: 'C' },
      { titulo: 'D' },
      { n: 2, titulo: 'E' },
    ];
    const revs = cambiosPorVersion(versiones, { titulo: 'F', version: 2 });
    const numeros = [...revs.map((r) => r.deN), revs[revs.length - 1]!.aN];
    expect(numeros).toEqual([...numeros].sort((a, b) => a - b));
    expect(new Set(numeros).size).toBe(numeros.length);
    for (let i = 1; i < revs.length; i++) expect(revs[i]!.deN).toBe(revs[i - 1]!.aN);
    expect(revs.map((r) => r.cambios[0]!.antes)).toEqual(['C', 'E', 'A', 'B', 'D']);
    expect(revs[revs.length - 1]!.cambios).toEqual([{ campo: 'titulo', antes: 'D', despues: 'F' }]);
    // No muta las versiones y es determinista.
    const copia = structuredClone(versiones);
    expect(cambiosPorVersion(versiones, { titulo: 'F', version: 2 })).toEqual(revs);
    expect(versiones).toEqual(copia);
  });

  it('con miles de versiones no se atasca', () => {
    const versiones: VersionRegistro[] = Array.from({ length: 3000 }, (_, i) => ({ n: i + 1, titulo: `T${i}`, tarjeta: { riesgos: Array.from({ length: 20 }, (_, j) => `r${j}`) } }));
    const revs = cambiosPorVersion(versiones, { titulo: 'final', version: 3001, tarjeta: { riesgos: Array.from({ length: 20 }, (_, j) => `r${j}`) } });
    expect(revs).toHaveLength(3000);
    expect(revs[0]!.deN).toBe(1);
    expect(revs[2999]!.aN).toBe(3001);
    expect(revs.every((r, i) => r.cambios.length === 1 && r.cambios[0]!.antes === `T${i}`)).toBe(true);
  });
});
