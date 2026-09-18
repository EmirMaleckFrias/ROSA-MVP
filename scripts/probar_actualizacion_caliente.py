"""Prueba HMR real con una investigación ficticia y la API interceptada.

Requiere Vite en localhost:5174. Actualiza solo la fecha del almacén para
provocar HMR, sin cambiar su contenido ni llamar a la API de ROSA2018.
uv run --with playwright python scripts/probar_actualizacion_caliente.py
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(reduced_motion="reduce")
        datos = None

        def api(route):
            if route.request.url.endswith('/acceso/estado'):
                route.fulfill(json={"correo": "qa@alzheimerproject.com" if datos else None,
                                    "administrador": False, "correoConfigurado": True, "instalacionLocal": False})
            elif '/api/eventos' in route.request.url:
                route.fulfill(content_type='text/event-stream', body='event: latido\ndata: 1\n\n')
            elif route.request.url.endswith('/api/estado') and datos:
                route.fulfill(json=datos, headers={'X-Rosa-Version': '1'})
            else:
                route.fulfill(status=503, json={})

        page.route('**/api/**', api)
        page.goto('http://localhost:5174')
        page.wait_for_load_state('networkidle')
        datos = page.evaluate("async () => (await import('/src/datos/muestra.ts')).estadoDeMuestra()")
        original = datos['investigaciones'][0]['id']
        datos = json.loads(json.dumps(datos).replace(original, 'qa-investigacion-real'))
        datos['conexion'] = 'en_linea'
        page.evaluate("localStorage.setItem('rosa.recorrido.v1', '1')")
        page.goto('http://localhost:5174/#/investigaciones/qa-investigacion-real/mundo')
        page.wait_for_selector('.hecho')
        page.evaluate("""() => {
          window.pruebaHMR = {fallos: [], cambios: 0};
          new MutationObserver(() => {
            const texto = document.body.innerText;
            if (document.querySelector('.acceso') || /No se pudo cargar esta investigación|Esta investigación no existe/.test(texto)) {
              window.pruebaHMR.fallos.push(texto.slice(0, 200));
            }
          }).observe(document.body, {childList: true, subtree: true});
        }""")
        mensajes = []
        page.on('console', lambda mensaje: mensajes.append(mensaje.text))
        archivo = Path(__file__).resolve().parents[1] / 'frontend/src/datos/almacen.ts'
        for _ in range(3):
            antes = len(mensajes)
            os.utime(archivo, None)
            for _ in range(40):
                page.wait_for_timeout(250)
                if any('hot updated' in m for m in mensajes[antes:]):
                    break
            assert any('hot updated' in m for m in mensajes[antes:]), mensajes
            page.wait_for_timeout(500)
            assert page.evaluate('Boolean(window.pruebaHMR)'), 'Se recargó el documento'
            assert page.evaluate('window.pruebaHMR.fallos') == [], page.evaluate('window.pruebaHMR.fallos')
            assert page.locator('.hecho').count() > 0
        print('Tres actualizaciones HMR reales: investigación conservada, sin login ni pantalla de error.')
        browser.close()


if __name__ == '__main__':
    main()
