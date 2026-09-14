"""QA local del acceso contra una base temporal, nunca contra las corridas reales.

Con un servidor de prueba y el frontend compilado en http://localhost:8879:
uv run --with playwright python scripts/probar_acceso_visual.py
"""
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    salida = Path(tempfile.mkdtemp(prefix='rosa-acceso-visual-'))
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        pagina = navegador.new_page(viewport={'width': 1440, 'height': 1000})
        errores = []
        pagina.on('pageerror', lambda e: errores.append(str(e)))
        pagina.goto('http://localhost:8879')
        pagina.wait_for_load_state('networkidle')
        pagina.screenshot(path=str(salida / 'inicial.png'), full_page=True)
        print(json.dumps({'capturaInicial': str(salida / 'inicial.png'), 'texto': pagina.locator('body').inner_text()[:800], 'errores': errores}, ensure_ascii=False))
        assert pagina.get_by_role('heading', name='Continúa tu investigación').is_visible()
        assert pagina.get_by_alt_text('Árbol de Alzheimer Project').is_visible()
        assert pagina.get_by_role('button', name='Continuar con mi correo').is_disabled()
        assert pagina.request.get('http://localhost:8879/api/estado').status == 401
        pagina.screenshot(path=str(salida / 'escritorio.png'), full_page=True)
        pagina.get_by_role('button', name='Registrarse', exact=True).click()
        assert pagina.get_by_role('heading', name='Únete a tu equipo').is_visible()
        pagina.get_by_label('Correo de Alzheimer Project', exact=True).fill('persona@gmail.com')
        assert not pagina.locator('#acceso-correo').evaluate('(el) => el.checkValidity()')
        pagina.get_by_label('Correo de Alzheimer Project', exact=True).fill('persona@alzheimerproject.com')
        assert pagina.locator('#acceso-correo').evaluate('(el) => el.checkValidity()')
        pagina.set_viewport_size({'width': 390, 'height': 844})
        pagina.screenshot(path=str(salida / 'movil.png'), full_page=True)
        assert pagina.evaluate('document.documentElement.scrollWidth <= innerWidth')
        pagina.get_by_text('Configurar correo de esta instalación', exact=True).click()
        assert pagina.get_by_label('Clave privada de envío').get_attribute('type') == 'password'
        pagina.screenshot(path=str(salida / 'instalacion.png'), full_page=True)
        pagina.goto('http://localhost:8879/#acceso=enlace-invalido-de-prueba')
        pagina.wait_for_load_state('networkidle')
        pagina.get_by_role('button', name='Confirmar e iniciar sesión').click()
        pagina.get_by_role('status').filter(has_text='Enlace inválido').wait_for()
        assert 'acceso=' not in pagina.url
        assert not errores, errores
        navegador.close()
    print(json.dumps({'ok': True, 'capturas': str(salida), 'errores': errores}, ensure_ascii=False))


if __name__ == '__main__':
    main()
